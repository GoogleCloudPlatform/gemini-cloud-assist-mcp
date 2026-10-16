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

# Installs the Cloud Operator plugin for Codex (desktop + CLI) from this
# repository checkout. It assembles the plugin as described in
# plugins/cloud-operator/README.md (skills/autocloud-operator first, then this
# folder on top), registers it in your personal Codex marketplace and installs it with
# the Codex CLI. The MCP server and OAuth sign-in are set up afterwards by the
# plugin's setup skill.

set -euo pipefail

usage() {
  cat <<'EOF'
Installs the Cloud Operator plugin for Codex (desktop app and CLI) from this
repository checkout. It:
  1. assembles the plugin in ~/.codex/plugins/cloud-operator
  2. registers it in ~/.agents/plugins/marketplace.json
  3. installs it with the Codex CLI

Then restart Codex, type @cloud-operator and ask "Set up Cloud Operator".

Usage: install.sh [options]

Options:
  -h, --help  Show this help.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
done

CODEX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPERATOR_SKILL="$CODEX_DIR/../../../skills/autocloud-operator"
PLUGIN_DIR="$HOME/.codex/plugins/cloud-operator"
MARKET="$HOME/.agents/plugins/marketplace.json"
CLI="/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"

say() { printf '\n==> %s\n' "$*"; }
die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

[ -f "$CODEX_DIR/.codex-plugin/plugin.json" ] && [ -f "$OPERATOR_SKILL/SKILL.md" ] ||
  die "run this script from a checkout of the repository (plugins/cloud-operator/codex/install.sh)"
command -v perl >/dev/null || die "perl is required"
if [ ! -x "$CLI" ]; then
  CLI="$(command -v codex || true)"
  # Only accept OpenAI's Codex CLI (it has the "plugin" command).
  if [ -n "$CLI" ] && ! "$CLI" plugin --help >/dev/null 2>&1; then CLI=""; fi
fi

say "1/3 Assembling the plugin in $PLUGIN_DIR"
mkdir -p "$HOME/.codex/plugins"
if [ -d "$PLUGIN_DIR" ]; then
  mkdir -p "$HOME/.codex/cloud-operator-backups"
  mv "$PLUGIN_DIR" "$HOME/.codex/cloud-operator-backups/cloud-operator.$(date +%Y%m%d-%H%M%S).$$"
  # Keep only the two most recent backups.
  ls -1dt "$HOME/.codex/cloud-operator-backups"/cloud-operator.* | tail -n +3 | while read -r d; do rm -rf "$d"; done
  echo "previous version moved to ~/.codex/cloud-operator-backups"
fi
mkdir -p "$PLUGIN_DIR/skills"
cp -R "$OPERATOR_SKILL" "$PLUGIN_DIR/skills/autocloud-operator"
(cd "$CODEX_DIR" && tar -cf - --exclude ./install.sh --exclude ./README.md .) | (cd "$PLUGIN_DIR" && tar -xf -)
echo "skills: $(ls "$PLUGIN_DIR/skills" | tr '\n' ' ')"

say "2/3 Registering the plugin in $MARKET"
mkdir -p "$(dirname "$MARKET")"
# Edit the marketplace as JSON (create it if missing): add the cloud-operator
# entry to the top-level "plugins" list unless it's already there. The previous
# file is kept as marketplace.json.bak.
MARKET="$MARKET" perl -MJSON::PP -e '
  my $json = JSON::PP->new->utf8->pretty->canonical;
  my $d = { name => "personal", interface => { displayName => "Personal" }, plugins => [] };
  my $raw;
  if (-s $ENV{MARKET}) {
    open my $in, "<", $ENV{MARKET} or die "cannot read $ENV{MARKET}: $!\n";
    { local $/; $raw = <$in>; }
    $d = eval { $json->decode($raw) } or die "$ENV{MARKET} is not valid JSON; fix or remove it\n";
  }
  ref $d eq "HASH" or die "$ENV{MARKET}: expected a JSON object\n";
  $d->{plugins} //= [];
  ref $d->{plugins} eq "ARRAY" or die "$ENV{MARKET}: \"plugins\" is not a list\n";
  if (grep { ref $_ eq "HASH" && ($_->{name} // "") eq "cloud-operator" } @{$d->{plugins}}) {
    print "already registered\n"; exit 0;
  }
  unshift @{$d->{plugins}}, {
    name => "cloud-operator",
    source => { source => "local", path => "./.codex/plugins/cloud-operator" },
    policy => { installation => "AVAILABLE", authentication => "ON_INSTALL" },
    category => "Productivity",
  };
  if (defined $raw) {
    open my $bak, ">", "$ENV{MARKET}.bak" or die "cannot write $ENV{MARKET}.bak: $!\n";
    print $bak $raw;
  }
  open my $out, ">", $ENV{MARKET} or die "cannot write $ENV{MARKET}: $!\n";
  print $out $json->encode($d);
  print "added cloud-operator\n";
' || die "couldn't update $MARKET"

if [ -z "${CLI:-}" ]; then
  say "Codex CLI not found. Finish in Codex desktop: Plugins > Personal > Cloud Operator > Install."
  exit 0
fi

say "3/3 Installing the plugin in Codex"
MKT="$("$CLI" plugin marketplace list 2>/dev/null | awk -v h="$HOME" '$2==h {print $1; exit}')"
MKT="${MKT:-personal}"
"$CLI" plugin remove "cloud-operator@$MKT" >/dev/null 2>&1 || true
"$CLI" plugin add "cloud-operator@$MKT"

cat <<EOF

Done. Next, in the Codex desktop app or the Codex CLI (setup is the same in
both, and once it's done, both use it):
  1. Restart Codex so it loads the plugin: quit (Cmd+Q) and reopen the
     desktop app, or start a new CLI session.
  2. Type @cloud-operator and ask "Set up Cloud Operator" (the desktop app
     may also offer to run setup on its own). It uses an existing OAuth
     client or helps you create one, registers the autocloud MCP server,
     then asks for your operator project and agent (helping you create the
     agent), verifies it and sets up your preferences.
Terminal: alias codex="$CLI"
EOF
