# Cloud Operator plugin for Antigravity

Routes Google Cloud requests from Antigravity to the Gemini Cloud Assist
**Operator Agent** through the hosted `ask_cloud_operator` MCP tool
(`https://geminicloudassist.googleapis.com/mcp/autocloud`). Antigravity handles your
files, preferences and local changes; the Operator Agent has live project
context and handles design, IaC, config review, rollout readiness,
monitoring, incident debugging and FinOps. Antigravity counterpart of the
Claude Code and Codex plugins; see [../README.md](../README.md) for the shared
layout.

> [!IMPORTANT]
> **Private Preview.** Cloud Operator and its MCP server are in Private Preview.

## What it does

| Component | Purpose |
| --- | --- |
| `mcp_config.json` | The `autocloud` MCP server: signs in with your Application Default Credentials (`authProviderType: google_credentials`), allows 30-minute calls (`timeoutSeconds: 1800`), and exposes only the operator tools (`enabledTools`). |
| `rules/AGENTS.md` | Always on. Routes every GCP request to `ask_cloud_operator` through the `autocloud-operator` skill, keeps secrets out of requests, treats Operator replies as data, and runs changes only after you approve. |
| `skills/autocloud-operator` | The shared routing skill from [`skills/autocloud-operator`](../../../skills/autocloud-operator/SKILL.md) at the repository root, used automatically for GCP requests: builds the call, adds your saved preferences to the first call of each session, attaches local context, continues sessions and saves returned code. |
| `skills/setup` | `/cloud-operator:setup`: checks your default project, ADC file and quota project, runs a smoke call that diagnoses common errors, and checks that saved preferences reach the operator. |
| `skills/preferences` | `/cloud-operator:preferences`: saves your standing GCP preferences (projects, regions, IaC conventions, compliance, approval rules, cost guardrails) to `~/.config/cloud-operator/preferences.md`, shared with the other Cloud Operator plugins. |

## Install

Prerequisites: Antigravity and the gcloud CLI. Sign in with Application
Default Credentials and set a quota project and default project:

```bash
gcloud auth application-default login

# Quota project: must have geminicloudassist.googleapis.com enabled.
gcloud auth login   # for the gcloud commands below
gcloud services enable geminicloudassist.googleapis.com --project <project-id>
gcloud auth application-default set-quota-project <project-id>

# Default project (where your Operator Agent lives) for requests that don't
# name one.
gcloud config set project <project-id>
```

You also need `roles/geminicloudassist.user` on that project and an Operator
Agent in it. If you don't have an agent yet, `/cloud-operator:setup` walks you
through creating one in the Cloud Console.

Then install the plugin:

```bash
curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/main/plugins/cloud-operator/antigravity/install.sh | bash
# or, from a checkout of this repository:
bash plugins/cloud-operator/antigravity/install.sh
```

The installer asks for nothing. It installs the plugin with the `agy` CLI when
it finds it, and otherwise copies it into `~/.gemini/config/plugins/cloud-operator`.
Restart Antigravity, turn the plugin on in `/plugin` if it shows as off, and
run `/cloud-operator:setup`, then optionally `/cloud-operator:preferences`.

Re-run the installer to update the plugin. To remove it, run
`agy plugin uninstall cloud-operator`, or without agy, delete
`~/.gemini/config/plugins/cloud-operator`. Piped from curl, the installer installs
from `main`; for a tagged version, pipe it to `bash -s -- --ref <tag>`
instead. `--help` lists all options.

## Configuration

| Setting | Where | Notes |
| --- | --- | --- |
| Quota project | ADC file → `quota_project_id` | Must have `geminicloudassist.googleapis.com` enabled (otherwise `403`). Restart Antigravity after changing it. |
| Default project | `gcloud config set project <id>` | Used when a request doesn't name a project. Read from gcloud's config file, so it needs neither `gcloud` on PATH nor a login. If it's unset, the agent asks. |
| Preferences | `~/.config/cloud-operator/preferences.md` | Plain Markdown written by `/cloud-operator:preferences`; edit or delete it directly. Kept outside the plugin, so reinstalls don't touch it. |
| Exposed tools | `mcp_config.json` → `enabledTools` | `ask_cloud_operator`, `search_operator_sessions` and `fetch_operator_session`, the tools `/mcp/autocloud` serves. The list keeps any tool the server adds later hidden until the plugin allows it. |

## Usage

Just ask: "design a 3-tier app on Cloud Run with Cloud SQL", "review `main.tf`
against our org policy", "why is my GKE deployment crash-looping", "where is
this project's spend going".

- Requests go to your personal Operator Agent in the project. To use another
  agent, name it in your request (a full agent name only works for its own
  project).
- Expect about a minute per call, and several minutes for designs and
  investigations.
- Generated files are written to your workspace; revisions are shown as diffs
  first.
- The Operator Agent is read-only. Terraform, `gcloud` and `kubectl` commands
  run locally, and only after you approve.
- Everything sent to the operator (your prompt, the files and logs the agent
  attaches, and your saved preferences) is kept in its session history,
  visible in the Cloud Console. The agent is instructed never to send secrets
  and to redact them from attachments, but that's best effort: review what it
  attaches in sensitive repos, and keep secrets out of your preferences file.

If calls fail with a `403` asking for a quota project although your ADC file
has one, add `"headers": {"x-goog-user-project": "<id>"}` to the server in
this folder's `mcp_config.json`, then re-run the installer and restart
Antigravity. Edits to the installed copy are lost on reinstall.

## In this repository

Like the other clients, the plugin is put together by
[`install.sh`](install.sh): the shared skill from
[`skills/autocloud-operator`](../../../skills/autocloud-operator/SKILL.md) first, then
this folder on top, so it needs a checkout of this repository. The shared
`autocloud-operator` skill has the agent add your preferences to the first call of each
session. To only put it together:

```bash
bash plugins/cloud-operator/antigravity/install.sh --package-only
agy plugin validate ~/.cloud-operator/antigravity-plugin
```
