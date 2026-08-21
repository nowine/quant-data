#!/bin/bash
# quant-collector container entrypoint.
#
# Routes --script {daily|weekly|monthly|quarterly} to the matching Python
# collector, forwarding remaining args (--mode, --config, --extra-holdings).
#
# Public contract (called by OpenClaw cron via podman run):
#   --script daily      --mode morning|close   --config PATH [--extra-holdings JSON]
#   --script weekly                          --config PATH
#   --script monthly                         --config PATH
#   --script quarterly                       --config PATH
#
# Exit codes propagate from the python collector; non-zero = cron alert.

set -euo pipefail

SCRIPT=""
ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --script)
            SCRIPT="$2"
            shift 2
            ;;
        --script=*)
            SCRIPT="${1#--script=}"
            shift
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

if [[ -z "$SCRIPT" ]]; then
    echo "[FATAL] --script {daily|weekly|monthly|quarterly} is required" >&2
    exit 2
fi

case "$SCRIPT" in
    daily)
        exec python3 src/collector_daily.py "${ARGS[@]}"
        ;;
    weekly)
        exec python3 src/collector_weekly.py "${ARGS[@]}"
        ;;
    monthly)
        exec python3 src/collector_monthly.py "${ARGS[@]}"
        ;;
    quarterly)
        exec python3 src/collector_quarterly.py "${ARGS[@]}"
        ;;
    *)
        echo "[FATAL] unknown --script value: $SCRIPT (expected daily|weekly|monthly|quarterly)" >&2
        exit 2
        ;;
esac
