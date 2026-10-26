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

# Installs the Cloud Operator plugin for Claude Code:
#
#   curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/main/plugins/cloud-operator/claude/install.sh | bash
#
# or, from a checkout of this repository (installs that checkout):
#
#   bash plugins/cloud-operator/claude/install.sh
#
# It puts the plugin together as plugins/cloud-operator/README.md describes
# (skills/autocloud-operator first, then shared/admin-setup, then this folder
# on top), writes its marketplace manifest
# and installs it, replacing the plugin at the root of this repository. It
# also updates the permissions in Claude Code's user settings, so Claude reads
# your preferences in ~/.config/cloud-operator without asking. It doesn't ask for
# anything: the MCP server and OAuth sign-in are set up afterwards by the
# plugin's /cloud-operator:setup command. Run with --help for all options. Works
# with macOS's default bash 3.2.

set -euo pipefail

PLUGIN="cloud-operator@cloud-operator-marketplace"
MARKETPLACE="cloud-operator-marketplace"
SERVER="autocloud"
GITHUB_REPO="GoogleCloudPlatform/gemini-cloud-assist-mcp"
STAGE="${CLOUD_OPERATOR_HOME:-$HOME/.cloud-operator}/claude-plugin"
PREFS="$HOME/.config/cloud-operator/preferences.md"
# Permission rule the installer adds to permissions.allow in Claude Code's user
# settings, and --uninstall takes out again: reading ~/.config/cloud-operator, so
# Claude reads your preferences there without asking.
SETTINGS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"
ALLOW_RULE="Read(~/.config/cloud-operator/**)"
# The plugin this one replaces: the plugin at the root of this repository. It's
# removed on install, because its skills and tools would compete with this
# plugin's for the same requests.
OLD_PLUGINS="gemini-cloud-assist-mcp@gemini-cloud-assist-mcp"
OLD_MARKETPLACE="gemini-cloud-assist-mcp"

SOURCE="${CLOUD_OPERATOR_SOURCE:-}"
REF="${CLOUD_OPERATOR_REF:-main}"
UNINSTALL=0
PACKAGE_ONLY=0
DOWNLOAD_DIR=""

say() { printf '\n==> %s\n' "$*"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '    WARNING: %s\n' "$*" >&2; }
die() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Installs the Cloud Operator plugin for Claude Code:
  1. checks that Claude Code is installed;
  2. puts the plugin together: the autocloud-operator skill from skills/ at
     the repository root, the admin-setup skill from plugins/cloud-operator/shared,
     then the Claude Code files from plugins/cloud-operator/claude, plus its
     marketplace manifest;
  3. installs it in Claude Code, replacing an earlier version of it and the
     plugin it supersedes: gemini-cloud-assist-mcp, from the root of this
     repository;
  4. updates the permissions in Claude Code's user settings,
     ~/.claude/settings.json, rewriting it pretty-printed with its keys
     sorted, and keeping the previous file as settings.json.bak: it lets
     Claude read your preferences in ~/.config/cloud-operator without asking, by
     adding Read(~/.config/cloud-operator/**) to permissions.allow.

It doesn't ask for anything. Afterwards, run /cloud-operator:setup in Claude Code:
it walks you through creating your OAuth client, has you register the
autocloud MCP server with it (the plugin's scripts/register-mcp.sh, run in
your terminal), and saves your preferences.

Usage: install.sh [options]

  --source DIR      Repository checkout to install. Default: the checkout this
                    script is in; when piped from curl, a download of
                    GoogleCloudPlatform/gemini-cloud-assist-mcp from GitHub.
                    Env: CLOUD_OPERATOR_SOURCE
  --ref REF         Branch or tag to download from GitHub. Default: main.
                    Env: CLOUD_OPERATOR_REF
  --package-only    Only put the plugin together and print where it is.
  --uninstall       Remove the plugin, its MCP server, your sign-in and the
                    permission rule it added, then exit.
  -h, --help        Show this help.

The assembled plugin and its local marketplace live in
~/.cloud-operator/claude-plugin (set CLOUD_OPERATOR_HOME to change).
EOF
}

need_value() { # need_value OPTION NUM_REMAINING_ARGS
  if [ "$2" -lt 2 ]; then die "$1 needs a value (see --help)"; fi
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

# Writes the marketplace manifest that makes directory $1 a one-plugin
# marketplace that Claude Code installs from. The claude/ folder doesn't ship
# one, so it can't be installed without the shared files.
write_marketplace() {
  cat >"$1/.claude-plugin/marketplace.json" <<EOF
{
  "name": "$MARKETPLACE",
  "owner": {
    "name": "Google LLC"
  },
  "description": "Cloud Operator: the Gemini Cloud Assist operator agent for Claude Code",
  "plugins": [
    {
      "name": "${PLUGIN%@*}",
      "source": "./",
      "description": "Operate GCP via the Gemini Cloud Assist cloud operator MCP tool."
    }
  ]
}
EOF
}

# Puts the plugin together from checkout $1 into $STAGE: the
# autocloud-operator skill from skills/ at the repository root first, then the
# admin-setup skill from plugins/cloud-operator/shared, then the claude/ folder
# on top (minus this script and the tests), and then the marketplace manifest.
assemble_plugin() {
  local src="$1/plugins/cloud-operator" skill="$1/skills/autocloud-operator" tmp="$STAGE.tmp.$$"
  [ -f "$skill/SKILL.md" ] && [ -f "$src/claude/.claude-plugin/plugin.json" ] && [ -f "$src/shared/admin-setup/SKILL.md" ] ||
    die "$1 doesn't contain skills/autocloud-operator, plugins/cloud-operator/claude and plugins/cloud-operator/shared/admin-setup"
  rm -rf "$tmp"
  mkdir -p "$tmp/skills"
  cp -R "$skill" "$tmp/skills/autocloud-operator"
  cp -R "$src/shared/admin-setup" "$tmp/skills/admin-setup"
  (cd "$src/claude" && tar -cf - --exclude ./install.sh --exclude ./tests .) | (cd "$tmp" && tar -xf -)
  write_marketplace "$tmp"
  rm -rf "$STAGE"
  mkdir -p "$(dirname "$STAGE")"
  mv "$tmp" "$STAGE"
}

# Prints the permission rule to add by hand when the installer can't.
print_permission_rules() {
  info "To set it yourself, add this rule under \"permissions\" in $SETTINGS:"
  info "  \"allow\":"
  info "    \"$ALLOW_RULE\""
}

# Adds the plugin's permission rule to Claude Code's user settings (add), or
# takes it out again (remove): reading ~/.config/cloud-operator in
# permissions.allow. Everything else in the file is kept, with its keys
# sorted, and the previous file is saved as settings.json.bak. A file that
# isn't valid JSON is left alone. Uses perl, which macOS ships, so the
# installer needs no Python.
update_permissions() { # update_permissions add|remove
  local mode="$1" out
  if ! command -v perl >/dev/null 2>&1 || ! perl -MJSON::PP -e 1 >/dev/null 2>&1; then
    if [ "$mode" = add ]; then
      warn "perl (with JSON::PP) isn't available, so the permissions in $SETTINGS weren't updated"
      print_permission_rules
    else
      warn "perl (with JSON::PP) isn't available, so the Cloud Operator rule wasn't removed from the permissions in $SETTINGS"
    fi
    return 0
  fi
  if [ "$mode" = add ]; then mkdir -p "$(dirname "$SETTINGS")"; fi
  if out="$(MODE="$mode" FILE="$SETTINGS" ALLOW="$ALLOW_RULE" perl -MJSON::PP -MCwd=abs_path -e '
    use strict;
    use warnings;
    my ($mode, $file) = ($ENV{MODE}, $ENV{FILE});
    my %rules = (allow => [split " ", $ENV{ALLOW}]);
    # Write through a symlink, such as one into a dotfiles repository.
    my $path = -l $file ? abs_path($file) : $file;
    die "it is a broken symlink, so it was left unchanged\n" unless defined $path;
    my $json = JSON::PP->new->utf8->pretty->space_before(0)->canonical->indent_length(2);
    my ($raw, $data) = (undef, {});
    if (-e $path) {
      open(my $in, "<", $path) or die "cannot read it: $!\n";
      { local $/; $raw = <$in>; }
      close $in;
      if ($raw =~ /\S/) {
        $data = eval { $json->decode($raw) };
        die "it is not valid JSON, so it was left unchanged\n" unless defined $data;
      }
    }
    exit 0 if $mode eq "remove" && !defined $raw;
    die "it does not hold a JSON object, so it was left unchanged\n" unless ref $data eq "HASH";
    my $perms = exists $data->{permissions} ? $data->{permissions} : {};
    die "its \"permissions\" is not an object, so it was left unchanged\n" unless ref $perms eq "HASH";
    for my $key (sort keys %rules) {
      die "its \"permissions.$key\" is not a list, so it was left unchanged\n"
        if exists $perms->{$key} && ref $perms->{$key} ne "ARRAY";
    }
    my @changed;
    for my $key (sort keys %rules) {
      my $list = exists $perms->{$key} ? $perms->{$key} : [];
      my @kept;
      if ($mode eq "add") {
        my %listed = map { $_ => 1 } grep { !ref } @$list;
        my @missing = grep { !$listed{$_} } @{$rules{$key}};
        next unless @missing;
        @kept = (@$list, @missing);
      } else {
        my %ours = map { $_ => 1 } @{$rules{$key}};
        @kept = grep { ref || !$ours{$_} } @$list;
        next if @kept == @$list;
      }
      push @changed, $key;
      if (@kept) { $perms->{$key} = \@kept } else { delete $perms->{$key} }
    }
    unless (@changed) {
      print "the Cloud Operator permission rule was already in $file\n" if $mode eq "add";
      exit 0;
    }
    if (%$perms) { $data->{permissions} = $perms } else { delete $data->{permissions} }
    my $tmp = "$path.tmp.$$";
    open(my $out, ">", $tmp) or die "cannot write $tmp: $!\n";
    print $out $json->encode($data);
    close($out) or do { unlink $tmp; die "cannot write $tmp: $!\n" };
    if (defined $raw) {
      chmod((stat $path)[2] & 07777, $tmp);
      open(my $bak, ">", "$path.bak") or do { unlink $tmp; die "cannot write $path.bak: $!\n" };
      print $bak $raw;
      close $bak;
      chmod((stat $path)[2] & 07777, "$path.bak");
    }
    rename($tmp, $path) or do { unlink $tmp; die "cannot replace it: $!\n" };
    my %what = (
      allow => "let Claude read ~/.config/cloud-operator without asking (permissions.allow)",
    );
    print $mode eq "add"
      ? join("; ", map { $what{$_} } @changed) . " in $file\n"
      : "removed the Cloud Operator rule from the permissions in $file\n";
  ' 2>&1)"; then
    if [ -n "$out" ]; then info "$out"; fi
  else
    warn "couldn't update $SETTINGS: $out"
    if [ "$mode" = add ]; then print_permission_rules; fi
  fi
}

uninstall() {
  command -v claude >/dev/null 2>&1 || die "Claude Code isn't installed or isn't on your PATH."
  say "Removing the Cloud Operator plugin"
  claude plugin uninstall "$PLUGIN" || true
  claude plugin marketplace remove "$MARKETPLACE" || true
  # Clears the stored sign-in, then removes the server and its client secret.
  claude mcp logout "$SERVER" >/dev/null 2>&1 || true
  claude mcp remove "$SERVER" -s user || true
  update_permissions remove
  rm -rf "$STAGE"
  info "Done. Left in place: your preferences ($PREFS) and your OAuth client"
  info "in the Google Cloud console."
}

check_prerequisites() {
  say "1/3 Checking prerequisites"
  command -v claude >/dev/null 2>&1 ||
    die "Claude Code isn't installed or isn't on your PATH. Install it, then re-run."
  info "$(claude --version 2>/dev/null | head -n 1)"
}

# Warns about a replaced plugin that's still installed, for example in a
# project's own settings, which the user-level uninstall doesn't reach.
check_replaced_plugins() {
  local installed old
  installed="$(claude plugin list 2>/dev/null || true)"
  for old in $OLD_PLUGINS; do
    case "$installed" in
      *"${old%@*}@"*)
        warn "${old%@*} is still installed, and competes with Cloud Operator for the same requests. Remove it: claude plugin uninstall $old (in a project that installed it, add --scope project)"
        ;;
    esac
  done
}

install_plugin() {
  local old
  say "3/3 Installing the plugin"
  for old in $OLD_PLUGINS; do
    if claude plugin uninstall "$old" >/dev/null 2>&1; then
      info "removed the ${old%@*} plugin: Cloud Operator replaces it, and the two would compete for the same requests"
    fi
  done
  claude plugin marketplace remove "$OLD_MARKETPLACE" >/dev/null 2>&1 || true
  # A clean reinstall, so re-running the script always picks up the new files.
  claude plugin uninstall "$PLUGIN" >/dev/null 2>&1 || true
  claude plugin marketplace remove "$MARKETPLACE" >/dev/null 2>&1 || true
  claude plugin marketplace add "$STAGE"
  claude plugin install "$PLUGIN"
  check_replaced_plugins
  update_permissions add
}

print_next_steps() {
  cat <<EOF

Done. Next, in Claude Code (restart it if it's running):

  /cloud-operator:setup  walks you through creating your OAuth client, has you
                         run the plugin's scripts/register-mcp.sh in a
                         terminal to register the autocloud MCP server
                         and sign in, and saves your preferences

Already set up? Then you're done: updating the plugin keeps your MCP server,
sign-in and preferences.

Then ask a Google Cloud question. Onboarding guide, with troubleshooting:
  $STAGE/onboarding.md
To update the plugin, re-run this script; --uninstall removes it.
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
      --uninstall) UNINSTALL=1; shift ;;
      -h | --help) usage; exit 0 ;;
      *) die "unknown option: $1 (see --help)" ;;
    esac
  done

  # When run from a checkout of this repository, install that checkout.
  if [ -z "$SOURCE" ]; then
    local script_path="${BASH_SOURCE[0]:-}" script_dir
    if [ -n "$script_path" ] && [ -f "$script_path" ]; then
      script_dir="$(cd "$(dirname "$script_path")" && pwd)"
      if [ -f "$script_dir/.claude-plugin/plugin.json" ] && [ -f "$script_dir/../../../skills/autocloud-operator/SKILL.md" ]; then
        SOURCE="$(cd "$script_dir/../../.." && pwd)"
      fi
    fi
  fi

  if [ "$UNINSTALL" -eq 1 ]; then
    uninstall
    exit 0
  fi

  if [ "$PACKAGE_ONLY" -eq 0 ]; then
    check_prerequisites
  fi

  say "2/3 Putting the plugin together"
  if [ -z "$SOURCE" ]; then
    download_source
  else
    [ -d "$SOURCE" ] || die "--source $SOURCE isn't a directory"
    info "from checkout: $SOURCE"
  fi
  assemble_plugin "$SOURCE"
  info "assembled in $STAGE"

  if [ "$PACKAGE_ONLY" -eq 1 ]; then
    cat <<EOF

Assembled only. To try it without installing:
  claude --plugin-dir "$STAGE"
To check the manifests:
  claude plugin validate "$STAGE"

This doesn't add the permission rule to your Claude Code settings. Run
install.sh without --package-only, or add it by hand (see --help).
EOF
    exit 0
  fi

  local validation
  if ! validation="$(claude plugin validate "$STAGE" 2>&1)"; then
    printf '%s\n' "$validation" >&2
    die "the assembled plugin didn't pass 'claude plugin validate'"
  fi

  install_plugin
  print_next_steps
}

# Everything runs from here, so a partly downloaded script does nothing.
main "$@"
