#!/usr/bin/env bash
# Hermetic end-to-end run: a throwaway ClickHouse server, the full pytest suite, every
# scripts/validate_clickhouse.py check (including a real EURUSD load) and
# examples/basic_usage.py, then teardown.
#
# Usage: bash scripts/e2e-ephemeral.sh   (or: moon run repo:e2e)
#
# The server binds 127.0.0.1 only, on two free ports picked at start, with its own config, data
# dir and passwordless `default` user, all under one mktemp dir. It never touches a shared server
# on :8123/:9000 (el02's system ClickHouse, gapless-crypto-clickhouse) or its data, and the temp dir
# is the only thing removed afterwards. EXNESS_REQUIRE_CLICKHOUSE=1 turns pytest's "ClickHouse
# unavailable" skips into a hard failure, so this run cannot pass by skipping.
#
# Memory: the load step parses a few million ticks per month with pandas. When a systemd user
# manager is up (state `running` or `degraded`; el02 is often `degraded` because of unrelated
# failed units) the whole run re-execs inside `systemd-run --user --scope -p MemoryMax=...`
# (E2E_MEMORY_MAX, default 16G). If systemd-run then fails, the run fails. Without a user manager
# the run continues uncapped and says so on stderr; E2E_MEMORY_MAX=off skips the cap on purpose.
#
# Python: the repo's .python-version wins, so an exported UV_PYTHON (which overrides it) is unset.
# Downloads: EXNESS_DOWNLOAD_DIR points inside the work dir, so no shared download dir is touched.
#
# Exit code: the first failing step's code (128+N if interrupted by signal N); 0 only when every
# step passed.
set -euo pipefail

if [[ -z "${E2E_IN_SCOPE:-}" && "${E2E_MEMORY_MAX:-16G}" != "off" ]]; then
    user_manager_state="$(systemctl --user is-system-running 2>/dev/null || true)"
    if command -v systemd-run >/dev/null 2>&1 && [[ "${user_manager_state}" =~ ^(running|degraded)$ ]]; then
        export E2E_IN_SCOPE=1
        exec systemd-run --user --scope --quiet -p MemoryMax="${E2E_MEMORY_MAX:-16G}" -- bash "$0" "$@"
    fi
    echo "WARNING: no systemd user manager (state: '${user_manager_state:-none}'); running WITHOUT a memory cap" >&2
fi

unset UV_PYTHON

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

CH="$(command -v clickhouse || true)"
if [[ -z "${CH}" ]]; then
    echo "ERROR: clickhouse binary not found on PATH" >&2
    exit 1
fi

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/exness-e2e.XXXXXX")"
SERVER_PID=""

stop_server() {
    [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null || return 0
    kill -TERM "${SERVER_PID}" 2>/dev/null || true
    for _ in $(seq 1 30); do
        kill -0 "${SERVER_PID}" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "${SERVER_PID}" 2>/dev/null; then
        echo "WARNING: ClickHouse (PID ${SERVER_PID}) ignored SIGTERM for 30s; sending SIGKILL" >&2
        kill -KILL "${SERVER_PID}" 2>/dev/null || true
    fi
    wait "${SERVER_PID}" 2>/dev/null || true
}

cleanup() {
    local rc=$?
    trap - EXIT INT TERM
    stop_server
    # Only the directory this script created; it holds nothing else.
    rm -rf -- "${WORK_DIR}"
    exit "${rc}"
}
# A signal must never end in exit 0: set the 128+N code before the EXIT trap runs cleanup.
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

read -r HTTP_PORT TCP_PORT < <(python3 -c '
import socket
socks = [socket.socket() for _ in range(2)]
for s in socks:
    s.bind(("127.0.0.1", 0))
print(*(s.getsockname()[1] for s in socks))
for s in socks:
    s.close()
')

cat > "${WORK_DIR}/config.xml" <<EOF
<clickhouse>
  <logger><level>warning</level><log>${WORK_DIR}/server.log</log><errorlog>${WORK_DIR}/server.err.log</errorlog></logger>
  <listen_host>127.0.0.1</listen_host>
  <!-- Deliberately not UTC: catches any query that parses a naive timestamp in the server zone. -->
  <timezone>America/New_York</timezone>
  <http_port>${HTTP_PORT}</http_port>
  <tcp_port>${TCP_PORT}</tcp_port>
  <path>${WORK_DIR}/data/</path>
  <tmp_path>${WORK_DIR}/tmp/</tmp_path>
  <user_files_path>${WORK_DIR}/user_files/</user_files_path>
  <users>
    <default>
      <password></password>
      <networks><ip>127.0.0.1</ip></networks>
      <profile>default</profile>
      <quota>default</quota>
    </default>
  </users>
  <profiles><default/></profiles>
  <quotas><default/></quotas>
</clickhouse>
EOF

echo "Starting throwaway ClickHouse on 127.0.0.1:${HTTP_PORT} (work dir ${WORK_DIR})..."
( cd "${WORK_DIR}" && exec "${CH}" server --config-file="${WORK_DIR}/config.xml" ) \
    > "${WORK_DIR}/stdout.log" 2>&1 &
SERVER_PID=$!

ready=0
for _ in $(seq 1 30); do
    if curl -sf --max-time 1 "http://127.0.0.1:${HTTP_PORT}/ping" >/dev/null; then
        ready=1
        break
    fi
    if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
        break
    fi
    sleep 1
done
if [[ "${ready}" -ne 1 ]]; then
    echo "ERROR: throwaway ClickHouse did not become ready" >&2
    tail -n 20 "${WORK_DIR}/server.err.log" "${WORK_DIR}/stdout.log" >&2 2>/dev/null || true
    exit 1
fi
echo "✅ ClickHouse $(curl -sf "http://127.0.0.1:${HTTP_PORT}/?query=SELECT%20version()") ready"

export CLICKHOUSE_MODE=local
export CLICKHOUSE_HOST=127.0.0.1
export CLICKHOUSE_PORT="${HTTP_PORT}"
export CLICKHOUSE_USER=default
export CLICKHOUSE_PASSWORD=""
export CLICKHOUSE_DATABASE=exness
export EXNESS_REQUIRE_CLICKHOUSE=1
export EXNESS_DOWNLOAD_DIR="${WORK_DIR}/downloads"

cd "${REPO_ROOT}"
echo "--- pytest (ClickHouse required) ---"
uv run pytest tests/ --tb=short
echo "--- validate_clickhouse.py all ---"
uv run python scripts/validate_clickhouse.py all
echo "--- examples/basic_usage.py ---"
uv run python examples/basic_usage.py
echo "✅ repo:e2e passed"
