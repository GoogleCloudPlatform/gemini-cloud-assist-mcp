# Cloud Operator plugin

The `cloud-operator` plugin connects Codex to the **Cloud Operator Agent**,
which designs, reviews, operates and troubleshoots infrastructure in your
Google Cloud projects.

This plugin bundles the `cloud-operator` skill and the configuration for the
**Autocloud** MCP server into a single portable package.

--------------------------------------------------------------------------------

## Prerequisites

The Autocloud server signs in with your Google credentials (Application Default
Credentials, ADC). On your machine you need:

1.  The [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
    (`gcloud`), on the `PATH` of the terminal you start Codex from.

1.  gcloud signed in, and Application Default Credentials for the same account,
    saved at gcloud's default location:

    ```bash
    gcloud auth login
    gcloud auth application-default login
    ```

1.  A quota project for those credentials: the project that calls are billed
    to, usually the one where your operator agent is. Your account needs
    `serviceusage.services.use` on it (project Owners and Editors have it):

    ```bash
    gcloud auth application-default set-quota-project <YOUR_PROJECT_ID>
    ```

1.  The API enabled in the project where your operator agent is:

    ```bash
    gcloud services enable geminicloudassist.googleapis.com --project=<YOUR_PROJECT_ID>
    ```

1.  The `roles/geminicloudassist.user` role on that project.

If your organization blocks Application Default Credentials ("This app is
blocked" at `gcloud auth application-default login`), the server can't sign
in; ask your admin.

--------------------------------------------------------------------------------

## Setup

Codex can't use the plugin's own server entry to sign in, so you add the server
to its configuration yourself. It signs in with your Google credentials
(Application Default Credentials).

1.  Finish the [Prerequisites](#prerequisites) above.

1.  Copy the plugin's sign-in helper to a fixed path, because the installed
    plugin folder changes with each version. The commands copy it from the
    most recently installed version, so run them after you install the
    plugin in Codex, and again after an update.

    macOS and Linux:

    ```bash
    mkdir -p ~/.codex/bin
    cp "$(ls -dt ~/.codex/plugins/cache/*/cloud-operator/*/ | head -n 1)scripts/adc-headers" ~/.codex/bin/
    chmod +x ~/.codex/bin/adc-headers
    ```

    Windows (PowerShell):

    ```powershell
    mkdir "$env:USERPROFILE\.codex\bin" -Force | Out-Null
    $dir = (Get-ChildItem "$env:USERPROFILE\.codex\plugins\cache\*\cloud-operator\*" -Directory | Sort-Object LastWriteTime)[-1].FullName
    Copy-Item "$dir\scripts\adc-headers.cmd" "$env:USERPROFILE\.codex\bin\" -Force
    ```

1.  Add the server to `~/.codex/config.toml` (or your project's
    `.codex/config.toml`), using the full path to the helper. The helper sends
    a fresh token from your Google credentials on each connection, and
    `tool_timeout_sec` lets Cloud Operator calls run for up to 20 minutes.

    -   **macOS and Linux:** copy the block below as it is, with your user name
        in place of `<YOU>`.
    -   **Windows:** copy the same block, then change the `http_headers_helper`
        line to:

        ```toml
        http_headers_helper = '"C:/Users/<YOU>/.codex/bin/adc-headers.cmd"'
        ```

    ```toml
    # Wait for the server to start: getting a token takes a few seconds.
    mcp_optional_startup_grace_ms = 0

    [mcp_servers.autocloud]
    url = "https://geminicloudassist.googleapis.com/mcp/autocloud"
    http_headers = { "X-Goog-Api-Client" = "cloud-operator/0.0.3 agent-skills/1.0 (skill:cloud-operator; version:1.0.3; plugin:cloud-operator)" }
    http_headers_helper = '"/Users/<YOU>/.codex/bin/adc-headers"'
    tool_timeout_sec = 1200
    ```

    Put `mcp_optional_startup_grace_ms` at the top of the file, before any
    `[section]`. This entry replaces the plugin's own entry of the same name.
    Keep the double quotes inside the single quotes: Codex runs the helper
    through a shell, and the quotes keep a path with spaces in one piece. The
    helper reads your credentials from gcloud's default location; Codex doesn't
    pass `CLOUDSDK_CONFIG` or `GOOGLE_APPLICATION_CREDENTIALS` to it.

1.  Restart Codex. In the Codex CLI, `/mcp` lists the server's tools.

The first time you ask about your Google Cloud projects, Codex asks which
project your operator agent is in, helps you create the agent if you don't have
one, and remembers your choice. To do this up front, ask it to **set up Cloud
Operator**. To create the agent yourself, open
`https://console.cloud.google.com/autocloud/home?project=<YOUR_PROJECT_ID>`,
signed in with the same account, and click **Create operator agent**.

To check the connection, ask Codex to **check Cloud Operator**: it makes one
harmless call and tells you the project and agent it used.

--------------------------------------------------------------------------------

## Troubleshooting

-   **Codex doesn't see the server's tools:** check that
    `mcp_optional_startup_grace_ms = 0` is at the top of `~/.codex/config.toml`,
    and that `codex mcp list` shows `autocloud`.
-   **Other errors:** Codex explains them and the fix when a call fails.

--------------------------------------------------------------------------------

## What's Included

### Bundled Skills

-   **[cloud-operator](./skills/cloud-operator)**:
    Routes Google Cloud requests about your projects (questions, architecture,
    Terraform and Kubernetes review, rollouts, incidents, cost) to the Cloud
    Operator Agent. In Codex, it works once you add the `autocloud` server
    (Setup, above).

### MCP Servers

-   **Autocloud MCP server**: The `ask_cloud_operator` tool, which hands Google
    Cloud work to the Cloud Operator Agent. Calls can run for up to 20 minutes.

In Codex, it's the `[mcp_servers.autocloud]` entry in `~/.codex/config.toml`
from Setup, above.

--------------------------------------------------------------------------------

## Network, Sandbox, and Permission Requirements

If you run Codex in its default sandbox or behind a corporate firewall/proxy,
configure your environment to allow the following outbound URLs and terminal
commands.

### 1. Required Outbound URL Allowlist

| Domain / Endpoint | Used By | Purpose |
| :--- | :--- | :--- |
| `https://github.com` | Installer | Installs the plugin. |
| `https://geminicloudassist.googleapis.com` | `autocloud` MCP, `cloud-operator` | Connects to the Autocloud MCP server (`/mcp/autocloud`). |
| `https://oauth2.googleapis.com` | `adc-headers` helper | Refreshes your Google credentials. |

### 2. Required Terminal Command Permissions

-   **MCP server sign-in**: the `adc-headers` helper you set up runs
    `gcloud auth application-default print-access-token` and
    `gcloud config get-value` each time Codex connects to the server.
-   **Cloud Operator** (`cloud-operator`): `gcloud config get-value project`,
    offered only as a suggestion for your operator project, and
    `gcloud auth application-default print-access-token`, to check your
    credentials when a call fails to sign in.
-   **Interactive or state-changing `gcloud` commands** (`cloud-operator`):
    `gcloud auth login`, `gcloud auth application-default login`,
    `gcloud auth application-default set-quota-project`,
    `gcloud services enable`. Do not auto-allow these commands; keep them gated
    behind confirmation or run them manually beforehand.
