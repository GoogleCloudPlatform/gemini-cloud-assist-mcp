# Cloud Operator plugin

The `cloud-operator` plugin connects Antigravity to the **Cloud Operator
Agent**, which designs, reviews, operates and troubleshoots infrastructure in
your Google Cloud projects.

This plugin bundles the `cloud-operator` skill and the configuration for the
**Autocloud** MCP server into a single portable package.

## Setup

The Autocloud server signs in with your Google credentials (Application Default
Credentials).

**Prerequisites:**

1.  The [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
    (`gcloud`), signed in, with Application Default Credentials for the same
    account: `gcloud auth login`, then `gcloud auth application-default login`.
1.  A quota project for those credentials, usually the project where your
    operator agent is:
    `gcloud auth application-default set-quota-project <YOUR_PROJECT_ID>`.
    Your account needs `serviceusage.services.use` on it (project Owners and
    Editors have it).
1.  The API enabled in the project where your operator agent is:
    `gcloud services enable geminicloudassist.googleapis.com --project=<YOUR_PROJECT_ID>`.
1.  The `roles/geminicloudassist.user` role on that project.

Then restart Antigravity. If the server doesn't appear, turn the plugin on in
`/plugin` (a new install can start disabled).

The first time you ask about your Google Cloud projects, Antigravity asks which
project your operator agent is in, helps you create the agent if you don't have
one, and remembers your choice. To do this up front, ask it to **set up Cloud
Operator**. To create the agent yourself, open
`https://console.cloud.google.com/autocloud/home?project=<YOUR_PROJECT_ID>`,
signed in with the same account, and click **Create operator agent**.

To check the connection, ask Antigravity to **check Cloud Operator**: it makes
one harmless call and tells you the project and agent it used.

## Troubleshooting

-   **The server doesn't appear:** restart Antigravity, and turn the plugin on
    in `/plugin` (a new install can start disabled).
-   **Other errors:** Antigravity explains them and the fix when a call fails.

## What's Included

### Bundled Skills

-   **[cloud-operator](./skills/cloud-operator)**:
    Routes Google Cloud requests about your projects (questions, architecture,
    Terraform and Kubernetes review, rollouts, incidents, cost) to the Cloud
    Operator Agent. The first time, it asks for your operator project and
    agent, and helps you create the agent.

### MCP Servers

-   **Autocloud MCP server** (`autocloud`): Gives AI agents the
    `ask_cloud_operator` tool, which hands Google Cloud work to the Cloud
    Operator Agent. It sees your live resources, logs, metrics,
    billing and policies, and calls can run for up to 20 minutes.

The server signs in with your Google credentials (Application Default
Credentials), declared in the plugin's `com.google.antigravity/mcp_config.json`
and `mcp_config.json`.

--------------------------------------------------------------------------------

## Network, Sandbox, and Permission Requirements

If you run Antigravity with terminal sandboxing or behind a corporate
firewall/proxy, configure your environment to allow the following outbound URLs
and terminal commands.

### 1. Required Outbound URL Allowlist

| Domain / Endpoint | Used By | Purpose |
| :--- | :--- | :--- |
| `https://github.com` | Installer | Installs the plugin. |
| `https://geminicloudassist.googleapis.com` | `autocloud` MCP, `cloud-operator` | Connects to the Autocloud MCP server (`/mcp/autocloud`). |
| `https://oauth2.googleapis.com` | `autocloud` MCP | Refreshes your Google credentials. |

### 2. Required Terminal Command Permissions

-   **Cloud Operator** (`cloud-operator`): `gcloud config get-value project`,
    offered only as a suggestion for your operator project, and
    `gcloud auth application-default print-access-token`, to check your
    credentials when a call fails to sign in. The skill prefixes each command
    with a usage attribution variable
    (`CLOUDSDK_METRICS_REQUEST_ATTRIBUTION="agent-skills/1.0 (skill:cloud-operator; version:1.0.3)"`),
    so command rules that match the start of a command need to include it.
-   **Interactive or state-changing `gcloud` commands** (`cloud-operator`):
    `gcloud auth login`, `gcloud auth application-default login`,
    `gcloud auth application-default set-quota-project`,
    `gcloud services enable`. Do not auto-allow these commands; keep them gated
    behind confirmation (**Ask**) or run them manually beforehand.
