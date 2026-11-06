# Cloud Operator plugin

The `cloud-operator` plugin connects AI coding agents to the **Cloud Operator
Agent**, which designs, reviews, operates and troubleshoots infrastructure in
your Google Cloud projects.

Built on the open [Agent Plugins specification](https://agent-plugins.org/),
this plugin bundles the `cloud-operator` skill and the configuration for the
**Autocloud** MCP server into a single portable package.

--------------------------------------------------------------------------------

## Prerequisites

In Claude Code and Antigravity, the Autocloud server signs in with
your Google credentials (Application Default Credentials, ADC). On your machine
you need:

1.  The [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
    (`gcloud`), on the `PATH` of the terminal you start your agent from.

1.  gcloud signed in, and Application Default Credentials for the same account:

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

Restart your agent after you change your credentials. If your organization
blocks Application Default Credentials ("This app is blocked" at
`gcloud auth application-default login`), the server can't sign in; ask your
admin.

In Codex, you also add the server to `~/.codex/config.toml` (Setup, below).

--------------------------------------------------------------------------------

## Installation

### Remove an earlier install first

If you installed Cloud Operator with one of the earlier per-client installers
(`install.sh`), remove that copy before you install this plugin. It would
compete with this plugin for the same requests, and its `autocloud` server
entry would replace this plugin's.

-   **Claude Code:**

    ```bash
    claude plugin uninstall cloud-operator@cloud-operator-marketplace
    claude plugin marketplace remove cloud-operator-marketplace
    claude mcp logout autocloud
    claude mcp remove autocloud -s user
    ```

    `claude mcp logout` revokes your sign-in, and `claude mcp remove` deletes
    the server entry with what Claude Code stored for it. Then remove
    `Read(~/.config/cloud-operator/**)` from `permissions.allow` in
    `~/.claude/settings.json`.

-   **Codex:**

    ```bash
    codex plugin remove cloud-operator@personal
    codex mcp logout autocloud
    codex mcp remove autocloud
    rm -rf ~/.codex/plugins/cloud-operator ~/.codex/cloud-operator-backups
    rm -f ~/.codex/config.toml.bak.cloud-operator.*
    ```

    If your personal marketplace has another name, run
    `codex plugin marketplace list` to find it. The
    `config.toml.bak.cloud-operator.*` files are the earlier setup's backups of
    `~/.codex/config.toml`, and they can hold your OAuth client secret. Then
    delete the `cloud-operator` entry in `~/.agents/plugins/marketplace.json`,
    and check that `~/.codex/config.toml` has no `[mcp_servers.autocloud]` or
    `[mcp_servers.autocloud.oauth]` table left.

-   **Antigravity:** run `agy plugin uninstall cloud-operator`.

Then delete `~/.cloud-operator` and `~/.config/cloud-operator`; nothing reads
them anymore. If you created an OAuth client only for the earlier setup, you
can also delete it in the Google Cloud console (**Google Auth Platform** >
**Clients**): this plugin signs in with Application Default Credentials.

### Antigravity CLI

Install the plugin directly via the CLI using its path in this repository:

```bash
agy plugin install https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/plugins/cloud-operator
```

### Claude Code

Add this repository's marketplace, then install the plugin:

```bash
claude plugin marketplace add GoogleCloudPlatform/gemini-cloud-assist-mcp
claude plugin install cloud-operator@gemini-cloud-assist-mcp
```

> [!NOTE] On native Windows, the plugin signs in with your Google credentials
> through `scripts/adc-headers.cmd`. If the server doesn't connect, run Claude
> Code in [WSL](https://code.claude.com/docs/en/setup#install-in-wsl).

### Codex CLI

Add this repository's marketplace, then install the plugin:

```bash
codex plugin marketplace add GoogleCloudPlatform/gemini-cloud-assist-mcp
codex plugin add cloud-operator@gemini-cloud-assist-mcp
```

> [!NOTE] If `codex` isn't found and you use the ChatGPT desktop app on macOS,
> the Codex CLI ships inside the app: run
> `/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`
> instead, or add its folder to your `PATH`.

Then finish the setup, below.

--------------------------------------------------------------------------------

## Setup

### Claude Code and Antigravity

With the prerequisites in place, the server connects on its own.

### Codex: add the server to config.toml

Codex can't use the plugin's own server entry to sign in, so you add the server
to its configuration yourself.

1.  Finish the [Prerequisites](#prerequisites) above (gcloud, Application
    Default Credentials, the API, and the role).

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

### First use (all agents)

The first time you ask about your Google Cloud projects, your agent asks which
project your operator agent is in, helps you create the agent if you don't have
one, and remembers your choice. To do this up front, ask your agent to **set up
Cloud Operator**.

To create the operator agent yourself, open
`https://console.cloud.google.com/autocloud/home?project=<YOUR_PROJECT_ID>`,
signed in with the same account, and click **Create operator agent**.

To check the connection, ask your agent to **check Cloud Operator**: it makes
one harmless call and tells you the project and agent it used.

--------------------------------------------------------------------------------

## Troubleshooting

-   **The server isn't listed, or `ask_cloud_operator` isn't available:**
    restart your agent. In Antigravity, turn the plugin on in `/plugin` (a new
    install can start disabled). In Claude Code, `claude mcp get autocloud`
    shows whether an `autocloud` entry of your own replaces the plugin's;
    remove it with `claude mcp remove autocloud -s <scope>`.
-   **Codex doesn't see the server's tools:** check that
    `mcp_optional_startup_grace_ms = 0` is at the top of `~/.codex/config.toml`,
    and that `codex mcp list` shows `autocloud`.
-   **Other errors:** your agent explains them and the fix when a call fails.

--------------------------------------------------------------------------------

## What's Included

### Bundled Skills

-   **[cloud-operator](./skills/cloud-operator)**:
    Routes Google Cloud requests about your projects (questions, architecture,
    Terraform and Kubernetes review, rollouts, incidents, cost) to the Cloud
    Operator Agent. The first time, it asks for your operator project and
    agent, and helps you create the agent.

### MCP Servers

The plugin declares the server for each agent (`mcp.json` for Agent Plugins
clients, `.mcp.json` for Claude Code, `mcp_config.json` for Antigravity):

| Server | Name | What it does | Endpoint |
| :--- | :--- | :--- | :--- |
| Autocloud | `autocloud` | The `ask_cloud_operator` tool: hands Google Cloud work to the Cloud Operator Agent, which sees your live resources, logs, metrics, billing and policies. Calls can run for up to 20 minutes | `https://geminicloudassist.googleapis.com/mcp/autocloud` |

In Claude Code, the plugin runs its `scripts/adc-headers` (on Windows,
`scripts/adc-headers.cmd`) each time it connects to the server, to send a fresh
token from your Google credentials; you don't run it yourself. In Codex, you
point `~/.codex/config.toml` at the same helper (Setup, above).

--------------------------------------------------------------------------------

## Network, Sandbox, and Permission Requirements

If you run your agent in a local sandbox or behind a corporate firewall/proxy,
configure your environment to allow the following outbound URLs and terminal
commands.

### 1. Required Outbound URL Allowlist

| Domain / Endpoint | Used By | Purpose |
| :--- | :--- | :--- |
| `https://github.com` | Installer | Installs the plugin. |
| `https://geminicloudassist.googleapis.com` | `autocloud` MCP, `cloud-operator` | Connects to the Autocloud MCP server (`/mcp/autocloud`). |
| `https://oauth2.googleapis.com` | `autocloud` MCP | Refreshes your Google credentials. |

### 2. Required Terminal Command Permissions

-   **MCP server sign-in** (Claude Code and Codex): the plugin's
    `scripts/adc-headers` (`scripts/adc-headers.cmd` on Windows) runs
    `gcloud auth application-default print-access-token` and
    `gcloud config get-value` each time the agent connects to the server.
-   **Cloud Operator** (`cloud-operator`): `gcloud config get-value project`,
    offered only as a suggestion for your operator project, and
    `gcloud auth application-default print-access-token`, to check your
    credentials when a call fails to sign in.
-   **Interactive or state-changing `gcloud` commands** (`cloud-operator`):
    `gcloud auth login`, `gcloud auth application-default login`,
    `gcloud auth application-default set-quota-project`,
    `gcloud services enable`. Do not auto-allow these commands; keep them gated
    behind confirmation (**Ask**) or run them manually beforehand.

> [!NOTE] The `cloud-operator` skill prefixes each `gcloud` command it runs
> with a usage attribution variable, for example
> `CLOUDSDK_METRICS_REQUEST_ATTRIBUTION="agent-skills/1.0 (skill:cloud-operator; version:1.0.3)" gcloud config get-value project`.
> Clients that match permission rules against the start of a command, such as
> Claude Code, need rules that include the prefix: a rule for
> `gcloud config get-value` alone doesn't match. For example, in Claude Code:
> `Bash(CLOUDSDK_METRICS_REQUEST_ATTRIBUTION=* gcloud config get-value *)`. Use
> `*` wildcards, not the trailing `:*` prefix syntax, which Claude Code doesn't
> combine with other wildcards.
>
> Claude Code also asks before reading a skill's reference files. To allow
> that, add a Read rule for the folder the plugin is installed in. Absolute
> paths in Read rules start with `//`, for example
> `Read(//Users/<you>/.claude/plugins/**)`.
