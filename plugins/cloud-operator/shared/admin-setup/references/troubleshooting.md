# Troubleshooting

Look up the key line of the error here. Explain the likely cause to the admin
in plain words, offer the workarounds in order, and ask before trying any of
them. If nothing works, escalate (bottom of this page).

## Any step

| Error contains | Likely cause | Workarounds |
| --- | --- | --- |
| `PERMISSION_DENIED`, `does not have ... permission`, `403` | The admin lacks the step's role, or a role granted in the last few minutes hasn't spread yet. | 1. Run `admin-status.sh roles` to see what's missing. 2. If it was granted recently, wait a minute and retry (up to 3 times). 3. Grant the role (Step 1) or send the request message from Step 1. 4. Offer show-only commands for someone who has the role. |
| `has not been used in project` or `SERVICE_DISABLED` | An API is disabled on the management project. gcloud uses the management project for quota on these calls. | Enable the API named in the error (Step 2 command), wait a minute, retry. |
| `requires a quota project` or `quota project` | gcloud didn't send a quota project for this API. | Add `--billing-project=<P>` to the command and retry. |
| `ALREADY_EXISTS` or `already exists` | An earlier run (or someone else) already created it. | Treat as done: run the step's check to confirm it has the expected settings. |
| `Invalid choice` or `unrecognized arguments` | gcloud is too old or is missing the beta component. | `gcloud components update`, `gcloud components install beta` (or the package manager equivalent), or use Cloud Shell. |
| `Reauthentication required`, `invalid_grant`, `There was a problem refreshing your current auth tokens` | The admin's gcloud sign-in expired. | The admin runs `gcloud auth login <A>` in their terminal, then you retry. |
| `Certificate-based access is enabled` (or other mTLS/CBA errors) | The machine enforces certificate-based access, and this endpoint override or API doesn't support it. | Run the step from Cloud Shell, or use the console fallback for the step. |
| `Certificate-based access is enabled, but the endpoint override ... is not using mTLS` (Model Armor) | Usually a different error underneath (often billing turned off) that gcloud reports this way on machines with certificate-based access. | Check billing first (`admin-status.sh preflight`). If billing is fine, use `https://modelarmor.us.rep.mtls.googleapis.com/` as the override for that command, or run the step from Cloud Shell. |
| `Permission 'resourcemanager.capabilityConfigs.list' denied on resource '//cloudresourcemanager.googleapis.com/organizations/<ORG>'` (in the console, often URL-encoded as `capabilityConfigs.list%27+denied`) | The person lacks the organization-level permission the AutoCloud console uses to find the management project. Organization Admin doesn't include it. | **Admin:** grant `roles/resourcemanager.editor` on the organization (Step 1). **Users** who see it: grant them the read-only `roles/resourcemanager.viewer` on the organization, for example `gcloud organizations add-iam-policy-binding <ORG> --member=group:<G> --role=roles/resourcemanager.viewer --condition=None --account=<A> --quiet --format=none` (with a yes, through `log-run.sh`). Then wait a few minutes and reload the console. |
| A check line says `UNKNOWN` with an error in it | The check couldn't read the resource (permission, disabled API, expired sign-in, billing). It doesn't mean the resource is missing. | Fix the quoted error first (rows above), then run the check again. Never treat `UNKNOWN` as done. |
| A command hangs or waits for input | It's prompting for something. | Every command must have `--quiet`. Stop it, add `--quiet`, and retry. |

## Step-specific

| Step | Error or symptom | Likely cause | Workarounds |
| --- | --- | --- | --- |
| 0 | Project parent is a folder | The management project must be at the organization root. | Move the project (needs `resourcemanager.projects.move` on both ends) or choose an allowlisted root project. Don't move it for them. |
| 0 | `billingEnabled` false or unknown | No billing account, or no permission to see it. | Link billing in the console (`/billing/linkedaccount?project=<P>`), or ask a billing admin. |
| 1 | `orgpolicy.policy.set` missing even though the admin is project Owner | Owner doesn't include org policy permissions. | Grant `roles/orgpolicy.policyAdmin` on the **organization** (needs an organization admin). |
| 1 | `networkservices.extensionBindings.create` missing after granting `roles/networkservices.serviceExtensionsAdmin` | As of October 2026, the published role doesn't list this permission; project Owner has it. | A project Owner runs Steps 7-8 (show-only commands), or escalate. |
| 2 | `FAILED_PRECONDITION` with `billing` | Billing isn't enabled. | Fix billing (Step 0), then retry. |
| 2 | `services enable` takes long or times out | API enablement can take a few minutes. | Wait, then run `admin-status.sh apis` again before retrying. |
| 3 | The console says the project or organization isn't allowlisted | The project differs from the one sent for Trusted Tester allowlisting, or allowlisting hasn't finished. | Double-check the project ID. Otherwise escalate. |
| 3 | The console shows a different management project | The organization was already bound to another project (permanent during Private Preview). | Use that project for the rest of the setup (run `admin-status.sh preflight` again with `--project <that project>`; the script saves it), or escalate to change it. |
| 4 | Group create `PERMISSION_DENIED` or `Not Authorized` | The admin isn't a Groups Admin, or the Workspace settings don't let users create groups. | Show-only: their Workspace admin runs the command, or creates the group at admin.google.com > Directory > Groups. Only after that fails, the single-user fallback (steps.md, Step 4a). |
| 4 | Group create `Entity already exists` | The group exists. | Treat as done; check membership. |
| 4 | Group create fails with `does not have permission to access organizations instance` and `Cloud Resource Manager API has not been used` | `gcloud identity groups create --organization` looks up the organization through the Cloud Resource Manager API on the management project. | Enable `cloudresourcemanager.googleapis.com` (Step 2), wait a minute, retry. |
| 4 | `memberships add` fails with `already exists` | The person is already a member (the account that creates a group becomes its owner). | Treat as done. |
| 4 | `memberships add` fails for an external email | The domain doesn't allow outside members in groups. | Add only people in the organization's domains, or change the group's settings in the Admin console. |
| 4 | `add-iam-policy-binding` fails with `domain` or `allowedPolicyMemberDomains` (`One or more users named in the policy do not belong to a permitted customer`) | Domain-restricted sharing blocks this member. | Use a member from the organization's own domain, or ask the org policy admin for an exception. |
| 5 | `allowedPolicyMemberDomains` error on the `principalSet://agents...` member | Domain-restricted sharing may block the agent principal set. | Ask the org policy admin to allow it on the management project (a project-level exception to `iam.allowedPolicyMemberDomains`), or escalate. |
| 5 | `INVALID_ARGUMENT: Identity Pool does not exist (organizations/<ORG>/locations/global/workloadIdentityPools/agents.global.org-<ORG>.system.id.goog)` | The organization's agent identity pool hasn't been created yet. Vertex AI creates it the first time a project in the organization creates an agent that uses Agent Identity; enabling APIs doesn't, so new organizations hit this. | Retry once after a minute. Then run `bootstrap-agent-identity-pool.sh` (steps.md, Step 5) and retry. If the helper fails, check that `aiplatform.googleapis.com` is enabled and the admin has `roles/aiplatform.user` (or Owner) on the project; otherwise escalate. |
| 6 | `set-policy` `PERMISSION_DENIED` | `roles/orgpolicy.policyAdmin` must be granted on the organization. | Grant it at the organization (Step 1) or have an organization policy admin run the show-only command. |
| 6 | `admin-status.sh orgpolicy` still says enforced right after the change | Org policy changes take a few minutes to apply. | Wait and recheck (up to 3 times). |
| 7, 8, 9 | A binding check says the binding points at the wrong producer, scope or template | It was created by hand or with different flags. | Delete it (`gcloud beta service-extensions extension-bindings delete <ID> --project=<P> --location=global`) and recreate it with the Step 7 or 8 command: two changes, each with its own confirmation. |
| 7, 8 | `extension-bindings create` `INVALID_ARGUMENT` about the producer extension | The producer isn't available to this project, often because allowlisting isn't finished. | Check the flags match steps.md exactly, then escalate. |
| 8 | Model Armor `NOT_FOUND` or `Template not found`, or every agent task fails after the binding | The template isn't in the `us` multi-region, or the binding points at the wrong template. | Check `admin-status.sh modelarmor`. Create the template in `us`, then delete and recreate the binding with the right template (two separate changes, each with a confirmation). |
| 8 | `model-armor templates create` fails with a location or endpoint error | The regional endpoint override wasn't applied. | Make sure `CLOUDSDK_API_ENDPOINT_OVERRIDES_MODELARMOR=https://modelarmor.us.rep.googleapis.com/` is in front of the command, or use the console fallback. |
| 8 | Agent tool calls fail with safety or blocked errors after setup | Model Armor flagged them (possibly false positives). | Review the scan results in Cloud Logging (log `modelarmor.googleapis.com/sanitize_operations`). If it's too strict, raise the confidence level or switch the template to inspect only in the console. |
| 10 | `policy-bindings create` fails with `FAILED_PRECONDITION`, `CUSTOM_ORG_POLICY_VIOLATION`, or mentions `iam.managed.disableAccessPolicyBinding` | The constraint is still enforced on the project (Step 6 not done, or not applied yet; it usually takes 30-60 seconds, sometimes a few minutes). | Finish Step 6, run `admin-status.sh orgpolicy` until it's OK, then retry. |
| 10 | `access-policies create` or `update` fails with `Failed to resolve policy members` | Same cause as the Step 5 `Identity Pool does not exist` error: the agent identity pool doesn't exist yet. | Bootstrap the pool (steps.md, Step 5) if that hasn't been done, wait a minute, and retry. |
| 10 | `access-policies create` `INVALID_ARGUMENT` about a rule or expression | The rules file is wrong or was edited. | Render it again with `admin-status.sh render-uap`, run `--validate-only`, and don't edit the file by hand. |
| 10 | `uap` says the rules differ | The policy has extra, duplicate or older rules (for example from pasting rules in the console twice). | Update the policy (Step 10b); updating replaces all of its rules. |
| 11 | `apphub boundary update` fails with `PERMISSION_DENIED` | Missing `roles/apphub.admin`. | Grant it (Step 1), wait, retry. |
| 11 | `FAILED_PRECONDITION ... managed boundaries cannot be updated` | The organization's boundary is managed and already covers the whole organization (set when the org was onboarded). | Treat as done: `admin-status.sh apphub` shows it as OK. |
| 8 | `admin-status.sh modelarmor` says the enforcement is `unset` | Templates created with gcloud have no enforcement type, and gcloud has no flag for it. | Run `set-modelarmor-enforcement.sh` (steps.md, Step 8a), or set **Inspect and block** in the console. |
| 8 | Model Armor `This API method requires billing to be enabled` | Billing was turned off on the management project. | Re-link billing (Step 0), then retry. |
| 11 | Other App Hub boundary errors | App Hub boundaries for agents are still in preview. | Retry once after a minute; otherwise escalate. |

## Escalation

When a problem needs the AutoCloud team (allowlisting, a wrong management
project binding, producer extension errors, App Hub issues, or any error the
workarounds don't fix), tell the admin to **contact their AutoCloud Trusted
Tester contact**, and give them this summary to send. Fill it in from the
state file and the last lines of the change log:

```text
Subject: Cloud Operator (AutoCloud) admin setup issue: Step <n>

Organization ID:        <ORG>
Management project:     <P> (number <N>)
Admin account:          <A>
Step:                   <n>, <title>
Time (UTC):             <from the change log>
Command:                <exact command from the change log>
Error:                  <key error line>
What we tried:          <workarounds tried>
admin-status.sh output: <the lines for this step>
```

Don't include tokens, credential files or anything from the admin's local
files other than the above.
