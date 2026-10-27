# Cloud Operator plugin for Claude Code

Operate GCP infrastructure from Claude Code through the Gemini Cloud Assist
`ask_cloud_operator` MCP tool (`https://geminicloudassist.googleapis.com/mcp/autocloud`).

> [!IMPORTANT]
> **Private Preview.** Cloud Operator and its MCP server are in Private Preview.

## What it does

- `/cloud-operator:setup [project]` — guides you through Cloud Console login, OAuth
  consent screen, and OAuth client creation in your own GCP project, or uses an
  existing OAuth client, then registers the `autocloud` MCP server
  (user scope, 30-minute tool timeout). It also checks that you have an
  operator agent, and walks you through creating one if you don't.
- `/cloud-operator:preferences [pref]` — interviews you for GCP operating preferences
  (projects, regions, naming, change policy, security, cost…) or saves a single
  preference. Stored in `~/.config/cloud-operator/preferences.md`.
- `autocloud-operator` skill — thin client: frames GCP requests, includes your preferences
  and local context, calls `ask_cloud_operator`, relays results, keeps you in
  control of approvals.

Claude reads your preferences file when it needs it, for example to find the
project to send to the operator.

The installer adds one rule to `permissions.allow` in your Claude Code user
settings, `~/.claude/settings.json`: `Read(~/.config/cloud-operator/**)`, so Claude
reads your preferences without asking each time.

It rewrites the file pretty-printed, with its keys sorted, and keeps the
previous one as `settings.json.bak`, so a diff between the two also shows
lines that only moved. `--uninstall` removes the rule.

## Onboarding

Step-by-step guide, including the OAuth consent-screen choice, verification and troubleshooting: [`onboarding.md`](onboarding.md).

## Install

Requires the Google Cloud CLI (`gcloud`).

```bash
gcloud auth login   # the Google account you'll use for Cloud Operator
curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/main/plugins/cloud-operator/claude/install.sh | bash
# or, from a checkout of this repository:
bash plugins/cloud-operator/claude/install.sh
```

The installer installs the plugin only, and asks for nothing. Then start
Claude Code and run `/cloud-operator:setup`: it walks you through creating your
OAuth client (or uses an existing one), runs
[`scripts/register-mcp.sh`](scripts/register-mcp.sh) with your client's
credentials JSON file, or has you run it in your terminal, to register the
`autocloud` MCP server (the script reads the client secret from the file, so it
stays out of the conversation), helps you create your operator agent if you
don't have one, and saves your preferences.

The installer also removes `gemini-cloud-assist-mcp`, the plugin at the root of
this repository, which this plugin replaces in Claude Code: their skills would
compete for the same requests. Re-run the installer to update the plugin, or
run it with `--uninstall` to remove it. Piped from curl, it installs from
`main`; for a tagged version, pipe it to `bash -s -- --ref <tag>` instead.
`--help` lists all options.

## In this repository

The `autocloud-operator` skill is shared by all clients and lives in
[`skills/autocloud-operator`](../../../skills/autocloud-operator/SKILL.md) at the
repository root, and this folder has no marketplace manifest, so it isn't
installable on its own. [`install.sh`](install.sh) puts the plugin together
(the shared skill, then this folder), writes the manifest and installs it. To only put it together,
for example to try it without installing:

```bash
bash plugins/cloud-operator/claude/install.sh --package-only
claude --plugin-dir ~/.cloud-operator/claude-plugin
```

This doesn't add the permission rule described above. Run the installer, or
add it by hand (see `install.sh --help`).
