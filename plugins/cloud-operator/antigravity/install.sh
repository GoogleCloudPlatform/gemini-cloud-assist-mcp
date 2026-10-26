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

# Installs the Cloud Operator plugin for Antigravity:
#
#   curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/main/plugins/cloud-operator/antigravity/install.sh | bash
#
# or, from a checkout of this repository (installs that checkout):
#
#   bash plugins/cloud-operator/antigravity/install.sh
#
# It puts the plugin together as plugins/cloud-operator/README.md describes
# (skills/autocloud-operator first, then shared/admin-setup, then this folder
# on top), checks it with agy plugin validate
# and installs it with agy plugin install (without agy, it copies it into
# Antigravity's plugin folder instead). It doesn't ask for anything:
# Antigravity signs in to the MCP server with your Application Default
# Credentials, and the plugin's /cloud-operator:setup skill checks the connection
# afterwards. Run with --help for all options. Works with macOS's default
# bash 3.2.

set -euo pipefail

PLUGIN="cloud-operator"
GITHUB_REPO="GoogleCloudPlatform/gemini-cloud-assist-mcp"
STAGE="${CLOUD_OPERATOR_HOME:-$HOME/.cloud-operator}/antigravity-plugin"
PREFS="$HOME/.config/cloud-operator/preferences.md"
CONFIG_DIR="$HOME/.gemini/config"

SOURCE="${CLOUD_OPERATOR_SOURCE:-}"
PLUGIN_SRC=""
REF="${CLOUD_OPERATOR_REF:-main}"
PACKAGE_ONLY=0
DOWNLOAD_DIR=""
AGY=""

say() { printf '\n==> %s\n' "$*"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '    WARNING: %s\n' "$*" >&2; }
die() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Installs the Cloud Operator plugin for Antigravity:
  1. checks for Antigravity's agy CLI (optional, see below) and Application
     Default Credentials (a warning only: the plugin needs ADC to reach the
     operator);
  2. puts the plugin together: the autocloud-operator skill from skills/ at
     the repository root, the admin-setup skill from plugins/cloud-operator/shared,
     then the Antigravity files from plugins/cloud-operator/antigravity, and
     checks it with agy plugin validate;
  3. installs it with agy plugin install, replacing an earlier version of it.

Without the agy CLI (for example, with only the Antigravity app), it skips the
validation and copies the plugin into ~/.gemini/config/plugins/cloud-operator,
where Antigravity looks for plugins.

It doesn't ask for anything. Afterwards, restart Antigravity and run
/cloud-operator:setup: it checks your project, ADC and quota project, and makes a
test call to the operator.

Usage: install.sh [options]

  --source DIR      Repository checkout to install. Default: the checkout this
                    script is in; when piped from curl, a download of
                    GoogleCloudPlatform/gemini-cloud-assist-mcp from GitHub.
                    Env: CLOUD_OPERATOR_SOURCE
  --ref REF         Branch or tag to download from GitHub. Default: main.
                    Env: CLOUD_OPERATOR_REF
  --package-only    Only put the plugin together and print where it is.
  -h, --help        Show this help.

The assembled plugin lives in ~/.cloud-operator/antigravity-plugin (set
CLOUD_OPERATOR_HOME to change); the installed copy is in
~/.gemini/config/plugins/cloud-operator. To remove the plugin, run
agy plugin uninstall cloud-operator, or without agy, delete that folder.
EOF
}

need_value() { # need_value OPTION NUM_REMAINING_ARGS
  if [ "$2" -lt 2 ]; then die "$1 needs a value (see --help)"; fi
}

# Sets AGY to Antigravity's CLI: agy on PATH, or where its installer puts it.
find_agy() {
  AGY="$(command -v agy 2>/dev/null || true)"
  if [ -z "$AGY" ] && [ -x "$HOME/.local/bin/agy" ]; then AGY="$HOME/.local/bin/agy"; fi
  [ -n "$AGY" ]
}

# Downloads the repository from GitHub and sets SOURCE to the unpacked tree.
download_source() {
  command -v curl >/dev/null 2>&1 || die "curl is needed to download the plugin"
  command -v tar >/dev/null 2>&1 || die "tar is needed to unpack the plugin"
  local url="${CLOUD_OPERATOR_ARCHIVE_URL:-https://github.com/$GITHUB_REPO/archive/$REF.tar.gz}"
  DOWNLOAD_DIR="$(mktemp -d)"
  trap 'rm -rf "$DOWNLOAD_DIR"' EXIT
  info "downloading $url"
  curl -fsSL "$url" | tar -xzf - -C "$DOWNLOAD_DIR" || die "couldn't download or unpack $url"
  SOURCE="$(find "$DOWNLOAD_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  [ -n "$SOURCE" ] || die "the download from $url was empty"
}

# Puts the plugin together from plugin folder $1 into $STAGE: the
# autocloud-operator skill from skills/ at the repository root first, then the
# admin-setup skill from plugins/cloud-operator/shared, then the folder itself
# on top (minus this script).
assemble_plugin() {
  local dir="$1" skill="$1/../../../skills/autocloud-operator" admin="$1/../shared/admin-setup" tmp="$STAGE.tmp.$$"
  [ -f "$dir/plugin.json" ] || die "$dir doesn't contain the Antigravity plugin (no plugin.json)"
  [ -f "$skill/SKILL.md" ] ||
    die "$dir isn't in a checkout of this repository (no skills/autocloud-operator at the root)"
  [ -f "$admin/SKILL.md" ] ||
    die "$dir isn't in a checkout of this repository (no plugins/cloud-operator/shared/admin-setup)"
  rm -rf "$tmp"
  mkdir -p "$tmp/skills"
  cp -R "$skill" "$tmp/skills/autocloud-operator"
  cp -R "$admin" "$tmp/skills/admin-setup"
  (cd "$dir" && tar -cf - --exclude ./install.sh --exclude __pycache__ .) | (cd "$tmp" && tar -xf -)
  rm -rf "$STAGE"
  mkdir -p "$(dirname "$STAGE")"
  mv "$tmp" "$STAGE"
}

check_prerequisites() {
  local adc
  say "1/3 Checking prerequisites"
  if find_agy; then
    info "agy $("$AGY" --version 2>/dev/null | head -n 1)"
  else
    warn "Antigravity's agy CLI isn't on your PATH: the plugin is copied into $CONFIG_DIR/plugins without being validated"
  fi
  adc="${GOOGLE_APPLICATION_CREDENTIALS:-${CLOUDSDK_CONFIG:-$HOME/.config/gcloud}/application_default_credentials.json}"
  if [ ! -f "$adc" ]; then
    warn "no Application Default Credentials: the plugin can't reach the operator until you run gcloud auth application-default login"
  elif ! grep -q '"quota_project_id"' "$adc"; then
    warn "your Application Default Credentials have no quota project; run gcloud auth application-default set-quota-project <project-id>"
  else
    info "Application Default Credentials: $adc"
  fi
}

install_plugin() {
  say "3/3 Installing the plugin"
  if [ -n "$AGY" ]; then
    # agy replaces the installed copy, so re-running the script picks up the
    # new files and keeps the plugin's on/off setting.
    "$AGY" plugin install "$STAGE"
  else
    rm -rf "$CONFIG_DIR/plugins/$PLUGIN"
    mkdir -p "$CONFIG_DIR/plugins"
    cp -R "$STAGE" "$CONFIG_DIR/plugins/$PLUGIN"
    info "copied it to $CONFIG_DIR/plugins/$PLUGIN"
  fi
}

print_next_steps() {
  cat <<EOF

Done. Next, in Antigravity:

  1. Restart it (it loads plugins on startup), and turn Cloud Operator on in /plugin
     if it shows as off.
  2. Run /cloud-operator:setup: it checks your project, Application Default
     Credentials and quota project, and makes a test call to the operator.
  3. Optionally run /cloud-operator:preferences to save your standing GCP
     preferences, which go with the first request of every operator session.
     They're kept in $PREFS.

Then ask a Google Cloud question. To update the plugin, re-run this script.
EOF
}

main() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --source) need_value "$1" $#; SOURCE="$2"; shift 2 ;;
      --source=*) SOURCE="${1#*=}"; shift ;;
      --ref) need_value "$1" $#; REF="$2"; shift 2 ;;
      --ref=*) REF="${1#*=}"; shift ;;
      --package-only) PACKAGE_ONLY=1; shift ;;
      -h | --help) usage; exit 0 ;;
      *) die "unknown option: $1 (see --help)" ;;
    esac
  done

  # When run from a file in a checkout of this repository, install that
  # checkout.
  if [ -z "$SOURCE" ]; then
    local script_path="${BASH_SOURCE[0]:-}"
    if [ -n "$script_path" ] && [ -f "$script_path" ] && [ -f "$(dirname "$script_path")/plugin.json" ]; then
      PLUGIN_SRC="$(cd "$(dirname "$script_path")" && pwd)"
    fi
  fi

  if [ "$PACKAGE_ONLY" -eq 0 ]; then
    check_prerequisites
  fi

  say "2/3 Putting the plugin together"
  if [ -z "$PLUGIN_SRC" ]; then
    if [ -z "$SOURCE" ]; then
      download_source
    else
      [ -d "$SOURCE" ] || die "--source $SOURCE isn't a directory"
    fi
    PLUGIN_SRC="$SOURCE/plugins/cloud-operator/antigravity"
  fi
  info "from: $PLUGIN_SRC"
  if [ -z "$DOWNLOAD_DIR" ] && [ "$REF" != main ]; then
    warn "--ref applies only to downloads from GitHub, so it's ignored for $PLUGIN_SRC"
  fi
  assemble_plugin "$PLUGIN_SRC"
  info "assembled in $STAGE"

  if [ "$PACKAGE_ONLY" -eq 1 ]; then
    cat <<EOF

Assembled only. To check it:
  agy plugin validate "$STAGE"
To install it:
  agy plugin install "$STAGE"
EOF
    exit 0
  fi

  if [ -n "$AGY" ]; then
    local validation
    if ! validation="$("$AGY" plugin validate "$STAGE" 2>&1)"; then
      printf '%s\n' "$validation" >&2
      die "the assembled plugin didn't pass 'agy plugin validate'"
    fi
  fi

  install_plugin
  print_next_steps
}

# Everything runs from here, so a partly downloaded script does nothing.
main "$@"
