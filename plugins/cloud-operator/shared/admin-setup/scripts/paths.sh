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

# Sourced by admin-status.sh and log-run.sh. Works out where the state file and
# change log for one organization and management project live:
#
#   ~/.config/cloud-operator/admin-setup/<ORG_ID>/<PROJECT_ID>/state.env
#   ~/.config/cloud-operator/admin-setup/<ORG_ID>/<PROJECT_ID>/changes.log
#
# Set CLOUD_OPERATOR_ADMIN_HOME to use another base folder. Each organization
# and project gets its own files, so nobody has to move or rename them.

ADMIN_HOME="${CLOUD_OPERATOR_ADMIN_HOME:-$HOME/.config/cloud-operator/admin-setup}"
LEGACY_DIR="$HOME/.config/cloud-operator"

STATE_DIR=""
STATE_FILE=""
LOG_FILE=""

valid_org_id() {
  case "$1" in
    '' | *[!0-9]*) return 1 ;;
  esac
}

valid_project_id() {
  case "$1" in
    '' | *[!a-z0-9.:-]* | *..*) return 1 ;;
  esac
}

# resolve_paths ORG_ID PROJECT_ID: sets STATE_DIR, STATE_FILE and LOG_FILE.
# Also moves the single state file and log that earlier versions kept in
# ~/.config/cloud-operator into the new folder, if they belong to this
# organization and project.
resolve_paths() {
  local org="$1" project="$2" legacy_org legacy_project
  valid_org_id "$org" || {
    printf 'ERROR: the organization ID must be numeric (got "%s")\n' "$org" >&2
    return 2
  }
  valid_project_id "$project" || {
    printf 'ERROR: "%s" is not a valid project ID\n' "$project" >&2
    return 2
  }
  STATE_DIR="$ADMIN_HOME/$org/$project"
  STATE_FILE="$STATE_DIR/state.env"
  LOG_FILE="$STATE_DIR/changes.log"

  # Earlier versions kept one state file and log in ~/.config/cloud-operator
  # (admin-setup.env / admin-setup.log, sometimes renamed by hand, for example
  # admin-setup.<org>.env). Move the pair that belongs to this org and project.
  if [ ! -f "$STATE_FILE" ]; then
    local legacy legacy_log
    for legacy in "$LEGACY_DIR"/admin-setup*.env; do
      [ -f "$legacy" ] || continue
      legacy_org="$(sed -n 's/^ORG_ID="\{0,1\}\([0-9]*\)"\{0,1\}$/\1/p' "$legacy" | head -n 1)"
      legacy_project="$(sed -n 's/^MGMT_PROJECT_ID="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p' "$legacy" | head -n 1)"
      [ "$legacy_org" = "$org" ] && [ "$legacy_project" = "$project" ] || continue
      mkdir -p "$STATE_DIR"
      # Keep the inputs only, quoted the way admin-status.sh writes them.
      grep -E '^(ADMIN_ACCOUNT|ORG_NAME|ORG_ID|MGMT_PROJECT_ID|MGMT_PROJECT_NUMBER|DOMAIN|USERS_GROUP|USERS_MEMBER_TYPE|EDITOR_ROLES|MODEL_ARMOR)=' "$legacy" |
        sed 's/^\([A-Z_]*\)="\{0,1\}\([^"]*\)"\{0,1\}$/\1="\2"/' >"$STATE_FILE"
      legacy_log="${legacy%.env}.log"
      if [ -f "$legacy_log" ] && [ ! -f "$LOG_FILE" ]; then mv "$legacy_log" "$LOG_FILE"; fi
      rm -f "$legacy"
      printf 'note: moved the saved setup for %s / %s to %s\n' "$org" "$project" "$STATE_DIR" >&2
      break
    done
  fi
  return 0
}
