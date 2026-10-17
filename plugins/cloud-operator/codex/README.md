# Cloud Operator plugin for Codex

Operate GCP infrastructure from Codex (desktop app and CLI) through the Gemini
Cloud Assist `ask_cloud_operator` MCP tool
(`https://geminicloudassist.googleapis.com/mcp/autocloud`).

> [!IMPORTANT]
> **Private Preview.** Cloud Operator and its MCP server are in Private Preview.

## What it does

- `setup` skill — uses an existing OAuth client, or guides you through
  Cloud Console login, the OAuth consent screen and Desktop app client creation
  in your own GCP project. It then registers the `autocloud` MCP server in
  `~/.codex/config.toml` (30-minute tool timeout, only the operator tools
  enabled), checks that you have an operator agent and walks you through
  creating one if you don't. It also starts on its own when a GCP request
  needs the operator and the server isn't set up.
- `preferences` skill — interviews you for GCP operating preferences
  (projects, regions, naming, change policy, security, cost…) or saves a single
  preference. Stored in `~/.config/cloud-operator/preferences.md` and sent to the
  operator's memory.
- `autocloud-operator` skill — thin client: frames GCP requests, includes your preferences
  and local context, calls `ask_cloud_operator`, relays results, keeps you in
  control of approvals.

## Install

Requires macOS, a ChatGPT desktop app with Codex 26.1007 or later, the Google
Cloud CLI (`gcloud`) signed in, and `roles/geminicloudassist.user` on the
project where your operator agent is.

```bash
gcloud auth login   # the Google account you'll use for Cloud Operator
git clone https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp.git
cd gemini-cloud-assist-mcp
bash plugins/cloud-operator/codex/install.sh
```

The installer installs the plugin only, and asks for nothing.

The Codex CLI ships with the ChatGPT app. If `codex` isn't on your `PATH`, add
an alias so you can run it in a terminal (use `~/.bash_profile` instead of
`~/.zshrc` if your shell is bash):

```bash
echo 'alias codex="/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex"' >> ~/.zshrc
source ~/.zshrc
codex --version
```

Then:

1. Restart Codex: quit (Cmd+Q) and reopen the desktop app, or start a new CLI
   session.
2. Type `@cloud-operator` and ask **"Set up Cloud Operator"**. Setup walks you
   through your OAuth client, has you run
   [`scripts/register-mcp.sh`](scripts/register-mcp.sh) in your terminal to
   register the `autocloud` MCP server and sign in (so the client secret stays
   out of the conversation), then asks you to restart Codex.
3. In a new chat, type `@cloud-operator`, pick the Cloud Operator plugin and
   say **"continue Cloud Operator setup"**. It sets up your operator project
   and agent, helping you create the agent if you don't have one, verifies it
   and saves your preferences.

The desktop app and the Codex CLI share `~/.codex`, so setup done in one works
in both.

To remove the plugin and its MCP server:

```bash
codex plugin remove cloud-operator@personal
codex mcp remove autocloud
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Setup says the Codex version is too old (`codex mcp add --help` doesn't list `--oauth-client-secret`) | Update the ChatGPT desktop app |
| `redirect_uri_mismatch` at sign-in | A new client: use a **Desktop app** client. An existing Web application client: rerun `register-mcp.sh --callback-port <PORT>` with the port of its redirect URI |
| "Missing required parameter: scope" at sign-in | Rerun `register-mcp.sh`, or `codex mcp login autocloud --scopes https://www.googleapis.com/auth/cloud-platform` |
| `access_not_configured`, `org_internal` or "access blocked" at sign-in | The client's consent screen doesn't allow your account. Add your account as a test user on the client's project (Google Auth Platform > Audience), or ask whoever manages that project |
| "invalid authentication credentials", or sign-in errors after about a week | Run `codex mcp login autocloud`. With an External consent screen, Google expires the sign-in every 7 days |
| `ask_cloud_operator` isn't available | Run `codex mcp get autocloud`; if the server is there, run `codex mcp login autocloud`, then restart Codex. If it isn't, say **"Set up Cloud Operator"** |
| A `.codex/config.toml` in your project defines `[mcp_servers.autocloud]` | In a trusted project it overrides the server setup created; remove that entry |
| "personal operator agent … has not been initialized yet" | Create your agent: open `https://console.cloud.google.com/autocloud/home?project=<PROJECT>`, click **Create operator agent**, then **Get started**, wait 1–3 minutes, then say **"continue Cloud Operator setup"** |
| "agent … is not ready to serve yet; it is probably still being provisioned" | A new agent takes 1–3 minutes to become ready. Wait and retry; if the Cloud Operator page shows the agent and calls still fail after a few tries, ask your admin |
| Permission error on the Cloud Operator page or in operator calls | Your account needs `roles/geminicloudassist.user` on the project; ask your admin. New access can take a few minutes to apply |
| "The caller does not own agent …", or calls hang on simple questions | The agent belongs to another user or project. Say **"continue Cloud Operator setup"** to choose your agent again, or fix it in `~/.config/cloud-operator/preferences.md` |
