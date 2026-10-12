#!/usr/bin/env bash
# Stop the local ClickHouse server started by scripts/clickhouse-start.sh.
#
# Usage: bash scripts/clickhouse-stop.sh   (or: moon run repo:clickhouse-stop)
#
# Stops exactly the PID recorded in this repo's pidfile, never by process-name match, so a
# ClickHouse server started by another project (e.g. gapless-crypto-clickhouse on the same port)
# is left alone. Exit codes: 0 = stopped or not running, 1 = failed to stop.
set -euo pipefail

CLICKHOUSE_DATA_DIR="${CLICKHOUSE_DATA_DIR:-${XDG_DATA_HOME:-${HOME}/.local/share}/exness-data-preprocess/clickhouse}"
PID_FILE="${CLICKHOUSE_DATA_DIR}/clickhouse-server.pid"

if [[ ! -f "${PID_FILE}" ]]; then
    echo "ClickHouse was not running (no pidfile at ${PID_FILE})"
    if nc -z localhost 8123 2>/dev/null; then
        echo "Note: something else is listening on port 8123; it was not started by this repo, so it is left alone."
    fi
    exit 0
fi

PID="$(tr -d '[:space:]' < "${PID_FILE}")"
if [[ ! "${PID}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: pidfile ${PID_FILE} does not hold a PID: '${PID}'" >&2
    exit 1
fi

# Only signal the PID if it is still a clickhouse process (guards against a stale pidfile whose
# PID has been reused by an unrelated process).
CMD="$(ps -p "${PID}" -o command= 2>/dev/null || true)"
if [[ -z "${CMD}" ]]; then
    echo "ClickHouse was not running (stale pidfile for PID ${PID}); removing it"
    rm -f "${PID_FILE}"
    exit 0
fi
if [[ "${CMD}" != *clickhouse* ]]; then
    echo "ERROR: PID ${PID} from ${PID_FILE} is not a clickhouse process: ${CMD}" >&2
    exit 1
fi

kill -TERM "${PID}"
for _ in $(seq 1 30); do
    if ! kill -0 "${PID}" 2>/dev/null; then
        rm -f "${PID_FILE}"
        echo "✅ ClickHouse server stopped (PID ${PID})"
        exit 0
    fi
    sleep 1
done

echo "ERROR: ClickHouse (PID ${PID}) did not exit within 30s after SIGTERM" >&2
exit 1
