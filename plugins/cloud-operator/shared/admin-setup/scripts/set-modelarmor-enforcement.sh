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

# Sets the enforcement type of the AutoCloud Model Armor template. gcloud has
# no flag for it, so this calls the Model Armor REST API (regional endpoint for
# the 'us' multi-region). Run it through log-run.sh after the admin approves:
#
#   log-run.sh "Step 8: Model Armor enforcement" --org <ORG> --project <P> -- \
#     set-modelarmor-enforcement.sh --account <A> --project <P> --mode inspect-and-block
#
# The access token is read here and sent through stdin, so it never appears in
# the command line, the process list or the change log.
#
# Works with macOS's default bash 3.2. Needs gcloud and curl.

set -uo pipefail

TEMPLATE_ID="autocloud-modelarmor-template"
LOCATION="us"
ACCOUNT=""
PROJECT=""
MODE="inspect-and-block"

usage() {
  printf 'Usage: set-modelarmor-enforcement.sh --account EMAIL --project ID [--mode inspect-and-block|inspect-only]\n' >&2
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --account) ACCOUNT="${2:-}"; shift 2 ;;
    --project) PROJECT="${2:-}"; shift 2 ;;
    --mode) MODE="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done
[ -n "$ACCOUNT" ] && [ -n "$PROJECT" ] || usage
case "$MODE" in
  inspect-and-block) TYPE="INSPECT_AND_BLOCK" ;;
  inspect-only) TYPE="INSPECT_ONLY" ;;
  *) usage ;;
esac

TOKEN="$(gcloud auth print-access-token --account="$ACCOUNT" 2>/dev/null)"
[ -n "$TOKEN" ] || {
  printf 'ERROR: could not get an access token for %s (run gcloud auth login %s)\n' "$ACCOUNT" "$ACCOUNT" >&2
  exit 1
}

URL="https://modelarmor.$LOCATION.rep.googleapis.com/v1/projects/$PROJECT/locations/$LOCATION/templates/$TEMPLATE_ID?update_mask=template_metadata.enforcement_type"
RESP="$(printf 'Authorization: Bearer %s\n' "$TOKEN" |
  curl -sS -X PATCH -H @- -H 'Content-Type: application/json' -H "x-goog-user-project: $PROJECT" \
    -d "{\"template_metadata\":{\"enforcement_type\":\"$TYPE\"}}" "$URL")"
RC=$?
if [ "$RC" -ne 0 ]; then
  printf 'ERROR: the request to the Model Armor API failed (curl exit %s)\n' "$RC" >&2
  exit 1
fi
case "$RESP" in
  *'"error"'*)
    printf 'ERROR: Model Armor API: %s\n' "$(printf '%s' "$RESP" | tr -d '\n' | sed -n 's/.*"message": *"\([^"]*\)".*/\1/p')" >&2
    exit 1
    ;;
esac
# Success only if the API returned the template with the new enforcement type.
FLAT="$(printf '%s' "$RESP" | tr -d '\n')"
if ! printf '%s' "$FLAT" | grep -q "\"name\": *\"projects/[^\"]*/templates/$TEMPLATE_ID\"" ||
  ! printf '%s' "$FLAT" | grep -q "\"enforcementType\": *\"$TYPE\""; then
  printf 'ERROR: unexpected response from the Model Armor API (no %s enforcement in it): %s\n' "$TYPE" "$(printf '%s' "$FLAT" | cut -c1-200)" >&2
  exit 1
fi
printf 'Model Armor template %s: enforcement type set to %s\n' "$TEMPLATE_ID" "$TYPE"
