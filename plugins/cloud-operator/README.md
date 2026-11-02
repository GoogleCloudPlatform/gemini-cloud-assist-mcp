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

--------------------------------------------------------------------------------

## Per-client plugins (deprecated)

> [!WARNING]
> **Deprecated.** The per-client plugins in `claude/`, `codex/` and
> `antigravity/` are deprecated and will be removed soon. Use the
> `cloud-operator` plugin above instead.

Client plugins for **Cloud Operator**, the Gemini Cloud Assist operator agent:
thin clients that route Google Cloud requests from an AI coding tool to the
hosted `ask_cloud_operator` MCP tool.

> [!IMPORTANT]
> **Private Preview.** Cloud Operator and its MCP server are in Private Preview.

### Install

You need access to Cloud Operator: an operator agent and
`roles/geminicloudassist.user` on its project. Each client's README covers the
other prerequisites, setup details and troubleshooting.

#### Claude Code

```shell
gcloud auth login   # the Google account you'll use for Cloud Operator
curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/main/plugins/cloud-operator/claude/install.sh | bash
```

Then run `/cloud-operator:setup` in Claude Code. It walks you through creating an
OAuth client, registering the server and signing in, and saves your
preferences. See [`claude/README.md`](claude/README.md).

#### ChatGPT Codex

For the ChatGPT desktop app and the Codex CLI on macOS:

```shell
gcloud auth login   # the Google account you'll use for Cloud Operator
git clone https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp.git
bash gemini-cloud-assist-mcp/plugins/cloud-operator/codex/install.sh
```

Then restart Codex, type `@cloud-operator` and ask "Set up Cloud Operator". See
[`codex/README.md`](codex/README.md).

#### Google Antigravity

The plugin signs in with your Application Default Credentials. Set those up
first, as [`antigravity/README.md`](antigravity/README.md) describes, then
install it:

```shell
curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/main/plugins/cloud-operator/antigravity/install.sh | bash
```

Then restart Antigravity, turn the plugin on in `/plugin` if it shows as off,
and run `/cloud-operator:setup`.

The rest of this page is for contributors.

### Layout

```text
skills/autocloud-operator/  The routing skill (when and how to call ask_cloud_operator),
                            shared by every client plugin and the repository-root plugin
plugins/cloud-operator/
├── antigravity/            Antigravity: client-specific files
├── claude/                 Claude Code: client-specific files
└── codex/                  Codex: client-specific files
```

Each client folder holds only what's specific to that client: its plugin
manifest, installer, sign-in setup, and client-specific commands or skills
(such as setup). The routing skill isn't copied into each client: every
installer takes it from [`skills/autocloud-operator`](../../skills/autocloud-operator/SKILL.md)
at the repository root.

### Packaging

Client folders aren't installable on their own: the routing skill lives at
the repository root, and client folders carry no marketplace manifest. Each
client has its own installer in its folder, such as `claude/install.sh`,
which assembles the plugin when the user installs it:

1. Copy `skills/autocloud-operator` from the repository root into the plugin's
   `skills/autocloud-operator` folder.
2. Copy the client folder on top.
3. Install the assembled plugin with the client's own tooling, through a
   marketplace where the client needs one.

### The repository-root plugin

The repository root also ships a plugin, `gemini-cloud-assist-mcp`, for
several clients. In Claude Code, Codex and Antigravity, a plugin from this
folder replaces it, so don't install both. Both bring the same routing skill,
and the two would compete for the same requests. Both connect to
`/mcp/autocloud`, which serves only the operator tools.

### Rules for the routing skill

- `skills/autocloud-operator` is the routing skill. Its wording was tuned and
  measured with routing evals, so keep it verbatim and change it only together
  with a new eval run.
- Every client follows the conventions that skill relies on: name the MCP
  server `autocloud`, and keep the user's standing GCP preferences in
  `~/.config/cloud-operator/preferences.md`, one file that all clients share.
- Keep it client-neutral: no client-specific tool prefixes, slash commands,
  file paths or settings. Refer to the MCP tool by its name,
  `ask_cloud_operator`. One known exception: the skill names the Claude Code
  command `/cloud-operator:preferences` as an example. Leave it there, since
  the skill changes only with a new eval run.
- Put client-specific details, such as setup and preference commands, in the
  client folder, for example in its setup skill.
- A change to the skill affects every client and the root plugin, so check it
  against each one.

### Adding a client

Create `plugins/cloud-operator/<client>/` with the client's manifest,
installer, sign-in setup, and any client-specific commands and skills,
following the packaging steps above. Describe it in the client's `README.md`.
