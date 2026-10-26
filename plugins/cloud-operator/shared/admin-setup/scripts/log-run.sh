#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Runs one command that changes something for the Cloud Operator admin setup,
# shows its output, and appends a line to the change log of that organization
# and management project:
#
#   log-run.sh "<step label>" --org <ORG_ID> --project <PROJECT_ID> -- gcloud ...
#
# The log is ~/.config/cloud-operator/admin-setup/<ORG_ID>/<PROJECT_ID>/changes.log
# (see paths.sh).
#
# Log line (tab-separated): UTC time, account, step, OK or FAILED(<exit code>),
# the command, and the last line of its error output when it failed. The log
# never holds tokens: the commands it records don't contain any.
#
# Exits with the command's exit status. Works with macOS's default bash 3.2.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=paths.sh
. "$SCRIPT_DIR/paths.sh"

usage() {
  printf 'Usage: log-run.sh "<step label>" --org <ORG_ID> --project <PROJECT_ID> -- <command> [args...]\n' >&2
  exit 2
}

[ $# -ge 1 ] || usage
STEP="$1"
shift
ORG=""
PROJECT=""
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
  case "$1" in
    --org) ORG="${2:-}"; shift 2 ;;
    --project) PROJECT="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done
[ "${1:-}" = "--" ] || usage
shift
[ $# -ge 1 ] || usage
resolve_paths "$ORG" "$PROJECT" || exit 2

# The account is whatever --account=X or --account X the command passes.
ACCOUNT="-"
PREV=""
for arg in "$@"; do
  case "$arg" in
    --account=*) ACCOUNT="${arg#--account=}" ;;
  esac
  if [ "$PREV" = "--account" ]; then ACCOUNT="$arg"; fi
  PREV="$arg"
done

# Quote the command so the log line can be copied and run again.
CMD=""
for arg in "$@"; do
  CMD="$CMD $(printf '%q' "$arg")"
done
CMD="${CMD# }"

ERR_FILE="$(mktemp)"
trap 'rm -f "$ERR_FILE"' EXIT

"$@" 2> >(tee "$ERR_FILE" >&2)
RC=$?
# Let tee finish writing before reading the error output.
wait 2>/dev/null || true

if [ "$RC" -eq 0 ]; then
  RESULT="OK"
  ERR=""
else
  RESULT="FAILED($RC)"
  # gcloud's own "ERROR: (gcloud...)" line is the most useful; some APIs add
  # stack traces after it, so take the first ERROR line before anything else.
  ERR="$(grep -E '^ERROR:' "$ERR_FILE" | head -n 1)"
  [ -n "$ERR" ] || ERR="$(grep -v '^[[:space:]]*$' "$ERR_FILE" | grep -v -E '\.go:[0-9]+|0x[0-9a-f]{6,}' | grep -E 'error|denied|DENIED|PRECONDITION|NOT_FOUND|INVALID' | head -n 1)"
  [ -n "$ERR" ] || ERR="$(grep -v '^[[:space:]]*$' "$ERR_FILE" | tail -n 1)"
  ERR="$(printf '%s' "$ERR" | tr '\t' ' ' | cut -c1-300)"
fi

mkdir -p "$(dirname "$LOG_FILE")"
printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$ACCOUNT" "$STEP" "$RESULT" "$CMD" "$ERR" >>"$LOG_FILE"
printf '\n[%s] %s, logged to %s\n' "$STEP" "$RESULT" "$LOG_FILE" >&2
exit "$RC"
