#!/usr/bin/env bash
# Start the local ClickHouse server for exness-data-preprocess.
#
# Usage: bash scripts/clickhouse-start.sh   (or: moon run repo:clickhouse-start)
#
# Data dir: ${CLICKHOUSE_DATA_DIR:-$XDG_DATA_HOME/exness-data-preprocess/clickhouse}
#           (default ~/.local/share/exness-data-preprocess/clickhouse)
# Pidfile:  <data dir>/clickhouse-server.pid, read by scripts/clickhouse-stop.sh
#
# The server listens on localhost:8123. gapless-crypto-clickhouse runs its own local server on the
# same port with a different data dir, so only one of the two can be up at a time; if the port is
# already taken this script reports it and exits 0 without starting anything.
set -euo pipefail

# Resolve the clickhouse binary, PATH first. proto shims, Homebrew and system installs all feed
# PATH; the explicit fallbacks cover a non-login shell whose PATH skipped profile activation.
CH=""
if command -v clickhouse >/dev/null 2>&1; then
    CH="$(command -v clickhouse)"
else
    for c in "${HOME}/.proto/shims/clickhouse" /opt/homebrew/bin/clickhouse /usr/local/bin/clickhouse; do
        if [[ -x "$c" ]]; then CH="$c"; break; fi
    done
fi

if [[ -z "$CH" ]]; then
    echo "ERROR: clickhouse binary not found on PATH or at any known location." >&2
    echo "       Install it (e.g. 'brew install clickhouse') or put it on PATH." >&2
    exit 1
fi

# Check if already running
if nc -z localhost 8123 2>/dev/null; then
    echo "✅ ClickHouse already running on port 8123"
    "${CH}" client --query "SELECT version()"
    exit 0
fi

# `clickhouse server` writes its data tree (store/, metadata/, cores/, status, uuid) relative to
# the working directory and exposes no --path flag, so it is started from a data dir OUTSIDE the
# repository; launched from a checkout it would litter the repo root with server state.
CLICKHOUSE_DATA_DIR="${CLICKHOUSE_DATA_DIR:-${XDG_DATA_HOME:-${HOME}/.local/share}/exness-data-preprocess/clickhouse}"
PID_FILE="${CLICKHOUSE_DATA_DIR}/clickhouse-server.pid"
mkdir -p "${CLICKHOUSE_DATA_DIR}"

echo "Starting ClickHouse server (data dir: ${CLICKHOUSE_DATA_DIR})..."
( cd "${CLICKHOUSE_DATA_DIR}" && "${CH}" server --daemon --pid-file="${PID_FILE}" )

# Wait for server to be ready
for _ in $(seq 1 10); do
    if nc -z localhost 8123 2>/dev/null; then
        echo "✅ ClickHouse server started (pidfile: ${PID_FILE})"
        "${CH}" client --query "SELECT version()"
        exit 0
    fi
    sleep 1
done

echo "ERROR: ClickHouse failed to start" >&2
exit 1
