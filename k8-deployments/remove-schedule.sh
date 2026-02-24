#!/usr/bin/env bash
set -euo pipefail

MARKER="# scorecheck-k8-schedule"
EXISTING_CRON="$(crontab -l 2>/dev/null || true)"

printf '%s\n' "${EXISTING_CRON}" | grep -v "${MARKER}" | crontab -

echo "Removed scorecheck sleep/wake cron schedule."
