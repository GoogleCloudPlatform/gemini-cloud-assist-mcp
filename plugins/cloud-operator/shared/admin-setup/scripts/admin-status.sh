#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Read-only status checks for the Cloud Operator (AutoCloud) organization admin
# setup. Used by the admin-setup skill to check each step before and after it
# runs, and to print the final status table.
#
# Every result comes from live gcloud and IAM API calls against the
# organization and project, made when the check runs. The state file only
# supplies inputs (account, names, the users group, the admin's choices), and
# the change log is never read.
#
# This script never changes anything in Google Cloud. Locally, it saves the
# inputs you pass it to the state file of that organization and project (see
# paths.sh), so later calls don't need them again, and render-uap writes the
# rules file you name.
#
# Works with macOS's default bash 3.2. Needs gcloud and curl.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UAP_TEMPLATE="$SCRIPT_DIR/../assets/uap-policy-3p.json"
# shellcheck source=paths.sh
. "$SCRIPT_DIR/paths.sh"

MIN_GCLOUD_MAJOR=587
UAP_POLICY_ID="autocloud-egress-policy"
PDP_BINDING_ID="autocloud-hodor-egress-binding"
PDP_PRODUCER="workspacepolicyengine.pa.googleapis.com"
IAP_BINDING_ID="autocloud-iap-egress-binding"
IAP_PRODUCER="iap.googleapis.com"
MA_BINDING_ID="autocloud-modelarmor-binding"
MA_TEMPLATE_ID="autocloud-modelarmor-template"
MA_LOCATION="us"
MA_PRODUCER="modelarmor.us.rep.googleapis.com"
MA_ENDPOINT="https://modelarmor.us.rep.googleapis.com/"
ORG_POLICY_CONSTRAINT="iam.managed.disableAccessPolicyBinding"

CORE_APIS="geminicloudassist.googleapis.com agentregistry.googleapis.com apptopology.googleapis.com aiplatform.googleapis.com logging.googleapis.com monitoring.googleapis.com developerconnect.googleapis.com"
EGRESS_APIS="networkservices.googleapis.com serviceextensions.googleapis.com iap.googleapis.com iam.googleapis.com modelarmor.googleapis.com"
OTHER_APIS="apphub.googleapis.com cloudidentity.googleapis.com cloudresourcemanager.googleapis.com orgpolicy.googleapis.com"

USER_ROLES_REQUIRED="roles/geminicloudassist.user roles/agentregistry.viewer"
USER_ROLES_EDITOR="roles/geminicloudassist.editor roles/aiplatform.editor"

ACCOUNT=""
ORG_ID=""
ORG_NAME=""
MGMT_PROJECT_ID=""
MGMT_PROJECT_NUMBER=""
DOMAIN=""
USERS_GROUP=""
USERS_MEMBER_TYPE=""
EDITOR_ROLES=""
MODEL_ARMOR=""
OUT=""
STRICT=0
LIVE_NUMBER=""
SINCE=""
FROM=""
G_OUT=""
G_ERR=""
G_RC=0

FAILED=0

usage() {
  cat <<'EOF'
Read-only status checks for the Cloud Operator organization admin setup.

Usage: admin-status.sh <check> [options]

Checks:
  preflight    gcloud version and beta, curl, account, project, org placement, billing
  roles        the admin's permissions on the organization and the project
  apis         required APIs enabled on the management project
  group        the users group exists (and the admin is a member)
  user-iam     the users group has its roles; warns about broad basic roles
  agent-iam    the agent principal set has roles/agentregistry.viewer
  orgpolicy    iam.managed.disableAccessPolicyBinding is not enforced
  deps         the PDP and IAP data egress policy (extension) bindings
  modelarmor   the Model Armor template (in 'us') and its binding
  uap          the UAP egress access policy, its rules and its binding
  apphub       the App Hub boundary points at the management project
  console      the organization is bound to the management project (Admin Onboarding Console)
  all          every check above, as raw lines
  summary      every check, as a fixed one-row-per-step table (print it verbatim), the
               saved choices, the raw lines, and with --since this session's changes
  changes      the change-log lines since --since TIME (no live checks)
  render-uap   write the UAP rules for this org/project to --out FILE (no checks)
  paths        print where this org/project's state file and change log are
  list         list the organizations and projects with saved setups

Every check except list needs --org and --project. Other options default to the
values saved for that org/project in
~/.config/cloud-operator/admin-setup/<ORG_ID>/<PROJECT_ID>/state.env, and the
values you pass are saved there. Results always come from live calls.

Options:
  --account EMAIL       the admin's gcloud account (ADMIN_ACCOUNT)
  --org ID              organization ID (ORG_ID)
  --org-name NAME       organization name, checked by preflight (ORG_NAME)
  --project ID          management project ID (MGMT_PROJECT_ID)
  --project-number N    management project number, checked by preflight (MGMT_PROJECT_NUMBER)
  --domain DOMAIN       organization domain, for the group name (DOMAIN)
  --group EMAIL         users group (USERS_GROUP, default autocloud-users@DOMAIN)
  --member-type group|user  'user' when a single user stands in for the group (USERS_MEMBER_TYPE)
  --editor-roles yes|no whether the group gets the two editor roles (EDITOR_ROLES, default yes)
  --model-armor yes|no  whether Model Armor is wanted (MODEL_ARMOR, default yes)
  --out FILE            output file for render-uap
  --since TIME          UTC start time (YYYY-MM-DDTHH:MM:SSZ) for summary and changes

  --strict              exit with status 1 if anything is MISSING

Each line starts with OK, MISSING, WARN, UNKNOWN (couldn't read it) or SKIP.
Exit status: 0 when the checks ran (read the lines for the results; with
--strict, 1 if anything is MISSING), 2 on usage errors. A MISSING line is a
normal result, not an error, so callers that treat a non-zero exit as a failure
don't report one.
EOF
}

# Reads KEY=value lines from the state file without executing it.
load_state() {
  [ -f "$STATE_FILE" ] || return 0
  local key value
  while IFS='=' read -r key value; do
    case "$key" in
      '' | \#*) continue ;;
    esac
    value="${value%\"}"
    value="${value#\"}"
    case "$key" in
      ADMIN_ACCOUNT) [ -n "$ACCOUNT" ] || ACCOUNT="$value" ;;
      ORG_ID) [ -n "$ORG_ID" ] || ORG_ID="$value" ;;
      ORG_NAME) [ -n "$ORG_NAME" ] || ORG_NAME="$value" ;;
      MGMT_PROJECT_ID) [ -n "$MGMT_PROJECT_ID" ] || MGMT_PROJECT_ID="$value" ;;
      MGMT_PROJECT_NUMBER) [ -n "$MGMT_PROJECT_NUMBER" ] || MGMT_PROJECT_NUMBER="$value" ;;
      DOMAIN) [ -n "$DOMAIN" ] || DOMAIN="$value" ;;
      USERS_GROUP) [ -n "$USERS_GROUP" ] || USERS_GROUP="$value" ;;
      USERS_MEMBER_TYPE) [ -n "$USERS_MEMBER_TYPE" ] || USERS_MEMBER_TYPE="$value" ;;
      EDITOR_ROLES) [ -n "$EDITOR_ROLES" ] || EDITOR_ROLES="$value" ;;
      MODEL_ARMOR) [ -n "$MODEL_ARMOR" ] || MODEL_ARMOR="$value" ;;
    esac
  done <"$STATE_FILE"
}

line() { # line STATUS CHECK MESSAGE
  printf '%-8s %-11s %s\n' "$1" "$2" "$3"
  if [ "$1" = "MISSING" ]; then FAILED=1; fi
}

need() { # need VAR_VALUE OPTION
  if [ -z "$1" ]; then
    printf 'ERROR: %s is needed (pass it once; it is then saved for this org and project)\n' "$2" >&2
    exit 2
  fi
}

# Saves the current inputs to the state file, only if something changed.
# Nothing is saved until the admin account is known, so a mistyped org or
# project doesn't leave a state file behind.
save_state() {
  local tmp key value content
  [ -n "$ACCOUNT" ] || return 0
  content=""
  for key in ADMIN_ACCOUNT ORG_NAME ORG_ID MGMT_PROJECT_ID MGMT_PROJECT_NUMBER DOMAIN \
    USERS_GROUP USERS_MEMBER_TYPE EDITOR_ROLES MODEL_ARMOR; do
    case "$key" in
      ADMIN_ACCOUNT) value="$ACCOUNT" ;;
      *) eval "value=\"\${$key}\"" ;;
    esac
    [ -n "$value" ] || continue
    content="$content$key=\"$value\"
"
  done
  if [ -f "$STATE_FILE" ] && [ "$(cat "$STATE_FILE")
" = "$content" ]; then
    return 0
  fi
  mkdir -p "$STATE_DIR"
  tmp="$STATE_FILE.tmp.$$"
  printf '%s' "$content" >"$tmp" && mv "$tmp" "$STATE_FILE"
}

list_setups() {
  local f found=0
  for f in "$ADMIN_HOME"/*/*/state.env; do
    [ -f "$f" ] || continue
    found=1
    printf 'organization %s (%s), project %s, admin %s\n' \
      "$(sed -n 's/^ORG_ID="\(.*\)"$/\1/p' "$f")" \
      "$(sed -n 's/^ORG_NAME="\(.*\)"$/\1/p' "$f")" \
      "$(sed -n 's/^MGMT_PROJECT_ID="\(.*\)"$/\1/p' "$f")" \
      "$(sed -n 's/^ADMIN_ACCOUNT="\(.*\)"$/\1/p' "$f")"
  done
  [ "$found" -eq 1 ] || printf 'no saved setups in %s\n' "$ADMIN_HOME"
}

# gcloud as the admin, never prompting.
g() { gcloud "$@" --account="$ACCOUNT" --quiet 2>/dev/null; }

# run_g [env VAR=value ...] gcloud ARGS...: runs a command as the admin and
# keeps its error, so a failed read isn't mistaken for "doesn't exist". Sets
# G_OUT (stdout), G_RC (exit status) and G_ERR (gcloud's ERROR line, or the
# first meaningful stderr line).
run_g() {
  local errf
  errf="$(mktemp)"
  G_OUT="$("$@" --account="$ACCOUNT" --quiet 2>"$errf")"
  G_RC=$?
  G_ERR="$(grep -E '^ERROR:' "$errf" | head -n 1)"
  [ -n "$G_ERR" ] || G_ERR="$(grep -v -E '^[[:space:]]*$|WARNING|\.go:[0-9]+|0x[0-9a-f]{6,}' "$errf" | head -n 1)"
  G_ERR="$(printf '%s' "$G_ERR" | cut -c1-240)"
  rm -f "$errf"
}

is_not_found() {
  case "$1" in
    *NOT_FOUND* | *'not found'* | *'does not exist'*) return 0 ;;
  esac
  return 1
}

# The project number as gcloud reports it now (set once per run by main).
project_number() {
  printf '%s' "$LIVE_NUMBER"
}

agent_principal() {
  printf 'principalSet://agents.global.org-%s.system.id.goog/attribute.platformContainer/aiplatform/projects/%s' \
    "$ORG_ID" "$(project_number)"
}

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

# Prints the permissions the admin holds, out of the ones given, on a resource
# (projects/ID or organizations/ID), one per line. Uses testIamPermissions, so
# grants through groups and inherited from the organization count. Returns 2 if
# it couldn't ask.
granted_permissions() {
  local resource="$1" token perms resp
  shift
  token="$(gcloud auth print-access-token --account="$ACCOUNT" 2>/dev/null)" || return 2
  [ -n "$token" ] || return 2
  perms="$(printf '"%s",' "$@")"
  perms="[${perms%,}]"
  # The token goes through stdin, so it doesn't show up in the process list.
  resp="$(printf 'Authorization: Bearer %s\n' "$token" |
    curl -sS -X POST -H @- -H 'Content-Type: application/json' \
      -d "{\"permissions\":$perms}" \
      "https://cloudresourcemanager.googleapis.com/v3/$resource:testIamPermissions" 2>/dev/null)" || return 2
  case "$resp" in
    *'"error"'*) return 2 ;;
  esac
  printf '%s' "$resp" | tr ',' '\n' | sed -n 's/.*"\([a-zA-Z]*\.[a-zA-Z.]*\)".*/\1/p'
}

# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

check_preflight() {
  local version major acct_found parent billing
  if ! command -v gcloud >/dev/null 2>&1; then
    line MISSING preflight "gcloud isn't installed (https://cloud.google.com/sdk/docs/install)"
    return
  fi
  version="$(gcloud version --format='value("Google Cloud SDK")' 2>/dev/null)"
  major="${version%%.*}"
  case "$major" in
    '' | *[!0-9]*) line UNKNOWN preflight "couldn't read the gcloud version" ;;
    *)
      if [ "$major" -ge "$MIN_GCLOUD_MAJOR" ]; then
        line OK preflight "gcloud $version"
      else
        line MISSING preflight "gcloud $version is older than $MIN_GCLOUD_MAJOR.0.0: run gcloud components update"
      fi
      ;;
  esac
  if gcloud beta service-extensions extension-bindings --help >/dev/null 2>&1; then
    line OK preflight "gcloud beta commands available"
  else
    line MISSING preflight "gcloud beta commands missing: run gcloud components install beta"
  fi
  if command -v curl >/dev/null 2>&1; then
    line OK preflight "curl available"
  else
    line MISSING preflight "curl isn't installed (needed for the permission checks)"
  fi
  if command -v python3 >/dev/null 2>&1; then
    line OK preflight "python3 available"
  else
    line WARN preflight "python3 isn't installed: the UAP rule comparison (Step 10) will show UNKNOWN until it is"
  fi

  need "$ACCOUNT" --account
  acct_found="$(gcloud auth list --filter="account:$ACCOUNT" --format='value(account)' 2>/dev/null)"
  if [ -n "$acct_found" ]; then
    line OK preflight "signed in to gcloud as $ACCOUNT"
  else
    line MISSING preflight "$ACCOUNT isn't signed in to gcloud: run gcloud auth login $ACCOUNT"
  fi
  case "$(lower "$ACCOUNT")" in
    *@gmail.com) line WARN preflight "$ACCOUNT is a consumer account; use your organization's admin account" ;;
    *@google.com) line WARN preflight "$ACCOUNT is a google.com account; use your own organization's admin account" ;;
  esac
  if [ -n "$DOMAIN" ]; then
    case "$(lower "$ACCOUNT")" in
      *"@$(lower "$DOMAIN")") ;;
      *) line WARN preflight "$ACCOUNT isn't in the domain $DOMAIN" ;;
    esac
  fi

  need "$ORG_ID" --org
  need "$MGMT_PROJECT_ID" --project
  local actual_number="$LIVE_NUMBER" org_name
  if [ -z "$actual_number" ]; then
    line MISSING preflight "can't read project $MGMT_PROJECT_ID as $ACCOUNT (wrong ID, or no access)"
    return
  fi
  if [ -z "$MGMT_PROJECT_NUMBER" ] || [ "$MGMT_PROJECT_NUMBER" = "$actual_number" ]; then
    line OK preflight "project $MGMT_PROJECT_ID (number $actual_number)"
  else
    line MISSING preflight "project $MGMT_PROJECT_ID has number $actual_number, not $MGMT_PROJECT_NUMBER: check which project you meant"
  fi
  org_name="$(g organizations describe "$ORG_ID" --format='value(displayName)')"
  if [ -z "$org_name" ]; then
    line UNKNOWN preflight "can't read organization $ORG_ID as $ACCOUNT (wrong ID, or no access)"
  elif [ -z "$ORG_NAME" ] || [ "$(lower "$ORG_NAME")" = "$(lower "$org_name")" ]; then
    line OK preflight "organization $ORG_ID ($org_name)"
  else
    line WARN preflight "organization $ORG_ID is named $org_name, not $ORG_NAME: check which organization you meant"
  fi
  parent="$(g projects describe "$MGMT_PROJECT_ID" --format='value(parent.type,parent.id)' | tr '\t' ' ')"
  case "$parent" in
    "organization $ORG_ID") line OK preflight "project is directly under organization $ORG_ID" ;;
    "folder "*) line MISSING preflight "project is in a folder ($parent); it must sit directly under the organization" ;;
    '') line UNKNOWN preflight "couldn't read the project's parent" ;;
    *) line MISSING preflight "project's parent is $parent, not organization $ORG_ID" ;;
  esac
  billing="$(g billing projects describe "$MGMT_PROJECT_ID" --format='value(billingEnabled)')"
  case "$(lower "$billing")" in
    true) line OK preflight "billing is enabled" ;;
    false) line MISSING preflight "billing isn't enabled on $MGMT_PROJECT_ID" ;;
    *) line UNKNOWN preflight "couldn't read billing (needs billing.resourceAssociations.list); check it in the console" ;;
  esac
}

# Permission that stands for each admin role, as "permission|role|why".
ORG_ROLE_CHECKS="resourcemanager.organizations.setIamPolicy|roles/resourcemanager.organizationAdmin|grant organization-level roles
orgpolicy.policy.set|roles/orgpolicy.policyAdmin|change organization policy constraints
resourcemanager.capabilityConfigs.list|roles/resourcemanager.editor|let the AutoCloud console find the organization's management project
resourcemanager.capabilityConfigs.create|roles/resourcemanager.editor|let Complete setup bind the organization to the management project"
PROJECT_ROLE_CHECKS="resourcemanager.projects.setIamPolicy|roles/resourcemanager.projectIamAdmin|grant IAM roles on the management project
serviceusage.services.enable|roles/serviceusage.serviceUsageAdmin|enable APIs
orgpolicy.policy.set|roles/orgpolicy.policyAdmin|override iam.managed.disableAccessPolicyBinding on the project
networkservices.extensionBindings.create|roles/networkservices.serviceExtensionsAdmin (or project Owner)|create data egress policy bindings
iam.accesspolicies.create|roles/iam.accessPolicyAdmin|create the UAP egress policy
iam.accesspolicies.bind|roles/iam.accessPolicyAdmin|bind the UAP egress policy
resourcemanager.projects.createPolicyBinding|roles/resourcemanager.projectIamAdmin|bind the UAP egress policy to the project
apphub.boundaries.update|roles/apphub.admin|set up the App Hub boundary"
MA_ROLE_CHECK="modelarmor.templates.create|roles/modelarmor.admin|create the Model Armor template"

check_role_list() { # check_role_list RESOURCE LABEL CHECKS
  local resource="$1" label="$2" checks="$3" perms granted perm role why
  perms="$(printf '%s\n' "$checks" | cut -d'|' -f1 | tr '\n' ' ')"
  # shellcheck disable=SC2086 # perms is a word list on purpose
  if ! granted="$(granted_permissions "$resource" $perms)"; then
    line UNKNOWN roles "couldn't check permissions on $label (testIamPermissions failed)"
    return
  fi
  while IFS='|' read -r perm role why; do
    [ -n "$perm" ] || continue
    if printf '%s\n' "$granted" | grep -qx "$perm"; then
      line OK roles "$label: $perm ($role)"
    else
      line MISSING roles "$label: $perm, needed to $why: grant $role"
    fi
  done <<EOF
$checks
EOF
}

check_roles() {
  need "$ACCOUNT" --account
  need "$ORG_ID" --org
  need "$MGMT_PROJECT_ID" --project
  check_role_list "organizations/$ORG_ID" "organization $ORG_ID" "$ORG_ROLE_CHECKS"
  if [ "$(lower "${MODEL_ARMOR:-yes}")" = "no" ]; then
    check_role_list "projects/$MGMT_PROJECT_ID" "project $MGMT_PROJECT_ID" "$PROJECT_ROLE_CHECKS"
  else
    check_role_list "projects/$MGMT_PROJECT_ID" "project $MGMT_PROJECT_ID" "$PROJECT_ROLE_CHECKS
$MA_ROLE_CHECK"
  fi
}

check_apis() {
  need "$MGMT_PROJECT_ID" --project
  local enabled api
  enabled="$(g services list --enabled --project="$MGMT_PROJECT_ID" --format='value(config.name)')"
  if [ -z "$enabled" ]; then
    line UNKNOWN apis "couldn't list enabled APIs on $MGMT_PROJECT_ID"
    return
  fi
  for api in $CORE_APIS $EGRESS_APIS $OTHER_APIS; do
    if printf '%s\n' "$enabled" | grep -qx "$api"; then
      line OK apis "$api"
    else
      line MISSING apis "$api isn't enabled"
    fi
  done
}

users_group() {
  if [ -z "$USERS_GROUP" ] && [ -n "$DOMAIN" ]; then USERS_GROUP="autocloud-users@$DOMAIN"; fi
  printf '%s' "$USERS_GROUP"
}

check_group() {
  need "$MGMT_PROJECT_ID" --project
  local group out member
  group="$(users_group)"
  if [ -z "$group" ]; then
    line SKIP group "no users group or domain saved yet"
    return
  fi
  if [ "$(lower "$USERS_MEMBER_TYPE")" = "user" ]; then
    line WARN group "using the single user $group instead of a group; create autocloud-users@${DOMAIN:-<domain>} later"
    return
  fi
  if ! out="$(gcloud identity groups describe "$group" --account="$ACCOUNT" \
    --billing-project="$MGMT_PROJECT_ID" --quiet --format='value(name)' 2>&1)"; then
    case "$out" in
      *'not been used'* | *SERVICE_DISABLED* | *'it is disabled'*)
        line UNKNOWN group "cloudidentity.googleapis.com isn't enabled on $MGMT_PROJECT_ID yet" ;;
      *NOT_FOUND* | *'does not exist'* | *'not found'*)
        line MISSING group "$group doesn't exist" ;;
      *PERMISSION_DENIED*)
        line UNKNOWN group "no permission to read $group" ;;
      *) line UNKNOWN group "couldn't read $group" ;;
    esac
    return
  fi
  line OK group "$group exists"
  member="$(gcloud identity groups memberships check-transitive-membership \
    --group-email="$group" --member-email="$ACCOUNT" --account="$ACCOUNT" \
    --billing-project="$MGMT_PROJECT_ID" --quiet --format='value(hasMembership)' 2>/dev/null)"
  case "$(lower "$member")" in
    true) line OK group "$ACCOUNT is a member" ;;
    false) line WARN group "$ACCOUNT isn't a member of $group" ;;
    *) line UNKNOWN group "couldn't check whether $ACCOUNT is a member" ;;
  esac
  run_g gcloud identity groups memberships list --group-email="$group" \
    --billing-project="$MGMT_PROJECT_ID" --format='value(preferredMemberKey.id)'
  if [ "$G_RC" -eq 0 ]; then
    line OK group "members: $(printf '%s\n' "$G_OUT" | grep -v '^$' | tr '\n' ',' | sed 's/,$//; s/,/, /g')"
  else
    line UNKNOWN group "couldn't list the members of $group: ${G_ERR:-unknown error}"
  fi
}

# One line per grant: role|member|condition title (empty when unconditional).
project_policy() {
  g projects get-iam-policy "$MGMT_PROJECT_ID" --flatten='bindings[].members' \
    --format='value[separator="|"](bindings.role,bindings.members,bindings.condition.title)'
}

# grant_state POLICY ROLE MEMBER: prints "yes" for an unconditional grant,
# "conditional" when the role is only granted with a condition, else "no".
grant_state() {
  if printf '%s\n' "$1" | grep -qix "$2|$3|"; then
    printf 'yes'
  elif printf '%s\n' "$1" | grep -qi "^$2|$3|."; then
    printf 'conditional'
  else
    printf 'no'
  fi
}

check_user_iam() {
  need "$MGMT_PROJECT_ID" --project
  local policy group role broad
  policy="$(project_policy)"
  if [ -z "$policy" ]; then
    line UNKNOWN user-iam "couldn't read the IAM policy of $MGMT_PROJECT_ID"
    return
  fi
  group="$(users_group)"
  if [ -z "$group" ]; then
    line SKIP user-iam "no users group saved yet"
  else
    # Every role is checked live; EDITOR_ROLES=no only turns a missing
    # editor role into SKIP instead of MISSING.
    local kind=group state
    if [ "$(lower "$USERS_MEMBER_TYPE")" = "user" ]; then kind=user; fi
    for role in $USER_ROLES_REQUIRED $USER_ROLES_EDITOR; do
      state="$(grant_state "$policy" "$role" "$kind:$group")"
      if [ "$state" = "yes" ]; then
        line OK user-iam "$role → $group"
      elif [ "$state" = "conditional" ]; then
        line WARN user-iam "$role is only granted to $group with a condition (it may expire or not apply); grant it without a condition"
      elif [ "$(lower "${EDITOR_ROLES:-yes}")" = "no" ] &&
        case " $USER_ROLES_EDITOR " in *" $role "*) true ;; *) false ;; esac; then
        line SKIP user-iam "$role not granted to $group (optional; not wanted)"
      else
        line MISSING user-iam "$role isn't granted to $group"
      fi
    done
  fi
  # Basic roles on the management project let people read everyone's
  # conversations during Private Preview. Service accounts are left out.
  broad="$(printf '%s\n' "$policy" | grep -E '^roles/(viewer|editor|owner)\|(user|group|domain):' |
    cut -d'|' -f1,2 | grep -v "|user:$ACCOUNT\$" | sed 's/^roles\/\([a-z]*\)|/\1 /' | tr '\n' ',' | sed 's/,$//; s/,/, /g')"
  if [ -n "$broad" ]; then
    line WARN user-iam "basic roles on the management project let these members read everyone's conversations: $broad"
  else
    line OK user-iam "no basic roles granted to other users or groups"
  fi
}

check_agent_iam() {
  need "$ORG_ID" --org
  need "$MGMT_PROJECT_ID" --project
  local policy principal
  policy="$(project_policy)"
  if [ -z "$policy" ]; then
    line UNKNOWN agent-iam "couldn't read the IAM policy of $MGMT_PROJECT_ID"
    return
  fi
  principal="$(agent_principal)"
  case "$(grant_state "$policy" "roles/agentregistry.viewer" "$principal")" in
    yes) line OK agent-iam "roles/agentregistry.viewer → agent principal set" ;;
    conditional) line WARN agent-iam "the agent principal set only has roles/agentregistry.viewer with a condition; grant it without one" ;;
    *) line MISSING agent-iam "the agent principal set doesn't have roles/agentregistry.viewer" ;;
  esac
}

check_orgpolicy() {
  need "$MGMT_PROJECT_ID" --project
  local fields count enforce dry conds
  run_g gcloud org-policies describe "$ORG_POLICY_CONSTRAINT" --project="$MGMT_PROJECT_ID" --effective \
    --format='value[separator="|"](spec.rules.len(),spec.rules[0].enforce,dryRunSpec.rules.len())'
  if [ "$G_RC" -ne 0 ]; then
    line UNKNOWN orgpolicy "couldn't read the effective $ORG_POLICY_CONSTRAINT policy: ${G_ERR:-unknown error}"
    return
  fi
  fields="$G_OUT"
  count="$(printf '%s' "$fields" | cut -d'|' -f1)"
  enforce="$(lower "$(printf '%s' "$fields" | cut -d'|' -f2)")"
  dry="$(printf '%s' "$fields" | cut -d'|' -f3)"
  run_g gcloud org-policies describe "$ORG_POLICY_CONSTRAINT" --project="$MGMT_PROJECT_ID" --effective \
    --format='value(spec.rules[].condition.expression)'
  conds="$(printf '%s' "$G_OUT" | tr -d '[:space:];')"
  case "$count" in '' | 0) count=0 ;; esac
  if [ "$count" -eq 0 ]; then
    line MISSING orgpolicy "$ORG_POLICY_CONSTRAINT has no rule in the effective policy of $MGMT_PROJECT_ID; it's enforced by default, so set the override"
  elif [ "$count" -gt 1 ] || [ -n "$conds" ]; then
    line UNKNOWN orgpolicy "$ORG_POLICY_CONSTRAINT has conditional or multiple rules on $MGMT_PROJECT_ID; check it in the console"
  elif [ "$enforce" = "false" ]; then
    line OK orgpolicy "$ORG_POLICY_CONSTRAINT isn't enforced on $MGMT_PROJECT_ID"
  elif [ "$enforce" = "true" ]; then
    line MISSING orgpolicy "$ORG_POLICY_CONSTRAINT is enforced on $MGMT_PROJECT_ID"
  else
    line UNKNOWN orgpolicy "unexpected rule for $ORG_POLICY_CONSTRAINT on $MGMT_PROJECT_ID: '$enforce'"
  fi
  case "$dry" in
    '' | 0) ;;
    *) line WARN orgpolicy "$ORG_POLICY_CONSTRAINT also has a dry-run spec on $MGMT_PROJECT_ID (doesn't change enforcement)" ;;
  esac
}

# Lists the project's extension bindings, one per line:
# name|producer|scope parent|resource types (;-separated)|model_armor_settings.
# Sets G_RC and G_ERR (see run_g).
EXT_LIST=""
list_extension_bindings() {
  run_g gcloud beta service-extensions extension-bindings list --project="$MGMT_PROJECT_ID" --location=global \
    --format='value[separator="|"](name.basename(),producerExtension,target.scope.parent,target.scope.resourceTypes,producerMetadata.model_armor_settings)'
  EXT_LIST="$G_OUT"
}

# check_binding LIST CHECK ID PRODUCER [TEMPLATE]: the binding must exist, use
# PRODUCER, be scoped to this project's AI applications and, with TEMPLATE,
# send requests and responses to that Model Armor template.
check_binding() {
  local row producer parent types meta number
  number="$(project_number)"
  row="$(printf '%s\n' "$1" | grep "^$3|" | head -n 1)"
  if [ -z "$row" ]; then
    line MISSING "$2" "extension binding $3 doesn't exist"
    return
  fi
  producer="$(printf '%s' "$row" | cut -d'|' -f2)"
  parent="$(printf '%s' "$row" | cut -d'|' -f3)"
  types="$(printf '%s' "$row" | cut -d'|' -f4)"
  meta="$(printf '%s' "$row" | cut -d'|' -f5-)"
  if [ "$producer" != "$4" ]; then
    line MISSING "$2" "$3 points at $producer, expected $4: recreate it"
  elif [ "$parent" != "projects/$number" ] && [ "$parent" != "projects/$MGMT_PROJECT_ID" ]; then
    line MISSING "$2" "$3 is scoped to '$parent', expected projects/$number: recreate it"
  elif ! printf '%s' "$types" | tr ';' '\n' | tr ',' '\n' | grep -qx 'AI_APPLICATION'; then
    line MISSING "$2" "$3 covers resource types '$types', expected AI_APPLICATION: recreate it"
  elif [ -n "${5:-}" ] && ! { printf '%s' "$meta" | grep -q "\"request_template_id\": *\"$5\"" &&
    printf '%s' "$meta" | grep -q "\"response_template_id\": *\"$5\""; }; then
    line MISSING "$2" "$3 doesn't send requests and responses to $5 (it has: ${meta:-no template}): recreate it"
  else
    line OK "$2" "$3 → $4 (scope projects/$number, AI applications)"
  fi
}

check_deps() {
  need "$MGMT_PROJECT_ID" --project
  list_extension_bindings
  if [ "$G_RC" -ne 0 ]; then
    line UNKNOWN deps "couldn't list extension bindings: ${G_ERR:-unknown error}"
    return
  fi
  check_binding "$EXT_LIST" deps "$PDP_BINDING_ID" "$PDP_PRODUCER"
  check_binding "$EXT_LIST" deps "$IAP_BINDING_ID" "$IAP_PRODUCER"
}

check_modelarmor() {
  need "$MGMT_PROJECT_ID" --project
  local tmpl pi conf enforcement extra wanted=1 template_name
  template_name="projects/$MGMT_PROJECT_ID/locations/$MA_LOCATION/templates/$MA_TEMPLATE_ID"
  # Always checked live. MODEL_ARMOR=no only turns a real "doesn't exist" into
  # SKIP; a failed read is UNKNOWN either way.
  if [ "$(lower "${MODEL_ARMOR:-yes}")" = "no" ]; then wanted=0; fi
  # The endpoint override applies to this one command only.
  run_g env CLOUDSDK_API_ENDPOINT_OVERRIDES_MODELARMOR="$MA_ENDPOINT" gcloud model-armor templates describe \
    "$MA_TEMPLATE_ID" --location="$MA_LOCATION" --project="$MGMT_PROJECT_ID" \
    --format='value[separator="|"](filterConfig.piAndJailbreakFilterSettings.filterEnforcement,filterConfig.piAndJailbreakFilterSettings.confidenceLevel,templateMetadata.enforcementType,filterConfig.raiSettings,filterConfig.sdpSettings,filterConfig.maliciousUriFilterSettings)'
  tmpl="$G_OUT"
  if [ "$G_RC" -ne 0 ] && ! is_not_found "$G_ERR"; then
    line UNKNOWN modelarmor "couldn't read template $MA_TEMPLATE_ID in '$MA_LOCATION': ${G_ERR:-unknown error}"
  elif [ -z "$tmpl" ] && [ "$wanted" -eq 0 ]; then
    line SKIP modelarmor "no template $MA_TEMPLATE_ID in '$MA_LOCATION' (MODEL_ARMOR=no)"
  elif [ -z "$tmpl" ]; then
    line MISSING modelarmor "template $MA_TEMPLATE_ID doesn't exist in location '$MA_LOCATION'"
  else
    pi="$(printf '%s' "$tmpl" | cut -d'|' -f1)"
    conf="$(printf '%s' "$tmpl" | cut -d'|' -f2)"
    enforcement="$(printf '%s' "$tmpl" | cut -d'|' -f3)"
    extra="$(printf '%s' "$tmpl" | cut -d'|' -f4-)"
    case "$pi:$conf" in
      ENABLED:MEDIUM_AND_ABOVE | ENABLED:LOW_AND_ABOVE)
        line OK modelarmor "template $MA_TEMPLATE_ID in '$MA_LOCATION': prompt injection filter on ($conf)" ;;
      *) line MISSING modelarmor "template $MA_TEMPLATE_ID: prompt injection filter is '${pi:-unset}' at '${conf:-unset}' (needs ENABLED, MEDIUM_AND_ABOVE)" ;;
    esac
    case "$enforcement" in
      INSPECT_AND_BLOCK) line OK modelarmor "enforcement: inspect and block" ;;
      '') line MISSING modelarmor "enforcement type is unset (gcloud can't set it): run set-modelarmor-enforcement.sh --mode inspect-and-block" ;;
      *) line MISSING modelarmor "enforcement is '$enforcement', not INSPECT_AND_BLOCK: run set-modelarmor-enforcement.sh --mode inspect-and-block" ;;
    esac
    case "$extra" in
      *[!\|]*) line WARN modelarmor "other filters are on (responsible AI, sensitive data or malicious URL); the guide turns them off to avoid blocking normal diagnostic data" ;;
    esac
  fi
  list_extension_bindings
  if [ "$G_RC" -ne 0 ]; then
    line UNKNOWN modelarmor "couldn't list extension bindings to check $MA_BINDING_ID: ${G_ERR:-unknown error}"
  elif [ "$wanted" -eq 0 ] && ! printf '%s\n' "$EXT_LIST" | grep -q "^$MA_BINDING_ID|"; then
    line SKIP modelarmor "no binding $MA_BINDING_ID (MODEL_ARMOR=no)"
  else
    check_binding "$EXT_LIST" modelarmor "$MA_BINDING_ID" "$MA_PRODUCER" "$template_name"
  fi
}

# Prints the UAP rules with this org and project filled in.
render_uap() {
  need "$ORG_ID" --org
  need "$MGMT_PROJECT_ID" --project
  local number
  number="$(project_number)"
  [ -n "$number" ] || {
    printf "ERROR: couldn't read the project number of %s\n" "$MGMT_PROJECT_ID" >&2
    exit 1
  }
  case "$ORG_ID" in *[!0-9]*) printf 'ERROR: --org must be numeric\n' >&2; exit 2 ;; esac
  case "$number" in *[!0-9]*) printf 'ERROR: unexpected project number %s\n' "$number" >&2; exit 1 ;; esac
  sed -e "s/__ORG_ID__/$ORG_ID/g" -e "s/__PROJECT_NUMBER__/$number/g" "$UAP_TEMPLATE"
}

check_uap() {
  need "$ORG_ID" --org
  need "$MGMT_PROJECT_ID" --project
  local number live verdict expected rows row name policy target cond kind found=0
  number="$(project_number)"
  run_g gcloud iam access-policies describe "$UAP_POLICY_ID" --project="$MGMT_PROJECT_ID" \
    --location=global --format='json(details.rules)'
  live="$G_OUT"
  if [ "$G_RC" -ne 0 ] && is_not_found "$G_ERR"; then
    line MISSING uap "access policy $UAP_POLICY_ID doesn't exist"
  elif [ "$G_RC" -ne 0 ]; then
    line UNKNOWN uap "couldn't read access policy $UAP_POLICY_ID: ${G_ERR:-unknown error}"
  elif ! command -v python3 >/dev/null 2>&1; then
    line UNKNOWN uap "access policy $UAP_POLICY_ID exists, but its rules can't be compared without python3"
  else
    verdict="$(render_uap | LIVE="$live" python3 -c '
import json, os, sys

def clean(v):
    # Drop empty values the API may add, so only real differences count.
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items() if x not in ({}, [], "", None)}
    if isinstance(v, list):
        return [clean(x) for x in v]
    return v

want = json.load(sys.stdin)
live = json.loads(os.environ["LIVE"] or "{}").get("details", {}).get("rules", [])
key = lambda rules: sorted(json.dumps(clean(r), sort_keys=True) for r in rules)
print("same %d" % len(want) if key(want) == key(live) else "differ %d %d" % (len(live), len(want)))
')"
    case "$verdict" in
      same*) line OK uap "access policy $UAP_POLICY_ID has the ${verdict#same } expected rules (the bundled AutoCloud rules)" ;;
      differ*)
        expected="${verdict##* }"
        verdict="${verdict#differ }"
        line MISSING uap "access policy $UAP_POLICY_ID has ${verdict%% *} rules that differ from the $expected expected ones: update it (Step 10b)" ;;
      *) line UNKNOWN uap "couldn't compare the rules of $UAP_POLICY_ID" ;;
    esac
  fi

  # The binding must attach exactly this policy to exactly this project, with
  # no condition. Other access policies on the project or organization are
  # reported for review: they can widen or block agent egress.
  run_g gcloud iam policy-bindings list --project="$MGMT_PROJECT_ID" --location=global \
    --format='value[separator="|"](name.basename(),policy,target.resource,condition.expression,policyKind)'
  if [ "$G_RC" -ne 0 ]; then
    line UNKNOWN uap "couldn't list the project's policy bindings: ${G_ERR:-unknown error}"
  else
    rows="$G_OUT"
    while IFS='|' read -r name policy target cond kind; do
      [ -n "$name" ] || continue
      case "$policy" in
        "projects/$number/locations/global/accessPolicies/$UAP_POLICY_ID" | \
          "projects/$MGMT_PROJECT_ID/locations/global/accessPolicies/$UAP_POLICY_ID")
          if [ "$target" != "//cloudresourcemanager.googleapis.com/projects/$number" ] &&
            [ "$target" != "//cloudresourcemanager.googleapis.com/projects/$MGMT_PROJECT_ID" ]; then
            line MISSING uap "binding $name attaches $UAP_POLICY_ID to '$target', not this project"
          elif [ -n "$cond" ]; then
            line MISSING uap "binding $name has a condition ($cond), so $UAP_POLICY_ID may not apply; bind it without one"
          else
            found=1
            line OK uap "binding $name attaches $UAP_POLICY_ID to projects/$number (no condition)"
          fi
          ;;
        *)
          case "$kind" in
            '' | ACCESS) line WARN uap "another access policy is also bound to the project: $policy (binding $name); review it, it can widen or block agent egress" ;;
          esac
          ;;
      esac
    done <<EOF
$rows
EOF
    if [ "$found" -eq 0 ] && ! printf '%s\n' "$rows" | grep -q "accessPolicies/$UAP_POLICY_ID|"; then
      line MISSING uap "$UAP_POLICY_ID isn't bound to the project"
    fi
  fi
  run_g gcloud iam policy-bindings list --organization="$ORG_ID" --location=global \
    --format='value[separator="|"](name.basename(),policy,policyKind)'
  if [ "$G_RC" -ne 0 ]; then
    line WARN uap "couldn't list organization-level policy bindings (other access policies may apply): ${G_ERR:-unknown error}"
  else
    while IFS='|' read -r name policy kind; do
      [ -n "$name" ] || continue
      case "$kind" in
        '' | ACCESS) line WARN uap "an organization-level access policy also applies: $policy (binding $name); review it, it can widen or block agent egress" ;;
      esac
    done <<EOF
$G_OUT
EOF
  fi
}

check_apphub() {
  need "$MGMT_PROJECT_ID" --project
  local node
  if ! node="$(gcloud apphub boundary describe --project="$MGMT_PROJECT_ID" --location=global \
    --account="$ACCOUNT" --quiet --format='value(crmNode)' 2>/dev/null)"; then
    line UNKNOWN apphub "couldn't read the App Hub boundary (is apphub.googleapis.com enabled?)"
    return
  fi
  case "$node" in
    "projects/$MGMT_PROJECT_ID" | "projects/$(project_number)")
      line OK apphub "boundary → $node" ;;
    "organizations/$ORG_ID")
      line OK apphub "managed boundary covering organization $ORG_ID (it can't be updated and doesn't need to be)" ;;
    '') line MISSING apphub "the App Hub boundary isn't set" ;;
    *) line MISSING apphub "the App Hub boundary points at $node, not projects/$MGMT_PROJECT_ID or organizations/$ORG_ID" ;;
  esac
}

# The Admin Onboarding Console binds the organization to the management project
# through a Resource Manager capability config. Read-only evidence for Step 3;
# the skill still asks the admin and never skips the step because of it.
check_console() {
  need "$ORG_ID" --org
  need "$MGMT_PROJECT_ID" --project
  local number mp id others="" match=0 odd=""
  number="$(project_number)"
  run_g gcloud resource-manager capability-configs list --organization="$ORG_ID" \
    --format='value(managementProject)'
  if [ "$G_RC" -ne 0 ]; then
    line UNKNOWN console "couldn't list the organization's capability configs: ${G_ERR:-unknown error}"
    return
  fi
  while IFS= read -r mp; do
    [ -n "$mp" ] || continue
    case "$mp" in
      */projects/* | projects/*) id="${mp##*/projects/}"; id="${id#projects/}"; id="${id%%/*}" ;;
      *) id="$mp" ;;
    esac
    case "$id" in
      "$MGMT_PROJECT_ID" | "$number") match=1 ;;
      *[!a-z0-9.:-]*) odd="$odd $mp" ;;
      *) others="$others $mp" ;;
    esac
  done <<EOF
$G_OUT
EOF
  if [ "$match" -eq 1 ]; then
    line OK console "organization $ORG_ID is bound to management project $MGMT_PROJECT_ID (capability config)"
  elif [ -n "$odd" ]; then
    line UNKNOWN console "unexpected management project value(s):$odd; check the Admin Onboarding Console"
  elif [ -n "$others" ]; then
    line MISSING console "organization $ORG_ID is bound to a different management project:$others (permanent during Private Preview; escalate)"
  else
    line MISSING console "organization $ORG_ID isn't bound to a management project yet (Complete setup not done)"
  fi
}

# ---------------------------------------------------------------------------
# Summary: one row per step, with fixed status rules. The skill prints it as is.
# ---------------------------------------------------------------------------

step_title() {
  case "$1" in
    0) printf 'Preflight' ;;
    1) printf 'Admin roles' ;;
    2) printf 'APIs' ;;
    3) printf 'Admin Onboarding Console' ;;
    4) printf 'Users group and roles' ;;
    5) printf 'Agent principal set' ;;
    6) printf 'Org policy override' ;;
    7) printf 'Data egress policies' ;;
    8) printf 'Model Armor' ;;
    9) printf 'Egress bindings' ;;
    10) printf 'UAP egress policy' ;;
    11) printf 'App Hub boundary' ;;
  esac
}

# step_lines STEP FILE: the check lines that make up a step.
step_lines() {
  case "$1" in
    0) awk '$2 == "preflight"' "$2" ;;
    1) awk '$2 == "roles"' "$2" ;;
    2) awk '$2 == "apis"' "$2" ;;
    3) awk '$2 == "console"' "$2" ;;
    4) awk '$2 == "group" || $2 == "user-iam"' "$2" ;;
    5) awk '$2 == "agent-iam"' "$2" ;;
    6) awk '$2 == "orgpolicy"' "$2" ;;
    7) awk '$2 == "deps"' "$2" ;;
    8) awk '$2 == "modelarmor"' "$2" ;;
    9) awk -v b="$MA_BINDING_ID" '$2 == "deps" || ($2 == "modelarmor" && index($0, b))' "$2" ;;
    10) awk '$2 == "uap"' "$2" ;;
    11) awk '$2 == "apphub"' "$2" ;;
  esac
}

# Status rules: any MISSING -> ❌; else any UNKNOWN (or no lines) -> ❔, never
# ✅; else any WARN -> ⚠️; only SKIP -> ➖; only OK (and SKIP) -> ✅.
status_of() {
  local lines="$1"
  if [ -z "$lines" ]; then printf '❔'; return; fi
  if printf '%s\n' "$lines" | grep -q '^MISSING '; then printf '❌'; return; fi
  if printf '%s\n' "$lines" | grep -q '^UNKNOWN '; then printf '❔'; return; fi
  if printf '%s\n' "$lines" | grep -q '^WARN '; then printf '⚠️'; return; fi
  if ! printf '%s\n' "$lines" | grep -q '^OK '; then printf '➖'; return; fi
  printf '✅'
}

evidence_of() {
  local lines="$1" status="$2" want n skips
  case "$status" in
    ❌) want=MISSING ;;
    ❔) want=UNKNOWN ;;
    ⚠️) want=WARN ;;
    ➖) want=SKIP ;;
    *) want="" ;;
  esac
  if [ -z "$lines" ]; then
    printf 'no check output'
  elif [ -n "$want" ]; then
    printf '%s\n' "$lines" | grep "^$want " | head -n 1 | sed 's/  */ /g'
  else
    n="$(printf '%s\n' "$lines" | grep -c '^OK ')"
    skips="$(printf '%s\n' "$lines" | grep -c '^SKIP ')"
    if [ "$skips" -gt 0 ]; then printf 'all %s checks OK (%s skipped by a saved choice)' "$n" "$skips"; else printf 'all %s checks OK' "$n"; fi
  fi
}

# summarize FILE: prints the step table, saved choices, changes and raw lines.
summarize() {
  local file="$1" step lines status evidence iap
  printf 'Admin setup status: organization %s%s, project %s, admin %s (%s)\n\n' \
    "$ORG_ID" "${ORG_NAME:+ ($ORG_NAME)}" "$MGMT_PROJECT_ID" "${ACCOUNT:--}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '%-5s %-6s %-26s %s\n' 'Step' 'Status' 'Title' 'Evidence (quoted from the check lines)'
  for step in 0 1 2 3 4 5 6 7 8 9 10 11; do
    lines="$(step_lines "$step" "$file")"
    status="$(status_of "$lines")"
    evidence="$(evidence_of "$lines" "$status")"
    if [ "$step" -eq 10 ]; then
      # UAP rules are only enforced through the IAP egress binding (Step 7).
      iap="$(awk -v b="$IAP_BINDING_ID" '$2 == "deps" && index($0, b)' "$file" | head -n 1)"
      case "$iap" in
        OK\ *) ;;
        *) if [ "$status" = "✅" ] || [ "$status" = "⚠️" ] || [ "$status" = "❔" ]; then
             status="❌"
             evidence="UAP is only enforced through the IAP egress binding (Step 7), which isn't OK: $(printf '%s' "${iap:-no IAP binding line}" | sed 's/  */ /g')"
           fi ;;
      esac
    fi
    printf '%-5s %-6s %-26s %s\n' "$step" "$status" "$(step_title "$step")" "$evidence"
  done
  printf '\nSaved choices (they only turn a real "doesn'"'"'t exist" into ➖ SKIP):\n'
  printf '  MODEL_ARMOR=%s\n' "${MODEL_ARMOR:-yes (default)}"
  printf '  EDITOR_ROLES=%s\n' "${EDITOR_ROLES:-yes (default)}"
  printf '  USERS_MEMBER_TYPE=%s\n' "${USERS_MEMBER_TYPE:-group (default)}"
  if [ -n "$SINCE" ]; then
    printf '\n'
    print_changes
  fi
  printf '\nRaw check lines:\n'
  sed 's/^/  /' "$file"
}

# Prints this org/project's change-log lines since $SINCE, with counts.
print_changes() {
  local lines ok failed
  if [ ! -f "$LOG_FILE" ]; then
    printf 'Changes since %s: none (no change log yet)\n' "$SINCE"
    return
  fi
  lines="$(awk -F '\t' -v since="$SINCE" '$1 >= since' "$LOG_FILE")"
  ok="$(printf '%s\n' "$lines" | awk -F '\t' '$4 == "OK"' | grep -c .)"
  failed="$(printf '%s\n' "$lines" | awk -F '\t' '$4 ~ /^FAILED/' | grep -c .)"
  printf 'Changes since %s: %s OK, %s FAILED (from %s)\n' "$SINCE" "$ok" "$failed" "$LOG_FILE"
  [ -n "$lines" ] && printf '%s\n' "$lines" | awk -F '\t' '{ printf "  %s  %s  %s  %s%s\n", $1, $3, $4, $5, ($6 != "" ? "  (" $6 ")" : "") }'
  return 0
}

run_all_checks() {
  check_preflight
  check_roles
  check_apis
  check_console
  check_group
  check_user_iam
  check_agent_iam
  check_orgpolicy
  check_deps
  check_modelarmor
  check_uap
  check_apphub
}

main() {
  local check="${1:-}"
  [ -n "$check" ] || {
    usage
    exit 2
  }
  shift
  while [ $# -gt 0 ]; do
    case "$1" in
      --account) ACCOUNT="${2:-}"; shift 2 ;;
      --org) ORG_ID="${2:-}"; shift 2 ;;
      --project) MGMT_PROJECT_ID="${2:-}"; shift 2 ;;
      --project-number) MGMT_PROJECT_NUMBER="${2:-}"; shift 2 ;;
      --org-name) ORG_NAME="${2:-}"; shift 2 ;;
      --domain) DOMAIN="${2:-}"; shift 2 ;;
      --group) USERS_GROUP="${2:-}"; shift 2 ;;
      --member-type) USERS_MEMBER_TYPE="${2:-}"; shift 2 ;;
      --editor-roles) EDITOR_ROLES="${2:-}"; shift 2 ;;
      --model-armor) MODEL_ARMOR="${2:-}"; shift 2 ;;
      --out) OUT="${2:-}"; shift 2 ;;
      --since) SINCE="${2:-}"; shift 2 ;;
      --from) FROM="${2:-}"; shift 2 ;;
      --strict) STRICT=1; shift ;;
      -h | --help) usage; exit 0 ;;
      *) printf 'ERROR: unknown option %s (see --help)\n' "$1" >&2; exit 2 ;;
    esac
  done
  case "$check" in
    -h | --help) usage; exit 0 ;;
    list) list_setups; exit 0 ;;
    preflight | roles | apis | group | user-iam | agent-iam | orgpolicy | deps | modelarmor | uap | apphub | console | all | summary | changes | render-uap | paths) ;;
    *) printf 'ERROR: unknown check %s (see --help)\n' "$check" >&2; exit 2 ;;
  esac

  # Everything else is about one organization and project.
  if [ -z "$ORG_ID" ] || [ -z "$MGMT_PROJECT_ID" ]; then
    printf 'ERROR: --org and --project are needed on every call (except list)\n' >&2
    exit 2
  fi
  resolve_paths "$ORG_ID" "$MGMT_PROJECT_ID" || exit 2
  load_state
  ACCOUNT="${ACCOUNT#user:}"
  if [ -z "$USERS_GROUP" ] && [ -n "$DOMAIN" ]; then USERS_GROUP="autocloud-users@$DOMAIN"; fi
  save_state

  if [ "$check" = "paths" ]; then
    printf 'state: %s\nlog:   %s\n' "$STATE_FILE" "$LOG_FILE"
    exit 0
  fi
  if [ "$check" = "changes" ]; then
    need "$SINCE" --since
    print_changes
    exit 0
  fi
  if [ "$check" = "summary" ] && [ -n "$FROM" ]; then
    # Test hook: summarize saved check lines without live calls.
    summarize "$FROM"
    exit 0
  fi
  need "$ACCOUNT" --account
  # The project number always comes from gcloud, never from the state file.
  LIVE_NUMBER="$(g projects describe "$MGMT_PROJECT_ID" --format='value(projectNumber)')"
  if [ "$check" != "render-uap" ] && [ "$check" != "summary" ]; then
    printf 'Live checks as %s on organization %s, project %s (%s)\n' \
      "$ACCOUNT" "$ORG_ID" "$MGMT_PROJECT_ID" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  fi

  case "$check" in
    preflight) check_preflight ;;
    roles) check_roles ;;
    apis) check_apis ;;
    group) check_group ;;
    user-iam) check_user_iam ;;
    agent-iam) check_agent_iam ;;
    orgpolicy) check_orgpolicy ;;
    deps) check_deps ;;
    modelarmor) check_modelarmor ;;
    uap) check_uap ;;
    apphub) check_apphub ;;
    console) check_console ;;
    all) run_all_checks ;;
    summary)
      local out
      out="$(mktemp)"
      run_all_checks >"$out"
      summarize "$out"
      rm -f "$out"
      exit 0
      ;;
    render-uap)
      need "$OUT" --out
      render_uap >"$OUT" || exit 1
      printf 'wrote %s (%s rules)\n' "$OUT" "$(grep -c '"effect"' "$OUT")"
      exit 0
      ;;
    -h | --help) usage; exit 0 ;;
    *) printf 'ERROR: unknown check %s (see --help)\n' "$check" >&2; exit 2 ;;
  esac
  if [ "$STRICT" -eq 1 ]; then exit "$FAILED"; fi
  exit 0
}

main "$@"
