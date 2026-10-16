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

# Registers the autocloud MCP server in Claude Code, at user scope, with your
# OAuth client and a 30-minute tool timeout, then signs you in with
# `claude mcp login autocloud`. /cloud-operator:setup asks you to run it in your
# own terminal, so the client secret stays out of the conversation:
#
#   bash <plugin folder>/scripts/register-mcp.sh
#
# Reads CLOUD_OPERATOR_CLIENT_ID / CLOUD_OPERATOR_CLIENT_SECRET from the environment, or
# asks for them (the secret is hidden). Run with --help for all options. Works
# with macOS's default bash 3.2.

set -euo pipefail

SERVER="autocloud"
SERVER_URL="https://geminicloudassist.googleapis.com/mcp/autocloud"
TIMEOUT_MS="1800000"

CLIENT_ID="${CLOUD_OPERATOR_CLIENT_ID:-}"
CLIENT_SECRET="${CLOUD_OPERATOR_CLIENT_SECRET:-}"
# Keep the secret out of the environment of the commands run below.
unset CLOUD_OPERATOR_CLIENT_SECRET
CALLBACK_PORT=""
LOGIN=1
SIGNED_IN=0

say() { printf '\n==> %s\n' "$*"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '    WARNING: %s\n' "$*" >&2; }
die() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Registers the autocloud MCP server in Claude Code with your OAuth client:
  1. asks for the OAuth client ID and secret (the secret isn't shown), unless
     CLOUD_OPERATOR_CLIENT_ID and CLOUD_OPERATOR_CLIENT_SECRET are set;
  2. replaces any user-scope autocloud server with one that uses your client
     and a 30-minute tool timeout. Claude Code keeps the secret in the system
     keychain (or its credentials file), not in its config;
  3. signs you in with claude mcp login autocloud: a browser window opens.

Create the OAuth client first, in the Google Cloud console: Google Auth
Platform > Clients > Create client > Desktop app. /cloud-operator:setup in Claude
Code walks you through it, and tells you when to run this script. Or use the
ID and secret of an existing client; for a Web application client, add
--callback-port with the port of its redirect URI.

Usage: register-mcp.sh [options]

  --no-login            Register only. Sign in later from Claude Code
                        (/mcp > autocloud > Authenticate) or with
                        claude mcp login autocloud.
  --callback-port PORT  Sign in on a fixed localhost port, for a Web
                        application client with http://localhost:PORT/callback
                        as an authorized redirect URI. Desktop app clients
                        don't need it.
  -h, --help            Show this help.

There's no option for the client secret, so it stays out of your shell
history.
EOF
}

# True if there's a terminal to ask from: this script's stdin. There's none
# when Claude runs the script, so it passes the environment variables instead.
can_prompt() { [ -t 0 ]; }

# Gets the terminal ready for answers: line input with echo, since a program
# that crashed earlier can leave it in raw mode, and nothing queued, since
# keystrokes typed ahead, or lines pasted together with the command, would
# otherwise be read as answers.
prepare_terminal() {
  local saved
  stty icanon echo icrnl 2>/dev/null || true
  saved="$(stty -g 2>/dev/null)" || return 0
  { stty -icanon min 0 time 0 && dd of=/dev/null bs=4096 count=1; } >/dev/null 2>&1 || true
  stty "$saved" 2>/dev/null || true
}

# ask VAR "Prompt" [secret]: reads VAR from the terminal unless it's already
# set, and asks again (up to three times) after an empty answer. A secret
# isn't shown as it's typed.
ask() {
  local var="$1" prompt="$2" secret="${3:-}" val="${!1:-}" tries=0 eof
  while [ -z "$val" ] && [ "$tries" -lt 3 ] && can_prompt; do
    tries=$((tries + 1))
    eof=0
    printf '%s: ' "$prompt" >&2
    if [ -n "$secret" ]; then
      IFS= read -r -s val || eof=1
      printf '\n' >&2
    else
      IFS= read -r val || eof=1
    fi
    # Drop whitespace that copy-paste tends to add.
    val="$(printf '%s' "$val" | tr -d '[:space:]')"
    if [ "$eof" -eq 1 ]; then break; fi
  done
  val="$(printf '%s' "$val" | tr -d '[:space:]')"
  printf -v "$var" '%s' "$val"
}

need_value() { # need_value OPTION NUM_REMAINING_ARGS
  if [ "$2" -lt 2 ]; then die "$1 needs a value (see --help)"; fi
}

set_callback_port() { # set_callback_port PORT
  local port_re='^[1-9][0-9]{0,4}$'
  [[ "$1" =~ $port_re ]] && [ "$1" -le 65535 ] ||
    die "--callback-port needs a port number from 1 to 65535"
  CALLBACK_PORT="$1"
}

ask_client() {
  if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    can_prompt ||
      die "no terminal to ask for your OAuth client from: run this script in your terminal, or set CLOUD_OPERATOR_CLIENT_ID and CLOUD_OPERATOR_CLIENT_SECRET"
    prepare_terminal
    say "Your OAuth client"
    info "Your OAuth client from the Google Cloud console (Google Auth Platform > Clients)."
  fi
  ask CLIENT_ID "OAuth client ID"
  [ -n "$CLIENT_ID" ] || die "a client ID is needed: enter it at the prompt or set CLOUD_OPERATOR_CLIENT_ID"
  local id_re='^[A-Za-z0-9._-]+$'
  [[ "$CLIENT_ID" =~ $id_re ]] || die "the client ID '$CLIENT_ID' contains unsupported characters"
  case "$CLIENT_ID" in
    *.apps.googleusercontent.com) ;;
    *) warn "'$CLIENT_ID' doesn't end in .apps.googleusercontent.com; check that it's the client ID" ;;
  esac
  ask CLIENT_SECRET "OAuth client secret (not shown)" secret
  [ -n "$CLIENT_SECRET" ] || die "a client secret is needed: enter it at the prompt or set CLOUD_OPERATOR_CLIENT_SECRET"
  info "client ID: $CLIENT_ID"
}

register_server() {
  local oauth json
  oauth="\"clientId\":\"$CLIENT_ID\""
  if [ -n "$CALLBACK_PORT" ]; then oauth="$oauth,\"callbackPort\":$CALLBACK_PORT"; fi
  json="{\"type\":\"http\",\"url\":\"$SERVER_URL\",\"timeout\":$TIMEOUT_MS,\"oauth\":{$oauth}}"
  say "Registering the autocloud MCP server"
  # A clean start: sign out of an earlier autocloud server, then remove it.
  claude mcp logout "$SERVER" >/dev/null 2>&1 || true
  claude mcp remove "$SERVER" -s user >/dev/null 2>&1 || true
  # Claude Code reads the secret from MCP_CLIENT_SECRET and keeps it in the
  # system keychain (or its credentials file), not in its config.
  if ! MCP_CLIENT_SECRET="$CLIENT_SECRET" claude mcp add-json -s user "$SERVER" "$json" --client-secret; then
    CLIENT_SECRET=""
    die "couldn't register the server. If Claude Code doesn't know --client-secret, update it (claude update) and re-run."
  fi
  CLIENT_SECRET=""
  info "registered at user scope, with a 30-minute tool timeout"
}

sign_in() {
  local term=""
  if [ "$LOGIN" -eq 0 ]; then
    info "sign in later: /mcp > autocloud > Authenticate in Claude Code, or claude mcp login autocloud"
    return 0
  fi
  if ! claude mcp login --help >/dev/null 2>&1; then
    info "sign in from Claude Code: /mcp > autocloud > Authenticate"
    return 0
  fi
  # The terminal to sign in from. Claude Code can't read from /dev/tty on
  # macOS (kqueue rejects it with EINVAL), so it gets this script's stdin when
  # that's the terminal, or else the terminal's real device.
  if [ -t 0 ]; then
    term="stdin"
  elif ! term="$(tty <&2 2>/dev/null)" || [ ! -r "$term" ]; then
    term=""
  fi
  if [ -z "$term" ]; then
    info "no terminal to sign in from; sign in from Claude Code (/mcp > autocloud > Authenticate), or run: claude mcp login autocloud"
    return 0
  fi
  say "Signing in"
  info "A browser window opens. Sign in with the Google account that owns your operator agent."
  if [ "$term" = "stdin" ]; then
    if claude mcp login "$SERVER"; then SIGNED_IN=1; fi
  elif claude mcp login "$SERVER" <"$term"; then
    SIGNED_IN=1
  fi
  if [ "$SIGNED_IN" -eq 0 ]; then
    warn "sign-in didn't finish; retry with: claude mcp login autocloud (or /mcp > autocloud > Authenticate in Claude Code)"
  fi
}

show_status() {
  local details
  details="$(claude mcp get "$SERVER" 2>&1 || true)"
  printf '\n'
  printf '%s\n' "$details" | sed 's/^/    /'
  case "$details" in
    *"Scope: Local"* | *"Scope: Project"*)
      warn "another 'autocloud' MCP server entry for this folder hides the new one; remove it with: claude mcp remove autocloud -s local (or -s project)"
      ;;
  esac
}

print_next_steps() {
  local mcp_step="Run /mcp and check that autocloud is connected."
  if [ "$SIGNED_IN" -eq 0 ]; then
    mcp_step="Sign in: run /mcp, select autocloud and choose Authenticate."
  fi
  cat <<EOF

Done. Next:
  1. Restart Claude Code so it loads the server: exit it, then run claude -c
     in the same folder to continue your conversation.
  2. $mcp_step
  3. Tell Claude you're connected: /cloud-operator:setup goes on with your
     operator project and preferences.
EOF
}

main() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --no-login) LOGIN=0; shift ;;
      --callback-port) need_value "$1" $#; set_callback_port "$2"; shift 2 ;;
      --callback-port=*) set_callback_port "${1#*=}"; shift ;;
      --client-secret | --client-secret=*)
        die "don't pass the client secret as an option: enter it at the prompt or set CLOUD_OPERATOR_CLIENT_SECRET" ;;
      -h | --help) usage; exit 0 ;;
      *) die "unknown option: $1 (see --help)" ;;
    esac
  done
  command -v claude >/dev/null 2>&1 ||
    die "Claude Code isn't installed or isn't on your PATH. Install it, then re-run."

  ask_client
  register_server
  sign_in
  show_status
  print_next_steps
}

main "$@"
