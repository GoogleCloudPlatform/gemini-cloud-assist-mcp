---
description: Set up Cloud Operator — log in to Cloud Console, create an OAuth client, register the autocloud MCP server, and bootstrap GCP preferences
argument-hint: "[gcp-project-id]"
---

Walk the user through Cloud Operator setup one step at a time. Wait for the user to confirm each console step before moving on. Run shell commands yourself where noted; never ask the user to do something you can do.

Constants:
- MCP server name: `autocloud`
- Endpoint: `https://geminicloudassist.googleapis.com/mcp/autocloud`
- OAuth client type, if the user creates a new client: **Desktop app** (Claude Code uses a random localhost callback port; Desktop clients accept any loopback port, Web clients don't)
- Tool timeout: `1800000` ms (30 minutes)
- Registration script: `${CLAUDE_PLUGIN_ROOT}/scripts/register-mcp.sh`

## Step 0 — Check current state and read the onboarding guide

The plugin ships an onboarding guide, `${CLAUDE_PLUGIN_ROOT}/onboarding.md`. It holds the details and the troubleshooting table. **Read it now**, and read its Troubleshooting section whenever a step below fails.

Run `claude mcp get autocloud`. If its URL isn't the Endpoint above, register the server again in Step 3 with the user's existing OAuth client, even if it reports "Connected", then skip the steps that are already done. Otherwise, if it reports "Connected", tell the user the autocloud MCP server is already set up and skip to Step 3b, which checks their operator project and agent, then Step 4 (offer to update preferences). If an `autocloud` server exists in **local** or **project** scope, note it — it would shadow the user-scope server this setup creates — and offer to remove it at the end.

## Step 1 — Choose the OAuth client project

First, ask whether the user already has an OAuth client. If they have the OAuth client credentials JSON file, ask where it is and skip to Step 3, path **File**. If they have only the client ID and secret, skip to Step 3, path **Prompt**. Check two things first.
- Ask whether it's a **Desktop app** or a **Web application** client. For a Web application client, ask for the port in its redirect URI, `http://localhost:<PORT>/callback`, listed under **Authorized redirect URIs** in the client's settings, and add `--callback-port <PORT>` to the registration command in Step 3.
- An existing client only signs in the accounts its owner allows. The owner must add the user's account as a test user of an External client, or the account must belong to the organization of an Internal one.

Otherwise, this project only hosts the user's OAuth client (`<PROJECT>` in Steps 1–2); it must have the Gemini Cloud Assist API enabled. It doesn't have to be the project the operator will work in (where the user's agent is); Step 3b asks for that separately. Use `$ARGUMENTS` if given, otherwise ask for the OAuth client project, and say that the same project is fine if it's where they'll run the operator.

1. Run `gcloud config get-value account`. If gcloud is missing or not logged in, tell the user to run `! gcloud auth login` and wait.
2. Run `gcloud services list --enabled --project <PROJECT> --filter="config.name:geminicloudassist.googleapis.com" --format="value(config.name)"`.
3. If the API is not enabled, ask permission, then run `gcloud services enable geminicloudassist.googleapis.com --project <PROJECT>`.

## Step 2 — Create the OAuth client and download its credentials JSON file

Tell the user to open (substituting the project ID), logged in with the Google account they will use for the autocloud MCP server:

https://console.cloud.google.com/auth/clients/create?project=<PROJECT>

- If the Console first asks them to configure Google Auth Platform (the consent screen), fill only the required fields and save. Choose the audience:
  - **Internal** if the project belongs to their own organization and only its users need access. No test users needed.
  - Otherwise **External**: add their own email under **Test users**. Warn them that:
    - refresh tokens for External apps in Testing expire after 7 days, so they'll need to re-authenticate weekly;
    - at login they'll see an "unverified app" screen; it's their own app, so they can continue.
- Application type: **Desktop app** (not Web application — Claude Code's login callback uses a random localhost port, which only Desktop clients accept)
- Name: `claude-code-cloud-operator`
- Before they click **Create**, warn them that the Console shows the client secret only once, in the dialog that opens after **Create**: they must click **Download JSON** there, before closing the dialog, to save the credentials JSON file. The file holds the client secret. To keep it, and to share the client with teammates, they can store the file in Secret Manager: https://docs.cloud.google.com/secret-manager/docs/overview
- Click **Create**, then **Download JSON**. They don't need to copy the client ID or secret, and shouldn't paste either here.

When they've downloaded the file, go to Step 3, path **File**.

## Step 3 — Register the MCP server

Register the server with the registration script, keeping the client secret out of this conversation. Use the path for the user's case:

- **File** (they have the OAuth client credentials JSON file, from Step 2 or from elsewhere). Find out where it is: in their Downloads folder (`~/Downloads`), or elsewhere (they give the path). Work out its absolute path. If it's in `~/Downloads` and they don't know its name, list the JSON files there (`ls -t ~/Downloads/*.json`) and ask which one it is, or ask for its path (if they give a relative path, work out the absolute path from it). Never open, read, print, copy or move the file yourself: the script reads it.

  Offer to run the script for them. It reads the client ID and secret from the file and prints only the client ID, so the secret stays out of this conversation. Keep `--no-login`: your shell has no terminal for the sign-in, so they sign in from `/mcp` after the restart.

  ```bash
  bash "${CLAUDE_PLUGIN_ROOT}/scripts/register-mcp.sh" --client-json "<ABSOLUTE PATH>" --no-login
  ```

  If they'd rather run it themselves, which also signs them in right away, show them this command to run in their own terminal (a new window or tab):

  ```bash
  bash "${CLAUDE_PLUGIN_ROOT}/scripts/register-mcp.sh" --client-json "<ABSOLUTE PATH>"
  ```

- **Prompt** (they have the client ID and secret, but no file). Ask them to run this command in their own terminal (a new window or tab), so the secret stays out of this conversation. It asks for the client ID and secret (the secret is hidden):

  ```bash
  bash "${CLAUDE_PLUGIN_ROOT}/scripts/register-mcp.sh"
  ```

  If they'd rather paste the client ID and secret here, first tell them that the secret then ends up in this conversation: in their message, and in your command that runs the script. If they still want to, run the script yourself with them in `CLOUD_OPERATOR_CLIENT_ID` and `CLOUD_OPERATOR_CLIENT_SECRET`, plus `--no-login` and, for a Web application client, `--callback-port <PORT>`, and don't repeat the secret in your replies.

The script registers the server and, without `--no-login`, signs the user in with `claude mcp login autocloud`, which opens the Google sign-in in the browser. It registers the server like this:

```bash
claude mcp remove autocloud -s user 2>/dev/null
MCP_CLIENT_SECRET='<CLIENT_SECRET>' claude mcp add-json -s user autocloud \
  '{"type":"http","url":"https://geminicloudassist.googleapis.com/mcp/autocloud","timeout":1800000,"oauth":{"clientId":"<CLIENT_ID>"}}' \
  --client-secret
```

When the script has finished, run `claude mcp get autocloud`: expect "Connected", or "Needs authentication" if the user hasn't signed in yet. If a local/project-scope `autocloud` MCP server entry was found in Step 0, offer to remove it now (`claude mcp remove autocloud -s local`).

Then tell the user:
1. Restart Claude Code so it picks up the new server: exit, then run `claude -c` in the same folder to continue this conversation.
2. Run `/mcp` and check that **autocloud** is connected. If it isn't signed in yet (for example, because you ran the script for them), select **autocloud**, choose **Authenticate**, and finish the Google login in the browser.
3. If Google shows `redirect_uri_mismatch` or "doesn't comply with Google's OAuth 2.0 policy … register the redirect URI": with an existing Web application client, rerun the script with `--callback-port` and the port of its redirect URI. Otherwise, first confirm the client is a **Desktop app** (Desktop clients accept any loopback port). If it still fails, switch to a **Web application** client with a fixed port: register `http://localhost:3118/callback` under **Authorized redirect URIs** and save, wait 2–5 minutes, then rerun the script with that client and `--callback-port 3118`, which puts `"callbackPort":3118` inside `"oauth"` (Claude Code otherwise picks a random port, which wouldn't match).

Wait for the user to confirm they are connected. If login fails, match the error against the Troubleshooting table in the onboarding guide, and walk them through the fix.

**Alternative: access token (quick test, or a client without OAuth support).** If the user can't complete the OAuth login, or wants to try Cloud Operator before creating an OAuth client:
1. They run `! gcloud auth application-default login` with the Google account they'll use. A plain `gcloud auth print-access-token` user token is rejected by the server; the Application Default Credentials token works.
2. Register the server with a bearer header (don't echo the token):
   ```bash
   claude mcp remove autocloud -s user 2>/dev/null
   claude mcp add-json -s user autocloud "{\"type\":\"http\",\"url\":\"https://geminicloudassist.googleapis.com/mcp/autocloud\",\"timeout\":1800000,\"headers\":{\"Authorization\":\"Bearer $(gcloud auth application-default print-access-token)\"}}"
   ```
3. Tell the user the token **expires after about 1 hour** and doesn't refresh. Re-run step 2 when calls fail with "invalid authentication credentials". The token is stored in plain text in `~/.claude.json`. For daily use, finish the OAuth setup above, which refreshes automatically.

## Step 3b — Choose the operator project and agent

Once **autocloud** shows as connected:

1. Ask which project the operator should work in: the project where their operator agent is, or will be. It can differ from the OAuth client project. Call it `<AGENT_PROJECT>`. Check the Gemini Cloud Assist API is enabled there (Step 1, items 2–3). If that check fails with a permission error because gcloud is signed in with a different account than the autocloud MCP server, skip it, since the call in item 3 checks access with the MCP server's account.
2. Ask which agent to use:
   - **Personal agent (default):** calls without `agentId` go to the user's **personal operator agent** in `<AGENT_PROJECT>`, which is right for most users. Don't pin it; there's nothing to save.
   - **A specific agent ID:** the user pastes it. Custom or shared agents (e.g. `servicenow-agent`) come from whoever created them; don't guess. Accept a bare ID, `locations/<loc>/agents/<ID>` or a full resource name, and keep it as `locations/<loc>/agents/<ID>` (a bare ID becomes `locations/global/agents/<ID>`), without the `projects/<p>/` prefix. If it had one, check that `<p>` is `<AGENT_PROJECT>`: it may be the project number, so compare with `gcloud projects describe <AGENT_PROJECT> --format="value(projectId,projectNumber)"`. If it doesn't match, tell the user the agent belongs to another project, and ask which project to use.

   Agent IDs are **per user and per project**: an agent that belongs to someone else, or to another project, fails with "The caller does not own agent …".
3. Check that the agent answers. Make one harmless `ask_cloud_operator` call with `project: projects/<AGENT_PROJECT>`, for example "In one line, what can you help me with in this project? Don't create anything." Tell the user first that it can take 1 to 3 minutes while the operator starts. Leave out `agentId` for the personal agent, and pass the pasted ID for a specific agent. If it answers, keep the `context_id` for item 4 and move on. If the personal agent call fails with "personal operator agent for project … has not been initialized yet", the user has no agent in that project yet. Walk them through creating it, one step at a time.
   - Open the Cloud Operator page in Cloud Console. Use the Cloud Operator link from their admin if they have one, otherwise `https://console.cloud.google.com/autocloud/home?project=<AGENT_PROJECT>`. Sign in with the account they use for the autocloud MCP server. A private or incognito window helps if the browser is signed in to another account.
   - Click **Create operator agent**. When the dialog says "Your operator agent is ready", click **Get started**. The agent is theirs alone, one per user and project.
   - If the page shows a permission error, their account has no access to the project yet. Their admin grants it with the Gemini Cloud Assist User role, `roles/geminicloudassist.user`, and new access can take a few minutes to apply.

   When they're done, repeat the harmless call. A new agent can take a few minutes to become ready, and until then the call fails with "has not been initialized yet" or "agent … is not ready to serve yet". If so, wait about a minute and try again, up to 3 times. If it still fails, ask the user to check that the agent shows on the Cloud Operator home page. If it does and calls still fail, they should ask their admin. For other errors, use the Troubleshooting table in the onboarding guide.
4. To show the user their personal agent ID (if they ask, or to confirm a pasted ID):
   - Call `mcp__autocloud__search_operator_sessions` with `project: projects/<AGENT_PROJECT>`. Each session's `contextId` has the form `projects/<AGENT_PROJECT>/locations/global/agents/<AGENT_ID>/sessions/<SESSION_ID>`, with the project usually given by number.
   - If there are no sessions yet, read the `context_id` from the call in item 3.
   - Report the agent as `locations/global/agents/<AGENT_ID>` in project `<AGENT_PROJECT>`. Don't pass or save the full name from a session: its project number doesn't match a project ID in `project`, and the call fails with "invalid argument".

## Step 4 — Bootstrap GCP preferences

Run the `/cloud-operator:preferences` flow so the operator starts with the user's context. Pass along `<AGENT_PROJECT>` as the default project and, only if the user picked a specific agent, that agent as `locations/<loc>/agents/<ID>` **with its project**, because it's only valid there. When done, summarize: account, OAuth client (one they created, with its project, or an existing one), operator project, MCP status, agent (personal default, noting if setup created it, or the pinned ID), preferences file location (`~/.config/cloud-operator/preferences.md`), the onboarding guide to keep for reference, and how to use it ("just ask me to do things in GCP").
