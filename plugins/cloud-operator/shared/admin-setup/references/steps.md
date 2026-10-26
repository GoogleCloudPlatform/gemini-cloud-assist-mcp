# Admin setup steps

Details for each step in `SKILL.md`. In the commands below:

| Placeholder | Value (from the state file) |
| --- | --- |
| `<A>` | `ADMIN_ACCOUNT`, the admin's gcloud account |
| `<ORG>` | `ORG_ID`, numeric organization ID |
| `<P>` | `MGMT_PROJECT_ID`, the central management project ID |
| `<N>` | `MGMT_PROJECT_NUMBER` |
| `<D>` | `DOMAIN`, the organization's domain |
| `<G>` | `USERS_GROUP`, normally `autocloud-users@<D>` |
| `<S>` | `<SKILL_DIR>/scripts` |

Always show commands with the real values. Both scripts always take
`--org <ORG> --project <P>`, which selects this organization and project's
state file and change log:

- Every change: `<S>/log-run.sh "Step <n>: <label>" --org <ORG> --project <P> -- <command>`
- Every check: `<S>/admin-status.sh <check> --org <ORG> --project <P>`. Checks
  always call gcloud and the IAM API live. Other inputs (account, names,
  group, choices) are saved by the first call that passes them, so later
  calls only need `--org` and `--project`.

Below, `admin-status.sh <check>` is short for the full command above. Never
write the state file yourself.

---

## Step 0: Preflight and inputs

**What this does:** collects what the setup needs and checks that the admin's
machine and the management project are ready. It changes nothing.

**Ask first, look up only if asked.** Don't run any command to find these
values before asking. Ask for all of them in **one message**:

```text
To get started, I need five things:
  1. Organization name, e.g. example.com
  2. Organization ID (numeric), e.g. 123456789012
  3. Management project ID: the project you sent for Trusted Tester
     allowlisting, where everyone's agents will live
  4. Management project number, e.g. 987654321098
  5. Admin account (principal) you'll run the setup as, signed in to gcloud,
     e.g. admin@example.com
If you don't know one of them, say so and I'll look it up.
```

Use values the admin already gave (in the command arguments or earlier
messages) without asking again. Then:

1. **Domain:** take the part after `@` in the admin account and confirm it in
   one line, for example: `I'll use example.com as your domain, so the users
   group will be autocloud-users@example.com. Is that right?` Use a different
   domain only if the admin gives one.
3. If they didn't confirm that the project is the one they sent for Trusted
   Tester allowlisting, ask once. If it isn't allowlisted, stop: the setup can't
   finish without it. Tell them to contact their AutoCloud Trusted Tester
   contact.
4. Run preflight once with every input. This also saves them for this org and
   project (no separate file write, no extra approval):

   ```sh
   <S>/admin-status.sh preflight --org <ORG> --project <P> --org-name "<ORG_NAME>" --project-number <N> --account <A> --domain <D>
   ```

   Besides gcloud, the account's sign-in, the project's parent and billing, it
   checks live that the project number and organization name match what gcloud
   reports. On a mismatch, show both values and ask the admin which is right
   before going on (then run preflight again with the corrected value).

**Only if the admin says they don't know a value**, run the one matching
lookup, once, and ask them to pick from the result:

| Value | Lookup |
| --- | --- |
| Admin account | `gcloud auth list --format="value(account)"` |
| Organization ID or name | `gcloud organizations list --account=<A> --quiet --format="table(ID,displayName)" --limit=20` |
| Project ID | `gcloud projects list --account=<A> --quiet --filter="parent.type:organization AND parent.id:<ORG>" --format="table(projectId,name,projectNumber)" --limit=50` |
| Project number | `gcloud projects describe <P> --account=<A> --quiet --format="value(projectNumber)"` |

If a lookup fails or comes back empty, don't try other ways to find the value:
tell the admin what failed and ask them for it.

If gcloud isn't installed, point them to https://cloud.google.com/sdk/docs/install
(or suggest Cloud Shell, which has gcloud) and stop. If the account isn't
signed in, ask them to run `gcloud auth login <account>` in their terminal and
tell you when it's done.

**Fixes for a MISSING line:**

| Line | What to tell the admin |
| --- | --- |
| gcloud older than 587 | `gcloud components update` updates it (Cloud Shell is always current). For package-manager installs (apt, yum, Homebrew), update with that package manager. Offer to run it after a yes. |
| beta commands missing | `gcloud components install beta` (or the package manager's `google-cloud-cli-beta` package). |
| curl missing | install curl; the permission checks need it. |
| account not signed in | the admin runs `gcloud auth login <A>` in their own terminal. |
| project in a folder | **Stop.** The management project must sit directly under the organization. They can move it (Resource Manager > Move, needs `resourcemanager.projects.move`), or pick a project at the root that's allowlisted. Don't move it yourself. |
| billing not enabled | the project needs a billing account. Show the console page `https://console.cloud.google.com/billing/linkedaccount?project=<P>`. Don't run billing commands yourself. |
| consumer or google.com account | warn that the setup must run as an identity in their own organization, and ask them to confirm or switch accounts. |

---

## Step 1: Admin roles

**What this does:** checks that the admin has every role the setup needs, and
fills any gaps.

**Why:** later steps change organization policy, project IAM, APIs and egress
settings. Checking first avoids failing halfway.

**Check:** `<S>/admin-status.sh roles`. It uses `testIamPermissions`, so
roles that come from groups or from the organization count too.

| Permission checked | Role (from the onboarding guide) | Needed for |
| --- | --- | --- |
| `resourcemanager.organizations.setIamPolicy` (org) | `roles/resourcemanager.organizationAdmin` | binding the org in Step 3; granting org roles |
| `orgpolicy.policy.set` (org and project) | `roles/orgpolicy.policyAdmin` (granted on the **organization**) | Step 6 |
| `resourcemanager.capabilityConfigs.list`, `resourcemanager.capabilityConfigs.create` (org) | `roles/resourcemanager.editor` (granted on the **organization**) | Step 3, and the AutoCloud console finding the organization's management project |
| `resourcemanager.projects.setIamPolicy` | `roles/resourcemanager.projectIamAdmin` (or Owner) | Steps 1, 4, 5, 10 |
| `serviceusage.services.enable` | `roles/serviceusage.serviceUsageAdmin` | Step 2 |
| `networkservices.extensionBindings.create` | `roles/networkservices.serviceExtensionsAdmin` | Steps 7, 8 |
| `modelarmor.templates.create` (only if Model Armor) | `roles/modelarmor.admin` | Step 8 |
| `iam.accesspolicies.create`, `iam.accesspolicies.bind` | `roles/iam.accessPolicyAdmin` | Step 10 |
| `apphub.boundaries.update` | `roles/apphub.admin` | Step 11 |

Show the result as a short table (role · ✅/❌ · needed for). If everything is
✅, say so and move on.

**About Resource Manager Editor:** the organization-level permissions are only
checked on the organization. Before granting `roles/resourcemanager.editor`,
explain it plainly: it lets the admin manage the organization's resource
hierarchy (create, move and delete folders and projects, manage tags) and its
capability configs. The AutoCloud console needs
`resourcemanager.capabilityConfigs.list` on the organization to find its
management project, and Organization Admin doesn't include it; without it the
console shows `Permission 'resourcemanager.capabilityConfigs.list' denied on
resource '//cloudresourcemanager.googleapis.com/organizations/<ORG>'`.

**Filling gaps:**

- **Project roles**, if the admin has `resourcemanager.projects.setIamPolicy`:
  offer to grant the missing roles to their own account, one command per role:

  ```sh
  gcloud projects add-iam-policy-binding <P> --member=user:<A> --role=<ROLE> --condition=None --account=<A> --quiet --format=none
  ```

- **Organization roles**, if the admin has
  `resourcemanager.organizations.setIamPolicy`:

  ```sh
  gcloud organizations add-iam-policy-binding <ORG> --member=user:<A> --role=<ROLE> --condition=None --account=<A> --quiet --format=none
  ```

- **If they can't grant a role**, draft a message they can send to someone who
  can (an organization admin, or the project owner):

  ```text
  Hi, I'm setting up Cloud Operator (AutoCloud) for our organization.
  Could you grant <A> these roles?
    - <ROLE> on organization <ORG>     (to <reason>)
    - <ROLE> on project <P>            (to <reason>)
  Commands, if you prefer:
    gcloud organizations add-iam-policy-binding <ORG> --member=user:<A> --role=<ROLE> --condition=None
    gcloud projects add-iam-policy-binding <P> --member=user:<A> --role=<ROLE> --condition=None
  ```

  Then ask whether to wait (they come back once it's granted and you recheck)
  or continue with the steps that don't need the missing roles. Mark the
  dependent steps as blocked, and come back to them at the end.

**Verify:** run `<S>/admin-status.sh roles` again, waiting about a minute
between tries, up to 3 times.

> **Known gap:** as of October 2026, the published
> `roles/networkservices.serviceExtensionsAdmin` role doesn't list
> `networkservices.extensionBindings.create`, but project Owner has it. If the
> permission is still missing after granting that role, a project Owner has to
> run Steps 7 and 8 (offer show-only commands for them), or the admin escalates.

---

## Step 2: APIs

**What this does:** enables the Google Cloud APIs the setup and the agents use,
on the management project only.

**Why:** the Admin Onboarding Console (Step 3) expects the AutoCloud APIs, and
the later steps need the rest. Enabling them first keeps Complete setup from
failing on a missing API.

**Needs:** `roles/serviceusage.serviceUsageAdmin`.

| API | Used for |
| --- | --- |
| `geminicloudassist.googleapis.com` | Cloud Operator itself |
| `agentregistry.googleapis.com` | agents' skills and configuration |
| `apptopology.googleapis.com` | application topology |
| `aiplatform.googleapis.com` | the agents' runtime |
| `logging.googleapis.com`, `monitoring.googleapis.com` | logs and metrics |
| `developerconnect.googleapis.com` | source connections |
| `networkservices.googleapis.com`, `serviceextensions.googleapis.com` | data egress policy bindings (Steps 7-9) |
| `iap.googleapis.com`, `iam.googleapis.com` | UAP egress policy (Step 10) |
| `modelarmor.googleapis.com` | Model Armor (Step 8) |
| `apphub.googleapis.com` | App Hub boundary (Step 11) |
| `cloudidentity.googleapis.com` | creating and checking the users group (Step 4) |
| `cloudresourcemanager.googleapis.com` | `gcloud identity groups create --organization` looks up the organization through it (Step 4) |
| `orgpolicy.googleapis.com` | the org policy commands (Step 6) |

**Check:** `<S>/admin-status.sh apis`. Enable only the missing ones.

**Change** (one command, missing APIs only; it can take a minute or two):

```sh
gcloud services enable <API> <API> ... --project=<P> --account=<A> --quiet
```

**Verify:** `<S>/admin-status.sh apis`.

---

## Step 3: Admin Onboarding Console (permanent)

**What this does:** binds the organization to the management project in
AutoCloud. Clicking **Complete setup** sets up the MCP services and turns on
AutoCloud's management features for the organization.

**Why:** AutoCloud only creates agents in the management project bound to the
organization.

**Needs:** `roles/resourcemanager.organizationAdmin` and
`roles/resourcemanager.editor` on the organization (from Step 1), the APIs
from Step 2, and Step 0's checks (project directly under the org, billing
enabled). Don't start this step if either Step 0 check failed.

**If Resource Manager Editor is still missing** (Step 1 showed it ❌ and it
wasn't granted), warn first: Complete setup and the AutoCloud console's lookup
of the management project may fail without it. Then offer three choices:
grant it now (if they have Organization Admin; the Step 1 command), send the
Step 1 request message and wait, or continue anyway.

**Ask first; the check is evidence only:** always show this step, and ask:
`Does the Admin Onboarding Console already show setup as complete for <P>?
(yes / no)`. If yes, run `<S>/admin-status.sh console` and quote its line:
`OK` confirms it; `MISSING` or `UNKNOWN` means tell the admin what it found
and ask them to check the console again before moving on. If no, continue
below. Never skip this step because of the check alone.

**Change:** show this warning first, word for word:

```text
⚠️  This choice is permanent during Private Preview.
Once your organization is bound to <P> in the AutoCloud Admin Onboarding
Console, it can't be changed or re-pointed from the Cloud Console, and <P>
must not be deleted while AutoCloud is active. Changing it later needs the
AutoCloud team.
```

Ask the admin to **type the project ID** (`<P>`) to confirm. Anything other
than an exact match means don't continue: ask again or let them stop.

Then give them the link and steps:

1. Open
   `https://console.cloud.google.com/autocloud/admin/onboarding?project=<P>&organizationId=<ORG>`,
   signed in as `<A>`. (A private window helps if the browser is signed in to
   other Google accounts.)
2. Choose `<P>` in the project picker if it isn't already selected.
3. Click **Complete setup** and wait for it to finish.
4. Reply `done` here (or paste any error you see).

**Verify:** run `<S>/admin-status.sh console` (the organization should now be
bound to `<P>`; it can take a minute, so retry up to 3 times) and
`<S>/admin-status.sh apis` (Complete setup may enable more APIs, and none
should be missing). Quote the lines. If the console showed an error, such as
the project not being allowlisted or a `capabilityConfigs` permission error,
or `console` says the organization is bound to a different project, see the
troubleshooting guide before going on.

---

## Step 4: Users group and roles

**What this does:** creates the group of people who can use Cloud Operator,
and grants it the roles to use agents in the management project.

**Why a group:** one IAM grant covers everyone. Adding people later is just
adding them to the group, with no IAM change. Always recommend it.

**Needs:** `roles/resourcemanager.projectIamAdmin` for the grants, and
permission to create groups in Google Workspace / Cloud Identity (a Groups
Admin, or a Workspace setting that lets users create groups). The second can't
be checked in advance.

### 4a. The group

1. Group email: `autocloud-users@<D>` (the admin can pick another name; pass
   it once as `--group <G>` to the next check, which saves it).
2. **Check:** `<S>/admin-status.sh group`. If it exists, say so and go to 4b.
3. **Change:** create it.

   ```sh
   gcloud identity groups create autocloud-users@<D> --organization=<ORG> --display-name="AutoCloud users" --description="People who can use Cloud Operator (AutoCloud) agents in <P>" --billing-project=<P> --account=<A> --quiet
   ```

   The account that creates the group becomes its owner, so the admin is
   already a member.
4. **If creating it fails,** don't offer individual users yet. First, give the
   admin what they need to create the group themselves:
   - the same command, to run in their own terminal (or by their Workspace
     admin), or
   - the Admin console: https://admin.google.com > **Directory > Groups >
     Create group**, name `AutoCloud users`, email `autocloud-users@<D>`.

   Wait for them to say it's done, then check again. **Only if that also
   fails**, offer to continue with just their own account for now: pass
   `--group <A> --member-type user` to the next check (it saves them), use
   `--member=user:<A>` in 4c, and remind them in the final report to create the group later and
   grant it the same roles.

### 4b. Members

1. **Check:** whether the admin is in the group (`admin-status.sh group` shows
   it). If the setup just created the group, they are (as its owner): don't
   add them again. Only if the check says they aren't a member, include
   adding them:

   ```sh
   gcloud identity groups memberships add --group-email=<G> --member-email=<A> --billing-project=<P> --account=<A> --quiet
   ```

2. Ask which other people should use Cloud Operator now (emails,
   comma-separated, or `none`; more can be added later). Show one
   `memberships add` command per person and ask once for the whole list.
3. **Verify** every member you added (the `group` check also lists all
   members):

   ```sh
   gcloud identity groups memberships check-transitive-membership --group-email=<G> --member-email=<EMAIL> --billing-project=<P> --account=<A> --quiet --format="value(hasMembership)"
   ```

### 4c. Roles on the management project

Explain each role in plain words:

| Role | What it allows |
| --- | --- |
| `roles/geminicloudassist.user` (required) | Chat with Cloud Operator agents and call them over MCP; create and delete their own agent. |
| `roles/agentregistry.viewer` (required during Private Preview) | See agent applications and MCP servers in Agent Registry. |
| `roles/geminicloudassist.editor` (optional in the guide) | Customize agents (custom instructions, skills) and change Gemini Cloud Assist settings for the project. |
| `roles/aiplatform.editor` (optional in the guide) | Manage and delete agent instances. It covers all of Vertex AI in the project, so members can also read, change and delete **other users'** agents, sessions, memories and tasks. |

The default is to grant all four. Ask once: `Grant all four roles (default), or
only the two required ones?` Right after the admin answers (and only then),
pass their answer as `--editor-roles yes` or `no`
to the verify check below (it saves it).

**Change** (one command per role; `<MEMBER>` is `group:<G>`, or `user:<A>` in
the single-user fallback):

```sh
gcloud projects add-iam-policy-binding <P> --member=<MEMBER> --role=<ROLE> --condition=None --account=<A> --quiet --format=none
```

**Verify:** `<S>/admin-status.sh user-iam`.

**Basic roles warning:** if `user-iam` shows a WARN about basic roles
(Viewer, Editor, Owner) on the management project, explain: during Private
Preview, anyone with a basic role on this project can read everyone's agent
conversations. List the members it found and suggest the admin review them.
**Don't remove anything yourself.** If they ask you to, treat it as a
separate change with its own commands and confirmation.

---

## Step 5: Agent principal set

**What this does:** lets the organization's Cloud Operator agents read their
skills and configuration from Agent Registry.

**Why:** every agent running in the management project acts as this
principal set. Without the grant, agents can't load their skills.

**Needs:** `roles/resourcemanager.projectIamAdmin`.

**Check:** `<S>/admin-status.sh agent-iam`.

**Change:**

```sh
gcloud projects add-iam-policy-binding <P> --member="principalSet://agents.global.org-<ORG>.system.id.goog/attribute.platformContainer/aiplatform/projects/<N>" --role=roles/agentregistry.viewer --condition=None --account=<A> --quiet --format=none
```

**Verify:** `<S>/admin-status.sh agent-iam`.

**If it fails with `Identity Pool does not exist`** (`organizations/<ORG>/locations/global/workloadIdentityPools/agents.global.org-<ORG>.system.id.goog`):
explain it in plain words. The agent principal set belongs to the
organization's agent identity pool, which Vertex AI creates the first time any
project in the organization creates an agent that uses Agent Identity.
Enabling APIs doesn't create it, so a brand-new organization doesn't have it
yet.

1. Wait about a minute and retry the command once.
2. If it still fails, offer to bootstrap the pool (one confirmation). The
   helper creates a temporary, empty Agent Engine instance with Agent Identity
   in `<P>` (region `us-central1`), waits until it has an agent identity
   (usually under a minute), and deletes it. The pool stays permanently. It
   needs `aiplatform.googleapis.com` (Step 2) and `roles/aiplatform.user` (or
   Owner) on `<P>`.

   ```sh
   <S>/log-run.sh "Step 5: Bootstrap agent identity pool" --org <ORG> --project <P> -- <S>/bootstrap-agent-identity-pool.sh --account <A> --project <P>
   ```

3. When it reports `agent identity pool is ready`, retry the
   `add-iam-policy-binding` command above. If the helper fails, see the
   troubleshooting guide; if it reports a leftover instance, tell the admin
   its name so they can delete it in the console (Vertex AI > Agent Engine).

---

## Step 6: Org policy override

**What this does:** turns off the `iam.managed.disableAccessPolicyBinding`
constraint **on the management project only**. Other projects keep the
organization's setting.

**Why:** the constraint is on by default and blocks binding access policies to
projects. Step 10 has to bind the UAP egress policy to the management project.

**Needs:** `orgpolicy.policy.set`, from `roles/orgpolicy.policyAdmin` on the
organization. Project Owner doesn't include it.

**Check:** `<S>/admin-status.sh orgpolicy`. Only an unconditional
`enforce: false` counts as `OK`. No rule at all is `MISSING` (the constraint
is enforced by default, and setting the override is harmless); conditional or
multiple rules are `UNKNOWN`: ask the admin to check the policy in the
console.

**Change:** write the policy to a temp file and show it:

```sh
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/autocloud.XXXXXX")"
POLICY_FILE="$TMP_DIR/orgpolicy.yaml"
cat >"$POLICY_FILE" <<'EOF'
name: projects/<P>/policies/iam.managed.disableAccessPolicyBinding
spec:
  rules:
  - enforce: false
EOF
cat "$POLICY_FILE"
```

Then, after a yes:

```sh
gcloud org-policies set-policy <POLICY_FILE path> --account=<A> --quiet
```

Delete the temp folder (`rm -rf <TMP_DIR path>`) afterwards.

**Verify:** `<S>/admin-status.sh orgpolicy`. It can take a few minutes to
apply, so retry as the safety rules say.

---

## Step 7: Data egress policies

**What this does:** attaches two policy extensions to the agent gateway for
agents in the management project:

- **PDP binding** (`autocloud-hodor-egress-binding`, producer
  `workspacepolicyengine.pa.googleapis.com`): applies the egress policies and
  attaches Google OAuth credentials to the agents' outgoing calls.
- **IAP binding** (`autocloud-iap-egress-binding`, producer
  `iap.googleapis.com`): enforces the UAP egress rules from Step 10 on every
  outgoing call.

**Why:** without them, agents can't make authenticated calls to Google Cloud,
and egress can't be controlled.

**Needs:** `networkservices.extensionBindings.create` (see the known gap in
Step 1).

**Check:** `<S>/admin-status.sh deps`. Create only the missing bindings, one
confirmation each.

**Change:**

```sh
gcloud beta service-extensions extension-bindings create autocloud-hodor-egress-binding --project=<P> --location=global --producer-extension=workspacepolicyengine.pa.googleapis.com --scope-parent=projects/<N> --scope-resource-types=ai-application --account=<A> --quiet
gcloud beta service-extensions extension-bindings create autocloud-iap-egress-binding --project=<P> --location=global --producer-extension=iap.googleapis.com --scope-parent=projects/<N> --scope-resource-types=ai-application --account=<A> --quiet
```

**Verify:** `<S>/admin-status.sh deps`.

---

## Step 8: Model Armor (optional, recommended)

**What this does:** has the agent gateway send prompts, MCP tool calls and tool
responses to Model Armor, which scans them for prompt injection and jailbreak
attempts and blocks the ones it flags.

**Explain the trade-off, then recommend yes:**

- It protects agents from instructions hidden in data they read (for example a
  log line telling the agent to ignore its rules).
- With inspect and block, a false positive makes that tool call fail for the
  agent. Scan results go to Cloud Logging, so the admin can review them.
- The template **must be in the `us` multi-region**. A template in a single
  region (such as `us-central1`) makes every agent task fail.
- Model Armor usage may be billed. See the Model Armor pricing page.

Ask `Set up Model Armor? (yes, recommended / no)`. Right after the admin
answers (and only then), pass their answer as
`--model-armor yes` or `no` to the next check (it saves it). If no, say they
can add it later by running admin setup again.

**Needs:** `roles/modelarmor.admin` and `networkservices.extensionBindings.create`.

**Check:** `<S>/admin-status.sh modelarmor`.

### 8a. Template

If it's missing, create it (the endpoint override applies to this one command):

```sh
CLOUDSDK_API_ENDPOINT_OVERRIDES_MODELARMOR=https://modelarmor.us.rep.googleapis.com/ <S>/log-run.sh "Step 8: Model Armor template" --org <ORG> --project <P> -- gcloud model-armor templates create autocloud-modelarmor-template --location=us --project=<P> --pi-and-jailbreak-filter-settings-enforcement=enabled --pi-and-jailbreak-filter-settings-confidence-level=medium-and-above --template-metadata-log-sanitize-operations --account=<A> --quiet
```

Then check again. gcloud has no flag for the enforcement type, and templates it
creates come back with the enforcement type **unset**. Set it explicitly to
inspect and block (one confirmation, through the change log; the helper calls
the Model Armor API and keeps the access token out of the command line):

```sh
<S>/log-run.sh "Step 8: Model Armor enforcement" --org <ORG> --project <P> -- <S>/set-modelarmor-enforcement.sh --account <A> --project <P> --mode inspect-and-block
```

If the template exists with other filters on, explain the difference and give
the console fix:
Model Armor page (`https://console.cloud.google.com/security/modelarmor?project=<P>`)
> `autocloud-modelarmor-template` > **Edit**: enforcement type **Inspect and
block**; prompt injection and jailbreak detection **on**, **Medium and above**;
malicious URL, Sensitive Data Protection and responsible AI filters **off**;
logging of sanitize operations **on**. These are recommendations; let the
admin keep their own settings if they prefer.

**Console fallback** (if gcloud fails): the same page > **Create template**
with ID `autocloud-modelarmor-template`, region **us (multi-region)**, and the
settings above. Then check that the template list shows its location as `us`.

### 8b. Binding

Write the producer metadata to a temp file and show it:

```sh
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/autocloud.XXXXXX")"
MA_META="$TMP_DIR/ma-meta.yaml"
cat >"$MA_META" <<'EOF'
model_armor_settings: '[{"request_template_id":"projects/<P>/locations/us/templates/autocloud-modelarmor-template","response_template_id":"projects/<P>/locations/us/templates/autocloud-modelarmor-template"}]'
EOF
cat "$MA_META"
```

Then, after a yes:

```sh
gcloud beta service-extensions extension-bindings create autocloud-modelarmor-binding --project=<P> --location=global --producer-extension=modelarmor.us.rep.googleapis.com --scope-parent=projects/<N> --scope-resource-types=ai-application --producer-metadata=<MA_META path> --account=<A> --quiet
```

Delete the temp folder (`rm -rf <TMP_DIR path>`) afterwards.

**Verify:** `<S>/admin-status.sh modelarmor`. The gateway can take about
4 minutes to pick up a new binding. To change the enforcement mode or threshold
later, edit the template; the binding doesn't need to be recreated.

---

## Step 9: Check the egress bindings

**What this does:** confirms the bindings from Steps 7 and 8 exist with the
right producer, the right scope (this project's AI applications) and, for
Model Armor, the right template. It changes nothing.

Run `<S>/admin-status.sh deps` and `<S>/admin-status.sh modelarmor` and quote
the binding lines (the summary's Step 9 row is built from the same lines).
Every binding line must be `OK` (`autocloud-modelarmor-binding` may be `SKIP`
only when the admin said no to Model Armor). Anything else sends you back to
Step 7 or 8; a binding with the wrong producer, scope or template has to be
deleted and recreated (two changes, each with its own confirmation).

---

## Step 10: UAP egress policy

**What this does:** creates a Universal Access Policy (UAP) named
`autocloud-egress-policy` and binds it to the management project. It decides
which endpoints the agents in this project may call through IAP.

**Why:** agent egress is denied unless a rule allows it. These rules let the
agents use read-only Google Cloud tools and nothing else.

**The rules, in plain words** (all ALLOW, all for the agent principal set of
this project only):

| Rule | Allows |
| --- | --- |
| 1 | The read-only Google Cloud CLI MCP endpoint (`cloudcli.googleapis.com/mcp/readonly`) |
| 2 | `GET` requests to the Terraform registry and HashiCorp releases (for `terraform init` / `validate`) |
| 3 | Registered MCP servers: discovery methods, and `tools/call` only for tools marked read-only |
| 3a | Discovery methods on Google MCP servers (GKE, Monitoring, Service Health, Developer Knowledge, App Topology, Design Center, App Optimize, Cloud Support, Telemetry Management) |
| 3b | Named read-only GKE tools |
| 3c | Named read-only Monitoring, Service Health and Developer Knowledge tools |
| 3d | Named read-only App Topology, Design Center and App Optimize tools |
| 3e | The Cloud Support eligibility check, and named read-only Telemetry Management tools |
| 4 | Read-only calls to Google APIs: `GET`, and `POST` only for `:list`, `:getIamPolicy`, `:query`, `:testIamPermissions` and the GKE read-only MCP path |

**Needs:** `iam.accesspolicies.create` and `iam.accesspolicies.bind`
(`roles/iam.accessPolicyAdmin`), `resourcemanager.projects.createPolicyBinding`
(`roles/resourcemanager.projectIamAdmin`), and **Step 6 done** (otherwise the
binding fails with `FAILED_PRECONDITION`).

**Check:** `<S>/admin-status.sh uap`.

### 10a. Render the rules

```sh
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/autocloud.XXXXXX")"
UAP_FILE="$TMP_DIR/uap-rules.json"
<S>/admin-status.sh render-uap --out "$UAP_FILE"
```

Show the rules table above, and offer the full JSON (`cat "$UAP_FILE"`) if they
want to review it.

### 10b. Create or update the policy

If the policy doesn't exist, validate first, then create:

```sh
gcloud iam access-policies create autocloud-egress-policy --project=<P> --location=global --display-name="AutoCloud egress policy" --details-rules=<UAP_FILE path> --validate-only --account=<A> --quiet
gcloud iam access-policies create autocloud-egress-policy --project=<P> --location=global --display-name="AutoCloud egress policy" --details-rules=<UAP_FILE path> --account=<A> --quiet
```

If it exists but `uap` says its rules differ, explain that updating
**replaces all of its rules** with the ones above (so any rules the admin
added to it themselves are removed), then validate and update:

```sh
gcloud iam access-policies update autocloud-egress-policy --project=<P> --location=global --details-rules=<UAP_FILE path> --validate-only --account=<A> --quiet
gcloud iam access-policies update autocloud-egress-policy --project=<P> --location=global --details-rules=<UAP_FILE path> --account=<A> --quiet
```

### 10c. Bind it to the project

```sh
gcloud iam policy-bindings create bind-autocloud-egress-policy --project=<P> --location=global --policy=projects/<N>/locations/global/accessPolicies/autocloud-egress-policy --target-resource=//cloudresourcemanager.googleapis.com/projects/<N> --account=<A> --quiet
```

Delete the temp folder (`rm -rf <TMP_DIR path>`) afterwards.

**Verify:** `<S>/admin-status.sh uap`. It needs a binding that attaches
exactly `autocloud-egress-policy` to exactly `projects/<N>` with no condition,
and rules identical (in any order) to the bundled ones; without `python3` the
rule comparison is `UNKNOWN`. It also lists any other access policy bound to
the project or the organization as `WARN`: tell the admin they can widen or
block what agents reach, and that the skill doesn't evaluate them. The
summary only shows Step 10 as ✅ when the IAP egress binding (Step 7) is also
`OK`, because UAP is enforced through it.

**If creating or updating the policy fails with `Failed to resolve policy
members`:** the rules name the agent principal set, and the organization's
agent identity pool doesn't exist yet (see Step 5). If the pool was already
bootstrapped in Step 5, wait a minute and retry. Otherwise follow Step 5's
"Identity Pool does not exist" steps (retry once, then offer the bootstrap
helper, labeled `Step 10: Bootstrap agent identity pool`), then retry 10b.

**Console fallback:** Agent Platform policies
(`https://console.cloud.google.com/agent-platform/policies/iam?project=<P>`)
> **Create policy**, name `autocloud-egress-policy`, **All agents in this
project**, **Custom**, then add each rule from the rendered file as an ALLOW
rule for `iap.googleapis.com/resources.egressViaIAP` with its CEL expression.
Check the result with `admin-status.sh uap`.

---

## Step 11: App Hub boundary

**What this does:** sets the App Hub boundary of the management project to the
project itself.

**Why:** App Hub (and the application topology AutoCloud reads) uses the
boundary to know which resources the management project's applications
cover.

**Needs:** `roles/apphub.admin`, and `apphub.googleapis.com` enabled (Step 2).

**Check:** `<S>/admin-status.sh apphub`. Three possible results:

- `boundary → projects/<P>`: done.
- `managed boundary covering organization <ORG>`: done. When the organization
  was onboarded through the Admin Onboarding Console, the management project's
  boundary is a **managed** boundary that covers the whole organization. It
  can't be updated (`gcloud apphub boundary update` fails with `managed
  boundaries cannot be updated`), and doesn't need to be. Don't run the update.
- not set (describing a boundary that was never set returns an empty one):
  run the update below.

**Change:**

```sh
gcloud apphub boundary update --crm-node=projects/<P> --project=<P> --location=global --account=<A> --quiet
```

**Verify:** `<S>/admin-status.sh apphub`, which accepts the project ID or
number in `crmNode`.

---

## Step 12: Final check

Run `<S>/admin-status.sh summary --org <ORG> --project <P> --since <session start>` and write the final report as `SKILL.md`
describes.
