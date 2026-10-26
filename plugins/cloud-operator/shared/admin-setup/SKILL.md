---
name: admin-setup
description: One-time Cloud Operator (AutoCloud) organization admin setup for a Google Cloud organization and its central management project - admin roles, the Admin Onboarding Console, APIs, the users group and its IAM roles, the agent principal set, the org policy override, data egress policies, optional Model Armor, the UAP egress policy and the App Hub boundary - checking each step first and asking before every change. Use only when the user runs /cloud-operator:admin-setup (optionally with "status") or asks to onboard, set up or check Cloud Operator / AutoCloud for their organization as an admin. Not for connecting a coding agent to Cloud Operator (use setup) and not for everyday Google Cloud questions.
---

# Cloud Operator organization admin setup

You're guiding an organization administrator through the one-time setup that
lets their users create Cloud Operator (AutoCloud) agents. The admin works in
their **own** Google Cloud organization with their **own** identity, and is
trusting you with organization-wide IAM and policy changes. Be careful, explain
everything, and never change anything they haven't approved.

Run the steps here yourself with local `gcloud` and shell commands. Don't send
any of them to `ask_cloud_operator`: the operator agent doesn't exist yet, and
it's read-only anyway.

## Files

`<SKILL_DIR>` is the folder that holds this `SKILL.md`.

| File | What it's for |
| --- | --- |
| `<SKILL_DIR>/references/steps.md` | **Read before starting.** What each step does and why, the role it needs, and its exact check, change and verify commands. |
| `<SKILL_DIR>/references/troubleshooting.md` | **Read whenever a command fails.** Error → cause → workaround, and the escalation summary. |
| `<SKILL_DIR>/scripts/admin-status.sh` | Read-only checks against the live org and project: `admin-status.sh <check> --org <ORG> --project <P> [inputs]`, or `all` for the full table. Never changes anything in Google Cloud. |
| `<SKILL_DIR>/scripts/log-run.sh` | Runs one approved change and appends it to the change log: `log-run.sh "<step>" --org <ORG> --project <P> -- <command>`. |
| `<SKILL_DIR>/scripts/bootstrap-agent-identity-pool.sh` | Makes Vertex AI create the organization's agent identity pool (temporary Agent Engine instance, deleted afterwards) when Step 5 or 10 fails with `Identity Pool does not exist` / `Failed to resolve policy members`. Run it through `log-run.sh`, only after the admin agrees. |
| `<SKILL_DIR>/scripts/set-modelarmor-enforcement.sh` | Sets the Model Armor template's enforcement type (gcloud has no flag for it). Run it through `log-run.sh`. |
| `<SKILL_DIR>/scripts/paths.sh` | Used by the other scripts to find each org and project's files. Don't run it directly. |
| `<SKILL_DIR>/assets/uap-policy-3p.json` | The UAP egress rules, with `__ORG_ID__` and `__PROJECT_NUMBER__` placeholders. |

Saved per organization and project, in
`~/.config/cloud-operator/admin-setup/<ORG_ID>/<PROJECT_ID>/` (no secrets):

- **`state.env`:** the inputs only (admin account, org name and ID, project
  ID and number, domain, users group, and the admin's Model Armor and editor
  role choices), so a later session doesn't ask again. `admin-status.sh` saves
  whatever inputs you pass it (`--account`, `--org-name`, `--project-number`,
  `--domain`, `--group`, `--member-type`, `--editor-roles`, `--model-armor`)
  and reads them back next time.
- **`changes.log`:** written by `log-run.sh`, one line per change: time,
  account, step, result, command, error. The admin's security team can review
  it.

Rules for these files:

- **Never create, write or edit them yourself** (no file-editing tools, no
  `echo >`, no `cat <<EOF >`). The scripts manage them as part of commands
  you're running anyway, so the admin isn't asked to approve file writes.
- **Always pass `--org <ORG> --project <P>`** to both scripts. That's how they
  pick this organization's files; different orgs and projects never share
  them, and nobody has to move or rename anything.
- **Status always comes from live checks.** `admin-status.sh` calls gcloud and
  the IAM API every time. Never decide a step is done from the state file, the
  change log or an earlier session: run the check.

## Arguments

- No argument: the full guided setup.
- `status`: get the inputs (from values the admin gave with the command, a
  saved setup they pick, or by asking, as in Step 0; never by searching), run
  `admin-status.sh summary` once, print its table as the reporting rules say,
  list the steps still to do, and stop. Don't change anything.

**Ask, don't search.** Never run commands to discover the organization name
or ID, the project ID or number, or the admin account before asking the admin
for them. Ask for
everything missing in one message, and look a value up only if the admin says
they don't know it (`references/steps.md`, Step 0). If a lookup fails, ask
instead of trying again another way.

## Safety rules (always apply)

1. **Nothing changes without a yes.** Before every change, show the exact
   commands and ask: `Run these now? (yes / no / skip / show-only)`.
   - `yes`: run them through `log-run.sh`, then verify.
   - `no`: don't run them. Ask what they'd like to do instead (change a value,
     stop for now, or skip).
   - `skip`: warn about what won't work without the step, and move on. (The
     final check shows it as still to do.)
   - `show-only`: print the commands for the admin to run in their own
     terminal, wait until they say they've run them, then verify.

   A question like "should I…?" or "what does this do?" isn't approval: answer
   it and ask again.
2. **Real values, never placeholders.** Fill in the admin's org ID, project,
   group and account in every command you show. ORG_ID, MGMT_PROJECT_ID and
   DOMAIN come only from the admin or from gcloud output. Never guess them.
3. **One identity.** Pass `--account=<ADMIN_ACCOUNT>` and `--quiet` to every
   gcloud command, and `--project=<MGMT_PROJECT_ID>` wherever it applies.
   Never run `gcloud config set`, `gcloud auth login` or anything else that
   changes the admin's gcloud configuration. If the account needs signing in,
   ask the admin to run `gcloud auth login <account>` themselves.
4. **Temporary overrides only.** For Model Armor, set
   `CLOUDSDK_API_ENDPOINT_OVERRIDES_MODELARMOR=https://modelarmor.us.rep.googleapis.com/`
   in front of that one command. Never persist it.
5. **Temp files.** Create them with `mktemp`, show their contents before using
   them, and delete them afterwards.
6. **Secrets.** Never print access tokens or credential files.
7. **Show the dry run first.** Where a command has `--validate-only`, run that
   first and show the result.
8. **Idempotent.** `ALREADY_EXISTS` counts as done: verify and move on.
9. **IAM takes time.** After any IAM or org policy change, a check can fail
   for 1-7 minutes while the change spreads. Wait about a minute and recheck,
   up to 3 times, before treating it as a failure.
10. **Stay on the steps.** Don't run extra commands that change things (no
    deleting, no changing other roles or policies) even if they look helpful.
    Suggest them and let the admin decide.

## Reporting rules (always apply)

The script decides every status; you only present it.

1. **Status tables come from `admin-status.sh summary`, printed verbatim.**
   This covers the start table, `status` and the final report. You may add a
   "What to do" column or notes below the table, but never change, add or
   remove a status symbol, and never write a status table of your own.
2. **✅ only where the script printed ✅.** ❔ (`UNKNOWN`, couldn't read)
   is never ✅ and never left out. A step that can't start because an earlier
   step failed is shown as the script printed it, with "blocked by Step N"
   in your "What to do" column.
3. **Evidence is quoted, not paraphrased.** When you say a step is done or
   failed, quote the script's line(s) for it.
4. **Never judge success by exit codes.** The scripts exit 0 whenever the
   checks ran; the result is in the lines. A change counts as done only when
   its verify check prints `OK`.
5. **Every change goes through `log-run.sh`,** with `--org` and `--project`,
   and is followed by its verify check. Don't run a changing gcloud command
   any other way.
6. **Saved choices only from the admin's answers.** Pass `--model-armor`,
   `--editor-roles` or `--member-type` only in the check you run right after
   the admin answers that question, with their exact answer. The summary
   shows these choices, so a ➖ always traces back to a decision.

## How every step looks

Use this layout for each step, so the admin always knows where they are:

```text
── Step <n> of 12: <title> ──
What this does: <one or two plain sentences>
Why AutoCloud needs it: <one sentence>
Needs: <role> on <resource>   (you have it ✅ / you're missing it ❌)
Current state: ✅ already done / ❌ not done / ⚠️ <partial or unexpected>

Commands (run as <account>):
  <exact command 1>
  <exact command 2>

Run these now? (yes / no / skip / show-only)
```

Then:

1. **Check first** with the step's read-only check (usually
   `admin-status.sh <check>`). If it prints only `OK` lines, say so with ✅,
   quote the line(s), and go to the next step without asking. Steps 3 and 9
   have their own rules (`references/steps.md`).
2. **Explain and show** using the layout above, with the details from
   `references/steps.md`.
3. **Ask** and wait.
4. **Run** each approved command with
   `<SKILL_DIR>/scripts/log-run.sh "Step <n>: <short label>" --org <ORG> --project <P> -- <command>`,
   one command at a time, and stop at the first failure.
5. **Verify** with the step's verify check. Tell the admin plainly what
   changed, for example: `✅ Step 5 done: the agent principal set now has
   roles/agentregistry.viewer on my-mgmt-project.`
6. **If it fails:** quote the key error line, look it up in
   `references/troubleshooting.md`, explain the likely cause in plain words,
   and offer the workarounds (retry, show-only, skip, or escalate). Don't
   retry a change more than once without asking.

Keep messages short. Explain more only if the admin asks or something fails.

## The flow

Read `references/steps.md` now. It has the full detail for each step below.

### Start

1. Run `<SKILL_DIR>/scripts/admin-status.sh list`. If it shows saved setups,
   list them and ask whether to continue one of them or set up a different
   organization or project. For a saved one, confirm its values in one line
   and skip to 3.
2. Otherwise, introduce the setup in a few lines: what it does, that it takes
   about 20-40 minutes, that it'll ask before every change, that some changes
   are organization-wide, and that **choosing the management project in the
   Admin Onboarding Console is permanent during Private Preview**. In the same
   message, ask for the five inputs from Step 0 (organization name,
   organization ID, management project ID, management project number, admin
   account). Run nothing until they answer. Then confirm the domain you
   inferred from the admin account.
3. Note the current UTC time as the session start (`date -u
   +%Y-%m-%dT%H:%M:%SZ`); the final report uses it. Do the rest of Step 0, then
   run `admin-status.sh summary` once and print its table (reporting rules).
   Start at the first step that isn't ✅ and say which steps you'll skip
   because they're done.

### Steps

| # | Step | Check | Main change |
| --- | --- | --- | --- |
| 0 | Preflight and inputs | `preflight` | none |
| 1 | Admin roles | `roles` | grant the admin's missing roles (if they can), or draft a request |
| 2 | APIs | `apis` | `gcloud services enable` (missing APIs only) |
| 3 | Admin Onboarding Console | ask the admin (`console` is evidence only) | the admin clicks **Complete setup** (permanent) |
| 4 | Users group and roles | `group`, `user-iam` | create `autocloud-users@<domain>`, add members, grant 4 roles |
| 5 | Agent principal set | `agent-iam` | grant `roles/agentregistry.viewer` |
| 6 | Org policy override | `orgpolicy` | `iam.managed.disableAccessPolicyBinding` → not enforced on the project |
| 7 | Data egress policies | `deps` | PDP and IAP extension bindings |
| 8 | Model Armor (optional, recommended) | `modelarmor` | template in `us` + binding |
| 9 | Check the egress bindings | `deps` + `modelarmor` | none |
| 10 | UAP egress policy | `uap` | create/update the access policy, then bind it |
| 11 | App Hub boundary | `apphub` | `gcloud apphub boundary update` |
| 12 | Final check | `summary --since <session start>` | none |

Order matters: Step 2 (APIs) must be done before Steps 3, 4, 7, 8, 10 and 11,
Step 3 needs Step 1's organization roles, and Step 6 must be done before
Step 10 can bind the policy. If the admin skips a step another one
depends on, say so before moving on.

### Step 12: final report

Run `admin-status.sh summary --org <ORG> --project <P> --since <session start>`
and show:

1. Its step table, verbatim, plus a "What to do" column for every row that
   isn't ✅.
2. Its "Saved choices" lines.
3. Its "Changes since ..." line and the change-log lines under it, quoted.
   These are this session's changes (OK and FAILED).
4. What users do next:
   - Make sure they're in `autocloud-users@<domain>` (members can be added
     later with `gcloud identity groups memberships add` or in the Admin
     console).
   - Open `https://console.cloud.google.com/autocloud/home?project=<MGMT_PROJECT_ID>`,
     signed in with their organization account, choose their data-sharing
     preference, and click **Create My Agent** (about 10-30 seconds).
   - To use Cloud Operator from a coding agent, install the Cloud Operator
     plugin and run its setup command (`/cloud-operator:setup`).
5. A reminder that `/cloud-operator:admin-setup status` rechecks everything.

Don't end with a recap of every step: the table already shows it.
