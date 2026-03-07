#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${REPO_DIR}/k8-deployments/schedule.log"
MARKER="# scorecheck-k8-schedule"

SLEEP_JOB="0 0 * * * cd ${REPO_DIR} && /bin/bash -lc 'make k8-sleep >> ${LOG_FILE} 2>&1' ${MARKER}"
WAKE_JOB="0 8 * * * cd ${REPO_DIR} && /bin/bash -lc 'make k8-wake >> ${LOG_FILE} 2>&1' ${MARKER}"

EXISTING_CRON="$(crontab -l 2>/dev/null || true)"
FILTERED_CRON="$(printf '%s\n' "${EXISTING_CRON}" | grep -v "${MARKER}" || true)"

{
  printf '%s\n' "${FILTERED_CRON}" | sed '/^$/d'
  echo "${SLEEP_JOB}"
  echo "${WAKE_JOB}"
} | crontab -

echo "Installed schedule (local timezone):"
echo "- Sleep: 00:00 daily"
echo "- Wake : 08:00 daily"
echo "Logs: ${LOG_FILE}"
