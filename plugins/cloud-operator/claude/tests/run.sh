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

# Stub tests for scripts/register-mcp.sh. They run with a fake claude command
# first on PATH and a throwaway HOME, so they touch no real Claude Code state
# and open no browser.
#
#   bash plugins/cloud-operator/claude/tests/run.sh          # all tests
#   bash plugins/cloud-operator/claude/tests/run.sh web_     # names matching
#   /bin/bash plugins/cloud-operator/claude/tests/run.sh     # macOS's bash 3.2
#
# The script under test runs with the same bash as this file. Needs perl
# (with JSON::PP and Digest::SHA); the python3 test runs only where python3
# exists.

set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../scripts/register-mcp.sh"
STUBS="$HERE/stubs"
ORIG_PATH="$PATH"
FILTER="${1:-}"
# Fake values, shaped like real ones. Not real credentials.
FAKE_SECRET="GOCSPX-fakeTestSecret0123456789abc"
FAKE_ID="123456789012-fakeclientid0123456789abcdef.apps.googleusercontent.com"
sha() { printf '%s' "$1" | perl -MDigest::SHA=sha256_hex -e 'local $/; print sha256_hex(<STDIN>)'; }
FAKE_SECRET_SHA="$(sha "$FAKE_SECRET")"

PASS=0
FAIL=0
SKIP=0
FAILED_NAMES=""
TMPROOT="$(mktemp -d "${TMPDIR:-/tmp}/oc-tests.XXXXXX")"
trap 'chmod -R u+rwx "$TMPROOT" 2>/dev/null; rm -rf "$TMPROOT"' EXIT

# --- helpers ---------------------------------------------------------------

# Fresh, isolated environment for one test. F is a credentials file path.
setup() {
  T="$TMPROOT/$1"
  F="$T/creds/client.json"
  mkdir -p "$T/home" "$T/log" "$T/tmp" "$T/creds"
  export HOME="$T/home"
  export TMPDIR="$T/tmp"
  export CLAUDE_STUB_LOG="$T/log/claude.log"
  : >"$CLAUDE_STUB_LOG"
  export PATH="$STUBS:$ORIG_PATH"
  unset CLOUD_OPERATOR_CLIENT_ID CLOUD_OPERATOR_CLIENT_SECRET CLOUD_OPERATOR_JSON_TOOL CLAUDE_STUB_FAIL_ADD
}

# write_client KIND PATH - a credentials file shaped like the one the console
# downloads (one line, JSON.stringify output). KIND is installed (Desktop
# app) or web (Web application).
write_client() {
  local kind="$1" path="$2" redirect="http://localhost"
  if [ "$kind" = web ]; then redirect="http://localhost:3118/callback"; fi
  mkdir -p "$(dirname "$path")"
  printf '{"%s":{"client_id":"%s","project_id":"dk-test-proj","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_secret":"%s","redirect_uris":["%s"]}}' \
    "$kind" "$FAKE_ID" "$FAKE_SECRET" "$redirect" >"$path"
}

# run_register ARGS... - runs register-mcp.sh without a terminal, as Claude's
# Bash tool does. Sets OUT (stdout and stderr) and RC.
run_register() {
  OUT="$("$BASH" "$SCRIPT" "$@" </dev/null 2>&1)"
  RC=$?
}

# run_register_in DIR ARGS... - the same, from folder DIR.
run_register_in() {
  local dir="$1"
  shift
  OUT="$(cd "$dir" && "$BASH" "$SCRIPT" "$@" </dev/null 2>&1)"
  RC=$?
}

CUR_OK=1
check() { # check DESCRIPTION CONDITION_RESULT
  if [ "$2" -ne 0 ]; then
    CUR_OK=0
    printf '    FAIL: %s\n' "$1"
  fi
}
skip() {
  CUR_OK=2
  printf '    (skipped: %s)\n' "$1"
}
assert_rc() { [ "$RC" -eq "$1" ]; check "exit code $RC, want $1" $?; }
assert_out_has() { case "$OUT" in *"$1"*) check "output has: $1" 0 ;; *) check "output has: $1" 1 ;; esac; }
assert_no_secret() {
  case "$OUT" in *GOCSPX-*) check "no secret in output" 1 ;; *) check "no secret in output" 0 ;; esac
  ! grep -q 'GOCSPX-' "$T/log/claude.log"
  check "no secret in the claude stub log" $?
}
assert_log_has() { grep -qF -- "$1" "$T/log/claude.log"; check "claude log has: $1" $?; }
assert_log_lacks() { ! grep -qF -- "$1" "$T/log/claude.log"; check "claude log lacks: $1" $?; }
assert_not_registered() { assert_log_lacks "add-json"; }
assert_exists() { [ -e "$1" ]; check "kept: $1" $?; }
registered_with() { # registered_with JSON_FRAGMENT
  grep -F "claude mcp add-json -s user autocloud " "$T/log/claude.log" | grep -F -- "$1" | grep -qF "MCP_CLIENT_SECRET=sha256:$FAKE_SECRET_SHA"
  check "registered autocloud with $1 and the right secret" $?
}

run_test() { # run_test NAME
  case "$1" in *"$FILTER"*) ;; *) return 0 ;; esac
  CUR_OK=1
  OUT=""
  setup "$1"
  "test_$1"
  case "$CUR_OK" in
    1)
      PASS=$((PASS + 1))
      printf 'ok   %s\n' "$1"
      ;;
    2)
      SKIP=$((SKIP + 1))
      printf 'skip %s\n' "$1"
      ;;
    *)
      FAIL=$((FAIL + 1))
      FAILED_NAMES="$FAILED_NAMES $1"
      printf 'FAIL %s\n' "$1"
      printf '%s\n' "$OUT" | sed 's/^/      | /'
      ;;
  esac
}

# --- --client-json: reading the file ------------------------------------------

test_json_desktop() {
  write_client installed "$F"
  run_register --client-json "$F" --no-login
  assert_rc 0
  assert_out_has "credentials file: $F"
  assert_out_has "client ID: $FAKE_ID"
  registered_with "\"oauth\":{\"clientId\":\"$FAKE_ID\"}}"
  assert_log_has '"url":"https://geminicloudassist.googleapis.com/mcp/autocloud","timeout":1800000'
  assert_log_has "--client-secret"
  assert_log_has "claude mcp logout autocloud"
  assert_log_lacks "claude mcp login"
  assert_exists "$F"
  assert_out_has "still holds the client secret"
  assert_no_secret
}

test_json_equals_form() {
  write_client installed "$F"
  run_register --client-json="$F" --no-login
  assert_rc 0
  registered_with "\"clientId\":\"$FAKE_ID\""
}

test_json_any_name_with_spaces() {
  local f="$T/My Files/oauth credentials (1).json"
  write_client installed "$f"
  run_register --client-json "$f" --no-login
  assert_rc 0
  registered_with "\"clientId\":\"$FAKE_ID\""
  assert_exists "$f"
  assert_no_secret
}

test_json_relative_path() {
  write_client installed "$F"
  run_register_in "$T/creds" --client-json client.json --no-login
  assert_rc 0
  registered_with "\"clientId\":\"$FAKE_ID\""
}

test_json_tilde_path() {
  write_client installed "$HOME/Downloads/client.json"
  # shellcheck disable=SC2088 # the script expands it, as a quoted path would arrive
  run_register --client-json='~/Downloads/client.json' --no-login
  assert_rc 0
  assert_out_has "credentials file: $HOME/Downloads/client.json"
  registered_with "\"clientId\":\"$FAKE_ID\""
}

test_json_byte_order_mark() {
  write_client installed "$T/plain.json"
  { printf '\357\273\277'; cat "$T/plain.json"; } >"$F"
  run_register --client-json "$F" --no-login
  assert_rc 0
  registered_with "\"clientId\":\"$FAKE_ID\""
}

# Cases that both parsers must handle alike: test_json_dash_path and
# test_json_trailing_newline run them with perl, test_json_python3 with python3.

# A relative path that starts with -. perl takes it for one of its own
# switches unless -- comes before it.
case_dash_path() {
  : >"$CLAUDE_STUB_LOG"
  write_client installed "$T/creds/-x.json"
  run_register_in "$T/creds" --client-json -x.json --no-login
  assert_rc 0
  assert_out_has "credentials file: -x.json"
  registered_with "\"clientId\":\"$FAKE_ID\""
  assert_no_secret
}

# A client ID or secret that ends in a newline. In perl, $ also matches before
# a final newline.
case_trailing_newline() {
  : >"$CLAUDE_STUB_LOG"
  printf '{"installed":{"client_id":"%s\\n","client_secret":"%s"}}' "$FAKE_ID" "$FAKE_SECRET" >"$F"
  run_register --client-json "$F" --no-login
  assert_rc 1
  assert_out_has "it has no valid client_id"
  assert_no_secret
  printf '{"installed":{"client_id":"%s","client_secret":"%s\\n"}}' "$FAKE_ID" "$FAKE_SECRET" >"$F"
  run_register --client-json "$F" --no-login
  assert_rc 1
  assert_out_has "its client_secret has unexpected characters"
  assert_not_registered
  assert_no_secret
}

test_json_dash_path() {
  export CLOUD_OPERATOR_JSON_TOOL=perl
  case_dash_path
}

test_json_trailing_newline() {
  export CLOUD_OPERATOR_JSON_TOOL=perl
  case_trailing_newline
}

test_json_web_needs_port() {
  write_client web "$F"
  run_register --client-json "$F" --no-login
  assert_rc 1
  assert_out_has "holds a Web application client: add --callback-port"
  assert_not_registered
  assert_no_secret
}

test_json_web_with_port() {
  write_client web "$F"
  run_register --client-json "$F" --callback-port 3118 --no-login
  assert_rc 0
  registered_with "\"oauth\":{\"clientId\":\"$FAKE_ID\",\"callbackPort\":3118}}"
  assert_no_secret
}

test_json_missing_file() {
  run_register --client-json "$T/nope.json" --no-login
  assert_rc 1
  assert_out_has "no such file: $T/nope.json"
  assert_not_registered
}

test_json_directory() {
  run_register --client-json "$T/creds" --no-login
  assert_rc 1
  assert_out_has "not a file: $T/creds"
}

test_json_missing_value() {
  run_register --client-json
  assert_rc 1
  assert_out_has "--client-json needs a value"
}

test_json_empty_value() {
  run_register --client-json= --no-login
  assert_rc 1
  assert_out_has "--client-json needs the path of your OAuth client credentials JSON file"
}

test_json_no_secret() {
  printf '{"installed":{"client_id":"%s","project_id":"p","redirect_uris":["http://localhost"]}}' "$FAKE_ID" >"$F"
  run_register --client-json "$F" --no-login
  assert_rc 1
  assert_out_has "$F: it has no client_secret"
  assert_not_registered
}

test_json_bad_values() {
  printf '{"installed":{"client_id":"bad id","client_secret":"%s"}}' "$FAKE_SECRET" >"$F"
  run_register --client-json "$F" --no-login
  assert_rc 1
  assert_out_has "it has no valid client_id"
  assert_no_secret
  printf '{"installed":{"client_id":"%s","client_secret":"%s with space"}}' "$FAKE_ID" "$FAKE_SECRET" >"$F"
  run_register --client-json "$F" --no-login
  assert_rc 1
  assert_out_has "its client_secret has unexpected characters"
  assert_not_registered
  assert_no_secret
}

test_json_not_client_file() {
  printf '{"type":"service_account","client_id":"123","private_key":"x"}' >"$F"
  run_register --client-json "$F" --no-login
  assert_rc 1
  assert_out_has "it is not an OAuth client credentials file"
  assert_not_registered
}

test_json_malformed() {
  printf '{"installed":{"client_id":"%s","client_secret":"%s"' "$FAKE_ID" "$FAKE_SECRET" >"$F"
  run_register --client-json "$F" --no-login
  assert_rc 1
  assert_out_has "it is not valid JSON"
  assert_not_registered
  assert_no_secret
}

test_json_empty_file() {
  : >"$F"
  run_register --client-json "$F" --no-login
  assert_rc 1
  assert_out_has "it is empty"
}

test_json_unreadable() {
  if [ "$(id -u)" = 0 ]; then
    skip "running as root, which can read any file"
    return 0
  fi
  write_client installed "$F"
  chmod 000 "$F"
  run_register --client-json "$F" --no-login
  chmod 600 "$F"
  assert_rc 1
  assert_out_has "$F: cannot read it"
  assert_not_registered
}

test_json_claude_fails() {
  write_client installed "$F"
  export CLAUDE_STUB_FAIL_ADD=1
  run_register --client-json "$F" --no-login
  assert_rc 1
  assert_out_has "couldn't register the server"
  assert_exists "$F"
  assert_no_secret
}

test_json_python3() {
  if ! command -v python3 >/dev/null 2>&1; then
    skip "no python3"
    return 0
  fi
  export CLOUD_OPERATOR_JSON_TOOL=python3
  write_client web "$F"
  run_register --client-json "$F" --callback-port 3118 --no-login
  assert_rc 0
  registered_with "\"callbackPort\":3118"
  assert_no_secret
  printf '{"installed":{"client_id":"%s"}}' "$FAKE_ID" >"$T/no-secret.json"
  run_register --client-json "$T/no-secret.json" --no-login
  assert_rc 1
  assert_out_has "it has no client_secret"
  case_dash_path
  case_trailing_newline
}

test_json_no_json_tool() {
  export CLOUD_OPERATOR_JSON_TOOL=none
  write_client installed "$F"
  run_register --client-json "$F" --no-login
  assert_rc 1
  assert_out_has "needs perl (with JSON::PP) or python3"
  assert_not_registered
  assert_no_secret
}

# --- other paths ----------------------------------------------------------------

test_login_needs_terminal() {
  write_client installed "$F"
  run_register --client-json "$F"
  assert_rc 0
  assert_out_has "no terminal to sign in from"
  assert_log_lacks "claude mcp login autocloud"
  assert_no_secret
}

test_prompt_needs_terminal() {
  run_register --no-login
  assert_rc 1
  assert_out_has "no terminal to ask for your OAuth client from"
  assert_out_has "--client-json"
}

test_env_vars_still_work() {
  export CLOUD_OPERATOR_CLIENT_ID="$FAKE_ID" CLOUD_OPERATOR_CLIENT_SECRET="$FAKE_SECRET"
  run_register --no-login
  assert_rc 0
  registered_with "\"clientId\":\"$FAKE_ID\""
  assert_no_secret
}

test_secret_option_refused() {
  run_register --client-secret "$FAKE_SECRET"
  assert_rc 1
  assert_out_has "don't pass the client secret as an option"
  assert_not_registered
  assert_no_secret
}

test_help() {
  run_register --help
  assert_rc 0
  assert_out_has "--client-json PATH"
  assert_log_lacks "claude"
}

# --- run ------------------------------------------------------------------------

printf 'bash %s, %s\n' "$BASH_VERSION" "$(uname -s)"
for t in \
  json_desktop json_equals_form json_any_name_with_spaces json_relative_path \
  json_tilde_path json_byte_order_mark json_dash_path json_trailing_newline \
  json_web_needs_port json_web_with_port \
  json_missing_file json_directory json_missing_value json_empty_value \
  json_no_secret json_bad_values json_not_client_file json_malformed json_empty_file \
  json_unreadable json_claude_fails json_python3 json_no_json_tool \
  login_needs_terminal prompt_needs_terminal env_vars_still_work \
  secret_option_refused help; do
  run_test "$t"
done
printf '\n%d passed, %d failed, %d skipped%s\n' "$PASS" "$FAIL" "$SKIP" "${FAILED_NAMES:+:$FAILED_NAMES}"
[ "$FAIL" -eq 0 ]
