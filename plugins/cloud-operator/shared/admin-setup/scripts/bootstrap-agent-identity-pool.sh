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

# Makes Vertex AI provision the organization's agent identity pool
# (agents.global.org-<ORG_ID>.system.id.goog).
#
# Vertex AI creates that organization-level pool the first time any project in
# the organization creates an agent that uses Agent Identity; enabling APIs
# doesn't. Until then IAM can't resolve the
# principalSet://agents.global.org-<ORG_ID>.system.id.goog/... members that
# setup Steps 5 and 10 use ("Identity Pool does not exist", "Failed to resolve
# policy members"). This script creates a temporary, empty Agent Engine
# (Reasoning Engine) instance with identityType AGENT_IDENTITY in the
# management project, waits for it, checks that it got an agent identity, and
# deletes it again. The pool is permanent, so this is needed at most once per
# organization. Run it through log-run.sh after the admin approves:
#
#   log-run.sh "Step 5: Bootstrap agent identity pool" --org <ORG> --project <P> -- \
#     bootstrap-agent-identity-pool.sh --account <A> --project <P>
#
# Needs aiplatform.googleapis.com enabled and permission to create and delete
# Agent Engine instances (roles/aiplatform.user, roles/aiplatform.admin or
# Owner). The access token is read here and sent through stdin, so it never
# appears in the command line, the process list or the change log.
#
# Works with macOS's default bash 3.2. Needs gcloud and curl.

set -uo pipefail

ACCOUNT=""
PROJECT=""
REGION="us-central1"
KEEP=0
TIMEOUT_S=180
INTERVAL_S=5
DISPLAY_NAME="autocloud-agent-identity-pool-bootstrap"
DESCRIPTION="Temporary. Created by Cloud Operator admin setup so Vertex AI provisions the organization's agent identity pool. Safe to delete."

usage() {
  printf 'Usage: bootstrap-agent-identity-pool.sh --account EMAIL --project ID [--region us-central1] [--keep]\n' >&2
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --account) ACCOUNT="${2:-}"; shift 2 ;;
    --project) PROJECT="${2:-}"; shift 2 ;;
    --region) REGION="${2:-}"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    *) usage ;;
  esac
done
[ -n "$ACCOUNT" ] && [ -n "$PROJECT" ] && [ -n "$REGION" ] || usage
case "$REGION" in *[!a-z0-9-]*) usage ;; esac

TOKEN="$(gcloud auth print-access-token --account="$ACCOUNT" 2>/dev/null)"
[ -n "$TOKEN" ] || {
  printf 'ERROR: could not get an access token for %s (run gcloud auth login %s)\n' "$ACCOUNT" "$ACCOUNT" >&2
  exit 1
}
BASE="https://$REGION-aiplatform.googleapis.com/v1beta1"

# api METHOD URL [BODY]: calls the Vertex AI API and prints the response.
api() {
  local method="$1" url="$2" body="${3:-}"
  if [ -n "$body" ]; then
    printf 'Authorization: Bearer %s\n' "$TOKEN" |
      curl -sS -X "$method" -H @- -H 'Content-Type: application/json' -H "x-goog-user-project: $PROJECT" -d "$body" "$url"
  else
    printf 'Authorization: Bearer %s\n' "$TOKEN" |
      curl -sS -X "$method" -H @- -H "x-goog-user-project: $PROJECT" "$url"
  fi
}

# Prints the value of the first "KEY": "value" pair in JSON on stdin.
json_string() {
  tr -d '\n' | sed -n "s/.*\"$1\": *\"\\([^\"]*\\)\".*/\\1/p"
}

error_message() {
  printf '%s' "$1" | tr -d '\n' | sed -n 's/.*"message": *"\([^"]*\)".*/\1/p'
}

# 1. Create the temporary instance.
RESP="$(api POST "$BASE/projects/$PROJECT/locations/$REGION/reasoningEngines" \
  "{\"displayName\":\"$DISPLAY_NAME\",\"description\":\"$DESCRIPTION\",\"spec\":{\"identityType\":\"AGENT_IDENTITY\"}}")" || {
  printf 'ERROR: the request to the Vertex AI API failed\n' >&2
  exit 1
}
case "$RESP" in
  *'"error"'*)
    printf 'ERROR: creating the temporary Agent Engine instance failed: %s\n' "$(error_message "$RESP")" >&2
    exit 1
    ;;
esac
OPERATION="$(printf '%s' "$RESP" | json_string name)"
case "$OPERATION" in
  */operations/*) ;;
  *)
    printf 'ERROR: the create call returned no operation: %s\n' "$(printf '%s' "$RESP" | tr -d '\n' | cut -c1-300)" >&2
    exit 1
    ;;
esac
ENGINE="${OPERATION%%/operations/*}"
printf 'created %s; waiting for it (up to %ss)\n' "$ENGINE" "$TIMEOUT_S"

# 2. Wait for the operation.
WAITED=0
OP=""
while :; do
  OP="$(api GET "$BASE/$OPERATION")" || OP=""
  if printf '%s' "$OP" | tr -d '\n' | grep -q '"done": *true'; then break; fi
  if [ "$WAITED" -ge "$TIMEOUT_S" ]; then
    printf 'ERROR: %s did not finish in %ss; delete %s by hand once it has\n' "$OPERATION" "$TIMEOUT_S" "$ENGINE" >&2
    exit 1
  fi
  sleep "$INTERVAL_S"
  WAITED=$((WAITED + INTERVAL_S))
done

PROBLEM=""
case "$OP" in
  *'"error"'*) PROBLEM="creating the instance failed: $(error_message "$OP")" ;;
esac
IDENTITY="$(printf '%s' "$OP" | json_string effectiveIdentity)"
if [ -z "$PROBLEM" ]; then
  case "$IDENTITY" in
    agents.*) ;;
    *) PROBLEM="the instance didn't get an agent identity (effectiveIdentity '${IDENTITY:-none}'), so the pool was probably not provisioned" ;;
  esac
fi

# 3. Delete the temporary instance.
CLEANUP="kept $ENGINE (--keep)"
if [ "$KEEP" -eq 0 ]; then
  DEL="$(api DELETE "$BASE/$ENGINE?force=true")" || DEL='{"error":{"message":"request failed"}}'
  case "$DEL" in
    *'"error"'*)
      CLEANUP="could not delete $ENGINE ($(error_message "$DEL")); delete it by hand"
      printf 'WARNING: %s\n' "$CLEANUP" >&2
      ;;
    *) CLEANUP="deleted $ENGINE" ;;
  esac
fi

if [ -n "$PROBLEM" ]; then
  printf 'ERROR: %s; %s\n' "$PROBLEM" "$CLEANUP" >&2
  exit 1
fi
printf 'agent identity pool is ready (effectiveIdentity %s); %s\n' "$IDENTITY" "$CLEANUP"
