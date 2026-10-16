---
name: setup
description: Health check for the Cloud Operator plugin's own connection - default project, Application Default Credentials quota project, and an ask_cloud_operator smoke call - plus saved preferences. Use only when the user runs /cloud-operator:setup or asks to set up or verify the Cloud Operator plugin, not for the user's own GCP auth, API or IAM problems.
---

# Cloud Operator plugin setup

Run the checks below, fix what you can, and end with a status table. Ask the
user only when a step needs them. None of the checks need the `gcloud` binary
(Antigravity reads ADC itself); when a fix needs `gcloud`, tell the user to run
it in their own terminal.

## 1. Default project

Read the active gcloud configuration's project from its config file:

```sh
CFG="${CLOUDSDK_CONFIG:-$HOME/.config/gcloud}"; echo "${CLOUDSDK_CORE_PROJECT:-$(sed -n 's/^project *= *//p' "$CFG/configurations/config_${CLOUDSDK_ACTIVE_CONFIG_NAME:-$(cat "$CFG/active_config" 2>/dev/null || echo default)}" 2>/dev/null)}"
```

If it's empty, the user runs `gcloud config set project <project-id>` (the
project their Operator agent lives in, or will live in); until then, ask them
which project to use.

## 2. ADC file and quota project

Read only the `type` and `quota_project_id` fields of the ADC file. **Never
print the whole file**: it contains a refresh token. If the command below
prints nothing, treat it as no quota project; don't open the file any other
way.

```sh
ADC="${GOOGLE_APPLICATION_CREDENTIALS:-${CLOUDSDK_CONFIG:-$HOME/.config/gcloud}/application_default_credentials.json}"
if [ -f "$ADC" ]; then grep -oE '"(type|quota_project_id)": *"[^"]*"' "$ADC"; else echo NO_ADC_FILE; fi
```

- `NO_ADC_FILE` → the user runs `gcloud auth application-default login`, then
  restarts Antigravity.
- No `quota_project_id` → the user runs
  `gcloud auth application-default set-quota-project <project-id>` (needs
  `serviceusage.services.use` on that project), then restarts Antigravity.

## 3. Smoke test

Check that an MCP server whose name ends in `autocloud` is connected and lists
`ask_cloud_operator`. If not, turn the plugin on in `/plugin` (a new install
can start disabled), check **... > MCP Servers**, and restart Antigravity.

Call `ask_cloud_operator` with `project` set to `projects/<default project>`
and `userQuery` set to `Hello. In two sentences, confirm which project you are
operating in and list the capabilities you offer.` Expect a reply and a
`context_id`; the first call can take 1-3 minutes while a sandbox warms up.
Then call `search_operator_sessions` for the same project; the hello session
should be the newest by `createTime`.

On failure:

- `401` → the credentials expired or were revoked: the user runs
  `gcloud auth application-default login`, then restarts Antigravity.
- `403` `SERVICE_DISABLED` ("has not been used in project ... or it is
  disabled") → the user enables the API on the quota project
  (`gcloud services enable geminicloudassist.googleapis.com --project <id>`,
  which needs `gcloud auth login`), or switches to a project that has it with
  `gcloud auth application-default set-quota-project`.
- `403` saying a quota project is required → set one as above. If the ADC file
  already has one, add `"headers": {"x-goog-user-project": "<id>"}` to the
  server in the plugin source's `mcp_config.json`, reinstall the plugin, and
  restart Antigravity. (Edits to the installed copy are lost on reinstall.)
- `403` about `serviceusage.services.use` → the user needs
  `roles/serviceusage.serviceUsageConsumer` on the quota project.
- Any other `403` / `PERMISSION_DENIED` → the user needs
  `roles/geminicloudassist.user` on the project; their admin grants it, and
  new access can take a few minutes to apply.
- `personal operator agent for project ... has not been initialized yet` →
  the user has no Operator agent in this project yet. Walk them through
  creating one, a step at a time:
  1. Open `https://console.cloud.google.com/autocloud/home?project=<default project>`,
     signed in with the account they use for Cloud Operator (a private window
     helps if the browser is signed in to another account). A permission
     error there means they need `roles/geminicloudassist.user`, as above.
  2. If the page already shows an operator agent, skip to 3. Otherwise click
     **Create operator agent**, then **Get started** when "Your operator
     agent is ready" appears.
  3. Repeat the smoke call. A new agent takes 1-3 minutes to become ready;
     until then the call fails as above or with `agent ... is not ready to
     serve yet`. Wait about a minute and retry, at most 3 times. If it still
     fails while the page shows the agent, the user asks their admin.
- Times out well before 30 minutes → `timeoutSeconds` in `mcp_config.json`
  wasn't applied; restart Antigravity.
- Server stuck connecting → check the network and credentials. With the
  30-minute timeout it can take that long to report an error.

## 4. Preferences

- If `~/.config/cloud-operator/preferences.md` has content,
  call `fetch_operator_session` for the hello session and check that its first
  message includes them under `User preferences:`.
- If no preferences are saved, ask whether to run `/cloud-operator:preferences`
  now. Don't run it unprompted.

## 5. Report

Print a table (check · result · fix), then one line saying that GCP requests now
go to the Operator Agent automatically.
