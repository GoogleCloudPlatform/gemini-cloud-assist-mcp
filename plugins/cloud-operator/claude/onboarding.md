# Cloud Operator onboarding for Claude Code

This guide walks you through setting up the Cloud Operator plugin for Claude Code.

**What you get:** Claude Code hands Google Cloud work to the Cloud Operator Agent through the `ask_cloud_operator` MCP tool, and saves generated Terraform/YAML back to your workspace. That covers questions, design, Terraform/Kubernetes review, rollouts, incidents and costs.

**Time:** about 15 minutes.

> Maintainers: this guide mirrors `commands/setup.md`. Change both together.

---

## 1. Prerequisites

| Need | Check |
|---|---|
| Claude Code | `claude --version` (install: see the Claude Code docs) |
| Google Cloud CLI, logged in with the account you'll use for the autocloud MCP server | `gcloud auth list`. If needed: `gcloud auth login` |
| A GCP project you can administer | `gcloud projects describe <PROJECT_ID>` |
| Permission to enable APIs and create OAuth clients in that project | Project Owner or Editor, or **Service Usage Admin** + **OAuth Config Editor** |
| perl (with JSON::PP) or python3, for `register-mcp.sh` to read your client's credentials JSON file. macOS includes perl | `perl -MJSON::PP -e 1` or `python3 --version`. Debian or Ubuntu: `sudo apt-get install perl` |

**Use the same Google account for every step:** `gcloud`, Cloud Console and the browser login in step 4.5.

**Two projects:** `<PROJECT_ID>` in sections 3 and 4 is the project for your OAuth client. The operator works in the project where your agent is (`<AGENT_PROJECT>`, section 5), which can be a different one. If you already have an OAuth client, you don't need `<PROJECT_ID>` or the project rows above (see the end of 4.3).

## 2. Install the plugin

```bash
curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/main/plugins/cloud-operator/claude/install.sh | bash
claude plugin list                           # cloud-operator should be listed and enabled
```

The installer puts the plugin together and installs it; it doesn't ask for anything. From a checkout of the repository, run `bash plugins/cloud-operator/claude/install.sh` instead.

Restart Claude Code after installing.

## 3. Run guided setup (recommended)

In Claude Code:
```
/cloud-operator:setup <PROJECT_ID>
```
Claude walks you through the steps in section 4: it first asks whether you already have an OAuth client, then runs the `gcloud` commands for you and waits at each Console step. For 4.4 and 4.5 it asks where your client's credentials JSON file is, then offers to run the plugin's `scripts/register-mcp.sh` with that file for you, or has you run it in your own terminal, which also signs you in. The script reads your client secret from the file, so the secret stays out of the conversation. Then it has you restart Claude Code (`claude -c` picks the setup back up) and, if the script didn't sign you in, sign in from `/mcp`. It then asks which project the operator should work in, checks that your operator agent answers and helps you create it if you don't have one yet (section 5), shows how to find your agent ID, and finishes with the preferences interview (section 6). **When guided setup finishes, go to section 7.** If you prefer to do it by hand, or setup stops partway, follow section 4.

## 4. Manual setup (what `/cloud-operator:setup` does)

### 4.1 Enable the Gemini Cloud Assist API
```bash
gcloud services enable geminicloudassist.googleapis.com --project <PROJECT_ID>
```

### 4.2 Configure the OAuth consent screen
1. Open `https://console.cloud.google.com/auth/overview?project=<PROJECT_ID>` signed in with your account.
2. If asked to configure Google Auth Platform, choose the audience:

   | Your situation | Choose |
   |---|---|
   | The project is in your organization, and only people in your organization will use it | **Internal** (no test users needed) |
   | The project isn't in an organization, or Internal isn't offered | **External**, then add your own email under **Test users** |

3. Fill in only the required fields (app name, support email), then save. You don't need to publish the app.

**External apps in "Testing" status:** Google's refresh tokens for these apps expire after 7 days. When the tool starts returning authentication errors, re-authenticate (step 4.5). Choosing Internal, where possible, avoids this.

### 4.3 Create a Desktop OAuth client
1. Open `https://console.cloud.google.com/auth/clients/create?project=<PROJECT_ID>`.
2. Set **Application type** to **Desktop app**, and name it `claude-code-cloud-operator`.
   - Don't choose "Web application": Claude Code's login uses a random localhost port, which only Desktop clients accept.
3. Before you click **Create**: the Console shows the client secret only once, in the dialog that opens after **Create**, so download the credentials JSON file there before you close it. Click **Create**, then **Download JSON**. The file holds the client secret, so keep it private. To keep it, and to share the client with teammates, you can store it in [Secret Manager](https://docs.cloud.google.com/secret-manager/docs/overview).

**Already have an OAuth client?** Skip 4.1–4.3 and use its credentials JSON file, or its client ID and secret, in 4.4. The client's owner has to allow your account: as a test user if the client's audience is **External**, or as a member of the client's organization if it's **Internal**. If it's a **Web application** client, add `--callback-port <PORT>` to `register-mcp.sh`, with the port of its redirect URI (`http://localhost:<PORT>/callback`).

### 4.4 Register the MCP server in Claude Code
The quickest way is the plugin's registration script, which also signs you in (4.5). Run it in your terminal, with the path of your client's credentials JSON file:
```bash
bash ~/.cloud-operator/claude-plugin/scripts/register-mcp.sh --client-json <PATH>
```
`~/.cloud-operator/claude-plugin` is the default location; `/cloud-operator:setup` shows the exact path. The script reads the client ID and secret from the file and shows only the ID. It replaces any user-scope `autocloud` MCP server entry with one that uses your client and a 30-minute timeout, and opens the Google sign-in in your browser. Claude Code keeps the secret in your system keychain. Without the file, leave out `--client-json`: the script asks for the client ID and secret (the secret isn't shown).

Or register it by hand:
```bash
claude mcp remove autocloud -s user 2>/dev/null
claude mcp add-json -s user autocloud \
  '{"type":"http","url":"https://geminicloudassist.googleapis.com/mcp/autocloud","timeout":1800000,"oauth":{"clientId":"<CLIENT_ID>"}}' \
  --client-secret                            # prompts for the client secret (keeps it out of shell history)
claude mcp get autocloud                     # expect: Needs authentication, Scope: User
```
- The `timeout` is 30 minutes, because operator calls can be long.
- **Scripting instead?** You can pass the secret with `MCP_CLIENT_SECRET='<CLIENT_SECRET>' claude mcp add-json …` (bash/zsh). Note the secret then lands in your shell history.
- Check the `Scope:` line of `claude mcp get autocloud`. If it says **Local** or **Project**, an older entry is shadowing this one. Remove it with `claude mcp remove autocloud -s local` (run it in the folder where that entry was added) or `claude mcp remove autocloud -s project` (or delete it from that repo's `.mcp.json`), then check again.

### 4.5 Authenticate
If `register-mcp.sh` signed you in, just do steps 1 and 4.
1. Restart Claude Code if it was running.
2. Run `/mcp`, select **autocloud**, then **Authenticate** (or, in a terminal: `claude mcp login autocloud`).
3. Complete the Google sign-in in the browser with the **same account**. With an External app you'll see an "unverified app" notice: continue, since it's your own app.
4. `claude mcp get autocloud` should now show **Connected**.

### 4.6 Alternative: access token (quick test, or clients without OAuth)
Use this if you can't complete the OAuth login yet, or want to try Cloud Operator first:
```bash
gcloud auth application-default login            # sign in with the account you'll use
claude mcp remove autocloud -s user 2>/dev/null
claude mcp add-json -s user autocloud "{\"type\":\"http\",\"url\":\"https://geminicloudassist.googleapis.com/mcp/autocloud\",\"timeout\":1800000,\"headers\":{\"Authorization\":\"Bearer $(gcloud auth application-default print-access-token)\"}}"
```
- Use the **Application Default Credentials** token as shown. A plain `gcloud auth print-access-token` token is rejected by the server.
- The token **expires after about 1 hour** and doesn't refresh: re-run the `add-json` line when calls fail with "invalid authentication credentials".
- It's stored in plain text in `~/.claude.json`.
- For daily use, set up OAuth (4.2–4.5), which refreshes automatically.
- **Other agents** (Codex, Gemini CLI, …) that support HTTP headers can use the same header: `Authorization: Bearer <token>`.

## 5. Your operator project and agent ID
- The operator works in the project where your **operator agent** is (`<AGENT_PROJECT>`). It can differ from your OAuth client's project. Guided setup asks for it and saves it as your default project (section 6).
- **No agent yet?** Calls then fail with "personal operator agent for project … has not been initialized yet". Create it in Cloud Console: open the Cloud Operator link your admin gave you, or `https://console.cloud.google.com/autocloud/home?project=<AGENT_PROJECT>`, signed in with the account you use for the autocloud MCP server (a private or incognito window helps if your browser is signed in to another account). Click **Create operator agent**. When the dialog says "Your operator agent is ready", click **Get started**. A permission error there means you need the Gemini Cloud Assist User role (`roles/geminicloudassist.user`) on the project, from its admin. A new agent can take a few minutes to answer. Guided setup checks this and walks you through it.
- You usually **don't need an agent ID**: calls without one go to your **personal operator agent** in the target project.
- Agent IDs are **per user and per project**. Using someone else's, or one from another project, fails with "The caller does not own agent …".
- To see yours, ask Claude:
  > List my recent cloud operator sessions in project <AGENT_PROJECT> and show the agent ID.

  Each session's `contextId` reads `projects/<AGENT_PROJECT>/locations/global/agents/<AGENT_ID>/sessions/<SESSION_ID>`. If you have no sessions yet, ask the operator any question first; every response includes a `context_id` in the same format.
- To pin it, save it **with its project**, in the short form, e.g. `/cloud-operator:preferences operator agent for projects/<AGENT_PROJECT> is locations/global/agents/<AGENT_ID>`. Sessions name the project by number, so a full name copied from one fails when you give the project by ID.
- **Custom or shared agents** (e.g. `servicenow-agent`): get the ID from whoever created the agent.

## 6. Set your preferences
```
/cloud-operator:preferences
```
- A short interview covers your default project (your operator project from section 5), region, naming, change policy and so on. It's saved to `~/.config/cloud-operator/preferences.md`.
- Claude reads the preferences before the first operator call of a conversation and sends them with it. They're also synced to the operator's own memory. The installer lets Claude read the file without asking (`Read(~/.config/cloud-operator/**)` in `permissions.allow`).
- Add one preference at any time, for example: `/cloud-operator:preferences always use europe-west4`.
- To pin an operator agent, see section 5.

## 7. Verify it works
Ask Claude something only the operator can answer, for example:
> What Cloud Run services are running in project <AGENT_PROJECT>, and in which regions?

You should see Claude invoke the `cloud-operator:autocloud-operator` skill and call `ask_cloud_operator`. Calls can take several minutes.

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `register-mcp.sh` says the credentials file has no `client_secret` | Use the file you downloaded from the dialog that opened when you created the client: the Console includes the client secret only there. If you no longer have it, create a new client (4.3) and download its file before you close the dialog |
| `register-mcp.sh` says it cannot read the file: "Operation not permitted" (macOS) | Your terminal app has no access to that folder. Allow it in System Settings > Privacy & Security > Files and Folders, or move the file to another folder |
| `redirect_uri_mismatch` / "doesn't comply with Google's OAuth 2.0 policy … register the redirect URI" during login | With an existing Web application client, run `register-mcp.sh --callback-port <PORT>` with the port of its redirect URI (`http://localhost:<PORT>/callback`), listed under **Authorized redirect URIs** in the client's settings. Otherwise, first check the client is a **Desktop app** (4.3): Desktop clients accept whatever local port Claude Code picks. If the error persists, use a **Web application** client with a **fixed port**. (1) Create a Web application client with `http://localhost:3118/callback` under **Authorized redirect URIs**. (2) Repeat 4.4 with its client ID/secret and add `"callbackPort":3118` inside `"oauth"`: `"oauth":{"clientId":"<CLIENT_ID>","callbackPort":3118}`, or run `register-mcp.sh --callback-port 3118`. Pinning the port keeps the registered URI matching. Wait 2–5 minutes after console changes, then retry |
| "Access blocked: … has not completed the Google verification process" / "access_denied" | External app: add your email under **Test users** (4.2) and sign in with that account. If someone else owns the client, ask the client's owner to add your account as a test user |
| "… can only be used within its organization" | Internal app, but you signed in with an account outside the organization. Use an account in the client's organization, or ask the client's owner to add your account (as a test user if it is External) |
| Authentication errors after about a week | External app in Testing (7-day refresh tokens): re-authenticate with `/mcp` → autocloud → **Authenticate** |
| `claude mcp get autocloud` shows "Needs authentication", or the tool returns 401 | Run `/mcp` → autocloud → **Authenticate** again. Using the access-token setup (4.6)? Re-run its `add-json` line (tokens last about 1 hour) |
| "The caller does not own agent …" | The pinned agent ID isn't yours or belongs to another project. Remove it from `~/.config/cloud-operator/preferences.md`, or replace it with yours (section 5) |
| "personal operator agent for project … has not been initialized yet" | You don't have an operator agent in that project yet. Create it (section 5), or check that you gave the right project. If you just created it, wait a few minutes and retry |
| "agent … is not ready to serve yet; it is probably still being provisioned" | Your new agent is still being set up. Wait about a minute and retry, up to 3 times. If it still fails, check that the agent shows on the Cloud Operator home page. If it does and calls still fail, ask your admin |
| 403 / permission denied that persists after re-authenticating | Your account may lack access to the target project, or the Gemini Cloud Assist API isn't enabled there. Check with the project owner and re-run 4.1 for that project |
| The `autocloud` MCP server isn't listed in `/mcp` | Restart Claude Code. Check `claude mcp list` and remove any local/project-scope `autocloud` MCP server entry |
| Errors like "Failed to send connect request" or "Request throttled" | Server-side; retry after a minute or two |
| Claude answers GCP questions itself instead of using the operator | Check the plugin is enabled (`claude plugin list`). Remove any standalone copy of the skill (`~/.claude/skills/autocloud-operator`), which competes with the plugin's skill |
| Generated files appear only in chat | Ask "save those files", and please report it: the skill should save them automatically |

## 9. Update or remove
```bash
# Update: re-run the installer, then restart Claude Code. Your server, sign-in and preferences stay.
curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/main/plugins/cloud-operator/claude/install.sh | bash
# Remove the plugin, the autocloud server and your sign-in. Your preferences stay in ~/.config/cloud-operator/.
curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/main/plugins/cloud-operator/claude/install.sh | bash -s -- --uninstall
```
