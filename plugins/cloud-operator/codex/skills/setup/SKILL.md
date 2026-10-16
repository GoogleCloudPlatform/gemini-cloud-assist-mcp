---
name: setup
description: "Set up Cloud Operator in Codex: use an existing OAuth client or create one in Cloud Console, register the autocloud MCP server (30-minute tool timeout) and sign in, choose the operator project and agent (creating the agent in Cloud Console if you don't have one) and verify it, and bootstrap GCP preferences. Also use to continue setup after the Codex restart. Use when the user asks to set up, install, connect or troubleshoot Cloud Operator, AND whenever a GCP request needs ask_cloud_operator but the autocloud MCP server or the ask_cloud_operator tool isn't available or isn't authenticated: run this skill to guide the user through connecting instead of only reporting that it failed."
---

If you got here because a GCP request couldn't reach `ask_cloud_operator`, say so in one line, then start at Step 0; after setup, return to the user's original request.

Walk the user through Cloud Operator setup one step at a time. Ask at most two questions per message, and wait for the answers before asking more. Wait for the user to confirm each console step before moving on. Run shell commands yourself where noted; never ask the user to do something you can do.

For console steps, tell the user which page to open, what to enter, and what they'll see when it's done. Don't mention or link this skill.

Constants:
- MCP server name: `autocloud`
- Endpoint: `https://geminicloudassist.googleapis.com/mcp/autocloud`
- OAuth client type, when the user creates one: **Desktop app** (Codex signs in through a localhost callback; Desktop clients accept any loopback port, Web clients don't)
- Tool timeout: `1800` s (30 minutes)
- Codex CLI (ships with the ChatGPT app): `/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex`. Below, `codex` means this path if `codex` isn't on `PATH`.
- Registration script: `scripts/register-mcp.sh` in this plugin, under the installed plugin folder: `~/.codex/plugins/cloud-operator/scripts/register-mcp.sh`.
- Preferences file: `~/.config/cloud-operator/preferences.md`. The operator skill reads it and sends it with the first `ask_cloud_operator` call of each conversation.
- Setup marker: `~/.config/cloud-operator/setup-pending`. The registration script creates it in Step 4, before the Codex restart, and Step 0 checks it when the user says "continue Cloud Operator setup" afterwards.
- Cloud Operator page in Cloud Console: `https://console.cloud.google.com/autocloud/home?project=<AGENT_PROJECT>`.

## Step 0: Check the current state

1. Run `codex mcp get autocloud`.
   - If its URL isn't the Endpoint above, register the server again in Step 4 with the user's existing OAuth client, even if `ask_cloud_operator` is available. Step 4 then has them restart Codex, and Step 4b checks their operator project and agent.
   - Check whether the `ask_cloud_operator` tool is available to you in this session; the user doesn't need to check `/mcp` for you.
   - If it shows the server and `ask_cloud_operator` is available in this session: if `~/.config/cloud-operator/setup-pending` exists, setup is resuming after the restart, so continue at Step 4b. Otherwise tell the user Cloud Operator is already set up, and still run Step 4b, which checks their operator project and agent, then Step 5 (offer to update preferences).
   - If it shows the server but `ask_cloud_operator` isn't available here, Codex hasn't loaded it yet or the sign-in didn't finish: ask the user to run `codex mcp login autocloud` if needed, then restart Codex (the restart steps in Step 4).
   - If `.codex/config.toml` in the current project defines `[mcp_servers.autocloud]`, note it: in a trusted project it overrides the user-level server this setup creates. Offer to remove it at the end (Step 4).
2. Run `codex mcp add --help` and check that it lists `--oauth-client-secret`. If it doesn't, the Codex version is too old: tell the user to update the ChatGPT app first.
3. Run `gcloud config get-value account`. If gcloud is missing or not logged in, tell the user to run `gcloud auth login` and wait. Ask whether they'll sign in to Cloud Operator with this same account. If they'll use a different account, skip the gcloud checks in Steps 1 and 4b, because they would run as the wrong account, and have the user check the same things in the Console instead.

## Step 1: Use an existing OAuth client, or choose the project for a new one

First, unless the user already named a project for a new OAuth client, ask whether they have an existing OAuth client (client ID and secret). If they do, skip to Step 4 with that client, after checking two things:
- Ask whether it's a **Desktop app** or a **Web application** client. For a Web application client, ask for the port in its redirect URI (`http://localhost:<PORT>/...`), because Step 4 needs it. The client's page in Google Auth Platform > Clients shows it.
- An existing client only signs in the accounts its consent screen allows: accounts in the organization that owns the client's project if its audience is **Internal**, or the accounts listed as test users if it's **External** in Testing. If the user's account is neither, it has to be added as a test user on that project, or the user creates a new client (below).

Otherwise, the user creates a new client. Use the project they named, or ask for the project that will host it (`<PROJECT>` in Steps 1–3). It doesn't have to be the project where their operator agent is (Step 4b asks for that separately), and using the same project is simplest.

Calls through the OAuth client count against `<PROJECT>`, so it needs the Gemini Cloud Assist API enabled:

1. Run `gcloud services list --enabled --project <PROJECT> --filter="config.name:geminicloudassist.googleapis.com" --format="value(config.name)"`.
2. If the Gemini Cloud Assist API is not enabled, ask permission, then run `gcloud services enable geminicloudassist.googleapis.com --project <PROJECT>`.

## Step 2: Log in to Cloud Console and configure the consent screen

Pick the audience by who will sign in, not by the type of account:
- **Internal** if the project is in an organization and everyone who'll sign in is in it (e.g. a Workspace account with a project in its own organization). If Internal is greyed out, use External.
- Otherwise **External**, with the user added as a test user. Tell them they'll sign in again every 7 days (`codex mcp login autocloud`) and may see an "unverified app" screen, which is safe to continue.

Give the user these instructions, with `<PROJECT>`, their email and the audience filled in:

1. Open https://console.cloud.google.com/auth/overview?project=<PROJECT>, signed in as the account they'll use for Cloud Operator.
2. If the page shows an overview with metrics and a left menu (Branding, Audience, Clients), the consent screen already exists. Skip to item 4.
3. If it shows **Get started**, click it and fill in the four sections:
   - **App information:** App name `codex-cloud-operator`; User support email: their email. Click **Next**.
   - **Audience:** choose **Internal** or **External** (as decided above). Click **Next**.
   - **Contact information:** their email. Click **Next**.
   - **Finish:** tick the box agreeing to the Google API Services User Data Policy, click **Continue**, then **Create**. The overview page appears.
4. For **External** only: open https://console.cloud.google.com/auth/audience?project=<PROJECT>, check the publishing status says **Testing**, and under **Test users** click **Add users**, enter their email and click **Save**. Their email now appears in the test users list.
5. Reply "done" when the overview page shows, and say which audience the consent screen has: **Internal** or **External** (shown on https://console.cloud.google.com/auth/audience?project=<PROJECT>). For External, their email must be in the test users list.

## Step 3: Create the OAuth client in that project

Give the user these instructions, with `<PROJECT>` filled in:

1. Open https://console.cloud.google.com/auth/clients/create?project=<PROJECT>.
2. **Application type:** **Desktop app** (not Web application).
3. **Name:** `codex-cloud-operator`.
4. Click **Create**. Keep the dialog with the **Client ID** and **Client secret** open, or click **Download JSON**; the next step asks for both.
5. Reply "done" when they have the client ID and secret. They shouldn't paste them here.

## Step 4: Register the MCP server

Ask the user to run the registration script **in their own terminal** (a new terminal window or tab), so the client secret stays out of this conversation:

```bash
bash ~/.codex/plugins/cloud-operator/scripts/register-mcp.sh
```

For a Web application client, such as an existing one from Step 1, add `--callback-port <PORT>` with the port from its redirect URI.

It asks for the client ID and secret (the secret is hidden), writes `[mcp_servers.autocloud]` to `~/.codex/config.toml` (URL, the `cloud-platform` scope, `tool_timeout_sec = 1800`, `startup_timeout_sec = 30`, `enabled_tools = ["ask_cloud_operator", "search_operator_sessions", "fetch_operator_session"]`, and the OAuth client), then runs `codex mcp login autocloud --scopes https://www.googleapis.com/auth/cloud-platform`, which opens the Google sign-in in the browser. (It doesn't use `codex mcp add`, which starts the sign-in without a scope; Google rejects that with "Missing required parameter: scope".)

If the user prefers to paste the client ID and secret here, first tell them that the secret then ends up in this conversation: in their message, and in your command that runs the script. If they still want to, run the script yourself with them in `CLOUD_OPERATOR_CLIENT_ID` and `CLOUD_OPERATOR_CLIENT_SECRET`, plus `--no-login` (your shell can't open the browser sign-in for them) and, for a Web application client, `--callback-port <PORT>`. Don't repeat the secret in your replies. They sign in afterwards with `codex mcp login autocloud`.

When the script has finished, run `codex mcp get autocloud` and check the server is there (the script also creates the setup marker). If a project-level `autocloud` MCP server entry was found in Step 0, offer to remove it now. Then tell the user:
1. If sign-in didn't finish in the browser (for example, because they pasted the client here), run `codex mcp login autocloud` in their terminal and complete the Google login.
2. Restart Codex so it loads the new server: quit (Cmd+Q) and reopen the desktop app, or start a new CLI session. They can continue in either one; both use the same `~/.codex` configuration.
3. In a new chat, type `@cloud-operator`: the Cloud Operator plugin shows in the list, which confirms it's installed. Pick it and say **"continue Cloud Operator setup"**. Setup checks that the autocloud tools are loaded, then picks up at Step 4b: the operator project and agent, then preferences. (In the Codex CLI, `/mcp` also lists the server's tools.)

If sign-in fails:
- `redirect_uri_mismatch` or "doesn't comply with Google's OAuth 2.0 policy … register the redirect URI": with an existing Web application client, rerun the script with `--callback-port` and the port of the redirect URI registered on it. Otherwise, first confirm it's a **Desktop app** (Desktop clients accept any loopback port). If it still fails, switch to a **Web application** client with a fixed port: register `http://localhost:3118/callback` under **Authorized redirect URIs** and save, wait 2–5 minutes, then rerun the script with that client and `--callback-port 3118`. In either case, Google's error page shows the exact redirect URI Codex sent; if its path differs, register that exact URI on the client.
- "Missing required parameter: scope": the server entry has no `scopes`; rerun `register-mcp.sh`, or run `codex mcp login autocloud --scopes https://www.googleapis.com/auth/cloud-platform`.
- `access_not_configured`, `org_internal` or "access blocked": the client's audience doesn't allow the account. Add the account as a test user on the client's project (Step 2), or ask whoever manages that project to.
- Calls later fail with "invalid authentication credentials": run `codex mcp login autocloud` again.

## Step 4b: Choose the operator project and agent, and verify it

After the restart, with `ask_cloud_operator` available:

1. **Project (always required).** Ask for the project where the operator will run: the project where the user already has an operator agent, or where they want to create one. It can differ from the OAuth client project. Call it `<AGENT_PROJECT>`. Don't assume `gcloud config get-value project`; offer it only as a suggestion. Check the Gemini Cloud Assist API is enabled there (Step 1, items 1–2), because the operator works in this project; skip the check if it's the OAuth client project you already checked in Step 1. If that check fails with a permission error because gcloud is signed in with a different account than Cloud Operator, skip it, since the calls in item 4 check access with the Cloud Operator account.
2. Ask whether they already have an operator agent in `<AGENT_PROJECT>`.
   - **Yes:** ask whether to use their **personal agent** (the default; right for most users) or **a different agent**. For a different agent, they paste its ID or a link to it. Custom or shared agents (e.g. `servicenow-agent`) come from whoever created them; don't guess.
   - **No, or not sure:** they create one now. Give them the Cloud Operator page link (see Constants) and walk them through it, one step at a time:
     - Open the link and sign in with the account they use for Cloud Operator. A private or incognito window helps if the browser is signed in to another account.
     - A dialog may ask whether to share data to improve the product. Either choice is fine, and it doesn't block them.
     - If the page already shows an operator agent, skip creation and continue to item 4; the harmless call there returns its ID.
     - Otherwise click **Create operator agent**. When "Your operator agent is ready" appears, click **Get started**, which opens the Cloud Operator home page. The agent is theirs alone, one per user and project.
     - If the page shows a permission error, their account has no access to the project yet. They ask their admin for `roles/geminicloudassist.user` on the project; new access can take a few minutes to apply.
     - When it's created, ask them to paste the agent's link (the address bar of the agent or session page) or its ID.
3. **Read the agent from what they pasted.** Accept a bare ID, `locations/<loc>/agents/<ID>`, a full resource name, or a Cloud Console link:
   - A link to the agent page looks like `https://console.cloud.google.com/autocloud/agents/<ID>?project=<P>`; a session link contains `projects/<p>/locations/global/agents/<ID>/sessions/…`. Take `<ID>` from the `agents/<ID>` segment.
   - Keep it as `locations/<loc>/agents/<ID>` (a bare ID becomes `locations/global/agents/<ID>`), without the `projects/<p>/` prefix.
   - If the link or name carries a project (`?project=<P>` or `projects/<p>/`), check that it is `<AGENT_PROJECT>`: it may be the project number, so compare with `gcloud projects describe <AGENT_PROJECT> --format="value(projectId,projectNumber)"`. If it doesn't match, tell the user the agent belongs to another project and ask which project to use.
   - If the link has no agent ID (for example, the Cloud Operator home page), treat it as the personal agent.

   Agent IDs are **per user and per project**: an agent that belongs to someone else, or to another project, fails with "The caller does not own agent …" or may hang.
4. **Verify the agent, and whether it's the personal (default) one.**
   - Make one harmless `ask_cloud_operator` call with `project: projects/<AGENT_PROJECT>` and no `agentId`, for example "In one line, what can you help me with in this project? Don't create anything." Tell the user the check can take a minute or two. Its `context_id` has the form `projects/<p>/locations/global/agents/<PERSONAL_ID>/sessions/<SESSION_ID>`; `<PERSONAL_ID>` is their personal agent. (`search_operator_sessions` with the same `project` also lists their sessions and agent.)
   - If it fails with "personal operator agent for project … has not been initialized yet", the user has no personal agent in that project yet. Walk them through creating it (item 2, "No"), then repeat the call.
   - Right after creation, the call can fail with "agent … is not ready to serve yet; it is probably still being provisioned", or still say the agent isn't initialized: a new agent takes 1–3 minutes to become ready. Wait a minute and repeat the call, at most 3 times. If the Cloud Operator home page shows the agent and calls still fail, tell the user to ask their admin.
   - **Personal agent chosen:** the call verified it. Report it as `locations/global/agents/<PERSONAL_ID>` in project `<AGENT_PROJECT>`. Don't pin it; there's nothing to save.
   - **Agent pasted:** if its ID equals `<PERSONAL_ID>`, it **is** the personal (default) agent: tell the user, and treat it as the personal agent (no `agentId`). If it's different, it's a separate agent: make the same harmless call with `agentId: locations/global/agents/<AGENT_ID>`. If that answers, keep it as their agent. If it fails or runs much longer than a couple of minutes (a mismatch can hang until the 30-minute timeout instead of failing, so the user can stop the turn), tell the user the agent doesn't belong to them or to this project, and offer to switch to the personal agent.
   - Don't pass or save the full name from a session: its project number doesn't match a project ID in `project`, and the call fails with "invalid argument".
   - A permission error (`PERMISSION_DENIED` or 403) means the account lacks `roles/geminicloudassist.user` on `<AGENT_PROJECT>`: the user asks their admin for it.
   - For other errors, match them against the sign-in list in Step 4.

## Step 5: Bootstrap GCP preferences

Run the preferences skill so the operator starts with the user's context: its bootstrap interview, then its "Sync to the operator" step. Pass along `<AGENT_PROJECT>` as the default project and, only if Step 4b settled on a separate (non-personal) agent, that agent as `locations/<loc>/agents/<ID>` **with its project**, because it's only valid there.

Then run `rm -f ~/.config/cloud-operator/setup-pending`, and summarize: account, OAuth client (new or existing, with its project), operator project, MCP status, agent (personal default, noting if setup created it or if a pasted agent turned out to be the personal one, or the separate agent's ID), preferences file location (`~/.config/cloud-operator/preferences.md`), and how to use it ("just ask me to do things in GCP"). If the user came here from a GCP request, return to it.
