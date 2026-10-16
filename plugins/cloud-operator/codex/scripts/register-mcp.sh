#!/bin/bash
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

# Registers the autocloud MCP server in Codex (~/.codex/config.toml) with
# your OAuth client and the plugin's settings (cloud-platform scope,
# 30-minute tool timeout, only the operator tools enabled), then signs in with
# `codex mcp login`. Run it in your own terminal so
# the client secret stays out of the conversation. Used by the setup skill.
#
# Reads CLOUD_OPERATOR_CLIENT_ID / CLOUD_OPERATOR_CLIENT_SECRET from the
# environment, or asks for them (the secret is hidden).

set -euo pipefail

usage() {
  cat <<'EOF'
Registers the autocloud MCP server in Codex (~/.codex/config.toml) with your
OAuth client, the cloud-platform scope, a 30-minute tool timeout and only the
operator tools enabled, then signs you in with `codex mcp login`.

Use a new Desktop app client from the Google Cloud console (Google Auth
Platform > Clients > Create client > Desktop app), or the ID and secret of an
existing OAuth client. For a Web application client, add --callback-port with
the port of its redirect URI. The setup skill in Codex walks you through it.

Usage: register-mcp.sh [options]

Options:
  --callback-port PORT  Fixed localhost port for the sign-in callback (needed
                        for Web application clients).
  --no-login            Register only; sign in later with `codex mcp login autocloud`.
  -h, --help            Show this help.

Environment: CLOUD_OPERATOR_CLIENT_ID and CLOUD_OPERATOR_CLIENT_SECRET, if set,
are used instead of asking.
EOF
}

CALLBACK_PORT=""
LOGIN=1
while [ $# -gt 0 ]; do
  case "$1" in
    --callback-port)
      [ $# -ge 2 ] || { echo "ERROR: --callback-port needs a port" >&2; exit 2; }
      CALLBACK_PORT="$2"; shift 2 ;;
    --callback-port=*) CALLBACK_PORT="${1#*=}"; shift ;;
    --no-login) LOGIN=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
done
case "$CALLBACK_PORT" in
  "") ;;
  *[!0-9]*) echo "ERROR: --callback-port must be a number, got: $CALLBACK_PORT" >&2; exit 2 ;;
  *) [ "$CALLBACK_PORT" -ge 1 ] && [ "$CALLBACK_PORT" -le 65535 ] ||
       { echo "ERROR: --callback-port must be between 1 and 65535" >&2; exit 2; } ;;
esac
# New files (config.toml, its backups) are readable only by the user: they
# hold the client secret.
umask 077

NAME="autocloud"
URL="https://geminicloudassist.googleapis.com/mcp/autocloud"
CONFIG="${CODEX_HOME:-$HOME/.codex}/config.toml"
CLI="/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"

die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

if [ ! -x "$CLI" ]; then
  CLI="$(command -v codex || true)"
  # Only accept OpenAI's Codex CLI (it has the "mcp" command).
  if [ -n "$CLI" ] && ! "$CLI" mcp --help >/dev/null 2>&1; then CLI=""; fi
fi
[ -n "${CLI:-}" ] || die "Codex CLI not found (it ships with the ChatGPT desktop app)"
"$CLI" mcp add --help 2>/dev/null | grep -q -e '--oauth-client-secret' ||
  die "this Codex version can't store an OAuth client secret; update the ChatGPT app"
command -v perl >/dev/null || die "perl is required"

CLIENT_ID="${CLOUD_OPERATOR_CLIENT_ID:-}"
if [ -z "$CLIENT_ID" ]; then
  echo "Your Desktop app client from the Google Cloud console (Google Auth Platform > Clients), or an existing OAuth client."
  read -r -p "OAuth client ID: " CLIENT_ID
fi
CLIENT_ID="$(printf '%s' "$CLIENT_ID" | tr -d '[:space:]')"
[ -n "$CLIENT_ID" ] || die "client ID is required"

CLIENT_SECRET="${CLOUD_OPERATOR_CLIENT_SECRET:-}"
unset CLOUD_OPERATOR_CLIENT_SECRET
if [ -z "$CLIENT_SECRET" ]; then read -r -s -p "OAuth client secret (hidden): " CLIENT_SECRET; echo; fi
[ -n "$CLIENT_SECRET" ] || die "client secret is required"

# Write the server entry ourselves instead of using `codex mcp add`: that
# command starts the sign-in immediately with only server-discovered scopes,
# and Google rejects a request without a scope. `codex mcp login` uses the
# scopes configured here.
echo "Registering the $NAME MCP server in $CONFIG..."
"$CLI" mcp remove "$NAME" >/dev/null 2>&1 || true
mkdir -p "$(dirname "$CONFIG")"
touch "$CONFIG"
# Back up config.toml (mode 600: older backups hold the previous secret) and
# keep only the two newest backups.
BACKUP="$CONFIG.bak.cloud-operator.$(date +%Y%m%d-%H%M%S)"
cp "$CONFIG" "$BACKUP"
chmod 600 "$BACKUP"
ls -1t "$CONFIG".bak.cloud-operator.* 2>/dev/null | tail -n +3 | while read -r f; do rm -f "$f"; done
# Fallback in case `codex mcp remove` left anything: drop the
# [mcp_servers.autocloud] table and its subtables, line by line. Comments and
# blank lines right before the next table belong to that table and are kept.
NAME="$NAME" perl -i -ne '
  BEGIN { $n = quotemeta $ENV{NAME}; $skip = 0; @held = () }
  if (/^\s*\[/) {
    print @held unless /^\s*\[\s*mcp_servers\s*\.\s*"?$n"?\s*(?:[.\]])/;
    @held = ();
    $skip = /^\s*\[\s*mcp_servers\s*\.\s*"?$n"?\s*(?:[.\]])/ ? 1 : 0;
  }
  if (!$skip) { print; next }
  if (/^\s*(?:#.*)?$/) { push @held, $_ } else { @held = () }
' "$CONFIG"
toml_escape() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }
{
  printf '\n[mcp_servers.%s]\n' "$NAME"
  printf 'url = "%s"\n' "$URL"
  printf 'scopes = ["https://www.googleapis.com/auth/cloud-platform"]\n'
  printf 'tool_timeout_sec = 1800\n'
  printf 'startup_timeout_sec = 30\n'
  printf 'enabled_tools = ["ask_cloud_operator", "search_operator_sessions", "fetch_operator_session"]\n'
  printf '\n[mcp_servers.%s.oauth]\n' "$NAME"
  printf 'client_id = "%s"\n' "$(toml_escape "$CLIENT_ID")"
  printf 'client_secret = "%s"\n' "$(toml_escape "$CLIENT_SECRET")"
  if [ -n "$CALLBACK_PORT" ]; then printf 'callback_port = %s\n' "$CALLBACK_PORT"; fi
} >> "$CONFIG"
unset CLIENT_SECRET
chmod 600 "$CONFIG"
# Tells the setup skill to resume at its agent check after the Codex restart.
mkdir -p "$HOME/.config/cloud-operator" && touch "$HOME/.config/cloud-operator/setup-pending"

if [ "$LOGIN" = 1 ]; then
  echo "Signing in (a browser window opens)..."
  "$CLI" mcp login "$NAME" --scopes "https://www.googleapis.com/auth/cloud-platform" ||
    echo "warning: sign-in didn't complete; retry with: \"$CLI\" mcp login $NAME"
else
  echo "Skipping sign-in (--no-login); sign in later with: \"$CLI\" mcp login $NAME"
fi

echo
"$CLI" mcp get "$NAME" 2>/dev/null || true
cat <<EOF

The $NAME MCP server is registered in $CONFIG (readable only by you; it holds the client secret).
Next: quit and reopen Codex (or start a new CLI session). In a new chat, type @cloud-operator, pick the
Cloud Operator plugin and say "continue Cloud Operator setup" to choose your operator project and agent (or create
the agent) and set up your preferences.
If sign-in didn't finish: "$CLI" mcp login $NAME
EOF
