# Cloud Operator client plugins

Client plugins for **Cloud Operator**, the Gemini Cloud Assist operator agent:
thin clients that route Google Cloud requests from an AI coding tool to the
hosted `ask_cloud_operator` MCP tool.

> [!IMPORTANT]
> **Private Preview.** Cloud Operator and its MCP server are in Private Preview.

## Install

You need access to Cloud Operator: an operator agent and
`roles/geminicloudassist.user` on its project. Each client's README covers the
other prerequisites, setup details and troubleshooting.

### Claude Code

```shell
gcloud auth login   # the Google account you'll use for Cloud Operator
curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/main/plugins/cloud-operator/claude/install.sh | bash
```

Then run `/cloud-operator:setup` in Claude Code. It walks you through creating an
OAuth client, registering the server and signing in, and saves your
preferences. See [`claude/README.md`](claude/README.md).

### ChatGPT Codex

For the ChatGPT desktop app and the Codex CLI on macOS:

```shell
gcloud auth login   # the Google account you'll use for Cloud Operator
git clone https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp.git
bash gemini-cloud-assist-mcp/plugins/cloud-operator/codex/install.sh
```

Then restart Codex, type `@cloud-operator` and ask "Set up Cloud Operator". See
[`codex/README.md`](codex/README.md).

### Google Antigravity

The plugin signs in with your Application Default Credentials. Set those up
first, as [`antigravity/README.md`](antigravity/README.md) describes, then
install it:

```shell
curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/main/plugins/cloud-operator/antigravity/install.sh | bash
```

Then restart Antigravity, turn the plugin on in `/plugin` if it shows as off,
and run `/cloud-operator:setup`.

## Organization admin setup

Before anyone in an organization can create an operator agent, an
organization administrator sets up Cloud Operator once for the organization and
its central management project. Every client plugin includes a guided
`admin-setup` skill for this: run `/cloud-operator:admin-setup` in Antigravity
or Claude Code, or ask Codex to "set up Cloud Operator for my organization".
`/cloud-operator:admin-setup status` only checks.

It walks the admin through each step: the admin's own roles, APIs, the
Admin Onboarding Console, a users group and its roles, the agent principal set,
the org policy override for the management project, data egress policies,
optional Model Armor, the UAP egress policy and the App Hub boundary. For each
step it checks the current state, explains what will change and why, shows the
exact `gcloud` commands, and runs them only after the admin says yes (or prints
them for the admin to run). It then verifies the result, suggests fixes when
something fails, and ends with a status table.

> [!WARNING]
> During Private Preview, binding the organization to a management project in
> the Admin Onboarding Console is permanent. The skill asks the admin to type the
> project ID before that step.

It runs on macOS, Linux and Cloud Shell, and needs `bash`, `curl` and `gcloud`
587.0.0 or later with the beta components. Every status it reports comes from
live `gcloud` and IAM API calls. For each organization and management project
it keeps two files in `~/.config/cloud-operator/admin-setup/<ORG_ID>/<PROJECT_ID>/`:
`state.env` (the inputs, such as the org, project and account, so a later run
doesn't ask again) and `changes.log` (every change it made: time, account,
command and result). Neither holds secrets, and its scripts manage both.

The rest of this page is for contributors.

## Layout

```text
skills/autocloud-operator/  The routing skill (when and how to call ask_cloud_operator),
                            shared by every client plugin and the repository-root plugin
plugins/cloud-operator/
├── shared/admin-setup/     The organization admin setup skill, the same for every client
├── antigravity/            Antigravity: client-specific files
├── claude/                 Claude Code: client-specific files
└── codex/                  Codex: client-specific files
```

Each client folder holds only what's specific to that client: its plugin
manifest, installer, sign-in setup, and client-specific commands or skills
(such as setup). The routing skill isn't copied into each client: every
installer takes it from [`skills/autocloud-operator`](../../skills/autocloud-operator/SKILL.md)
at the repository root.

## Packaging

Client folders aren't installable on their own: the routing skill lives at
the repository root, and client folders carry no marketplace manifest. Each
client has its own installer in its folder, such as `claude/install.sh`,
which assembles the plugin when the user installs it:

1. Copy `skills/autocloud-operator` from the repository root into the plugin's
   `skills/autocloud-operator` folder.
2. Copy `plugins/cloud-operator/shared/admin-setup` into the plugin's
   `skills/admin-setup` folder.
3. Copy the client folder on top.
4. Install the assembled plugin with the client's own tooling, through a
   marketplace where the client needs one.

## Rules for the admin setup skill

- `shared/admin-setup` is client-neutral: plain `gcloud`, `bash` and `curl`, no
  client-specific tool names or paths. It refers to its own files relative to
  its folder. A client that needs a slash command for it adds a thin wrapper in
  its own folder (as `claude/commands/admin-setup.md` does).
- Helpers that call REST APIs gcloud doesn't cover
  (`scripts/set-modelarmor-enforcement.sh`,
  `scripts/bootstrap-agent-identity-pool.sh`) read the access token
  themselves and send it through stdin, so it never reaches a command line or
  the change log.
- Every change goes through `scripts/log-run.sh` after the admin approves it;
  `scripts/admin-status.sh` stays read-only in Google Cloud and always checks
  live. Both take `--org` and `--project` and keep their files per org and
  project (`scripts/paths.sh`); the skill never writes those files itself.
- `assets/uap-policy-3p.json` holds the UAP egress rules. To update them, take
  the current third-party rules from the AutoCloud team, keep the
  `__ORG_ID__` and `__PROJECT_NUMBER__` placeholders, leave out hosts that
  only serve Google-internal environments, update the rules table in
  `references/steps.md` (Step 10), and check the result with
  `admin-status.sh render-uap`. The current rules match the AutoCloud
  third-party template as of October 2026.

## The repository-root plugin

The repository root also ships a plugin, `gemini-cloud-assist-mcp`, for
several clients. In Claude Code, Codex and Antigravity, a plugin from this
folder replaces it, so don't install both. Both bring the same routing skill,
and the two would compete for the same requests. Both connect to
`/mcp/autocloud`, which serves only the operator tools.

## Rules for the routing skill

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

## Adding a client

Create `plugins/cloud-operator/<client>/` with the client's manifest,
installer, sign-in setup, and any client-specific commands and skills,
following the packaging steps above. Describe it in the client's `README.md`.
