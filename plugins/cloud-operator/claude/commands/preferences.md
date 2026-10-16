---
description: Capture or update your GCP operating preferences, sent to the cloud operator as bootstrap context
argument-hint: "[preference to add, e.g. 'always use us-central1']"
---

Maintain the user's GCP operating preferences in `~/.config/cloud-operator/preferences.md`. This file will be read before the first `ask_cloud_operator` call in a new session and passed as context, so it should be concise, factual, and written as directives.

## If `$ARGUMENTS` is non-empty

Treat it as a single preference to remember (like `/remember`). Read the existing file, add or update the matching entry under the right heading (replace contradicting entries rather than appending duplicates), write it back, and confirm in one line. Then sync it to the operator (below).

## Otherwise — bootstrap interview

1. Read the existing file if present and show a short summary; ask whether to update or start fresh.
2. Look for context the user already has, and propose it rather than asking from scratch:
   - `gcloud config list --format=json` (account, default project, region/zone)
   - IaC files in the current directory (e.g. `*.tf`, provider/backend blocks) for tool, provider version, state backend, naming patterns
   - Any GCP-related lines in the user's CLAUDE.md files or memory
3. Ask about the remaining topics in two or three short batches (not one question at a time). Accept "skip" for anything:
   - **Scope:** organization / folder, default project (used as `project` for `ask_cloud_operator`), other allowed projects, environments (dev/staging/prod) and how to tell them apart, operator agent ID only if they want to pin one instead of their personal default agent. Agent IDs are per user and per project: find yours in the `contextId` of your sessions (`search_operator_sessions`, or any operator response): `projects/<p>/locations/global/agents/<AGENT_ID>/sessions/…`. Save it as `locations/global/agents/<AGENT_ID>` together with its project: sessions name the project by number, so the full name fails when `project` is the project ID
   - **Location:** default region/zone, data residency constraints
   - **Conventions:** resource naming, required labels/tags, networking (shared VPC, subnets, private IPs only)
   - **Tooling:** Terraform vs gcloud vs console, module sources, state backend, CI/CD
   - **Change policy:** what needs explicit approval (e.g. anything in prod, IAM changes, deletes), dry-run/plan first, change windows
   - **Security & compliance:** least-privilege IAM, CMEK, VPC-SC, org policies, no public IPs/buckets
   - **Cost:** budgets, preferred machine types, committed-use or spot preferences
   - **Communication:** level of detail, whether to show commands/plans before acting
4. Write the file in this shape (omit empty sections):

```markdown
# GCP operating preferences
_Last updated: <YYYY-MM-DD>_

## Scope
- ...
## Location
- ...
## Conventions
- ...
## Tooling
- ...
## Change policy
- ...
## Security & compliance
- ...
## Cost
- ...
## Communication
- ...
```

5. Create `~/.config/cloud-operator/` if needed. Show the final file and tell the user they can add a preference any time with `/cloud-operator:preferences <preference>`.

## Sync to the operator

The cloud operator agent has its own memory. After writing the file (either mode), send the new or changed preferences to it with `ask_cloud_operator` (project from the file's default project, `agentId` if the file names one, no `contextId`): `Remember these preferences for future sessions: <the new/changed entries>`. Relay its confirmation in one line. If the call fails, say so; the local file is still saved and is sent on the first call of each conversation. When a preference is removed or changed, also ask the operator to delete the old entry, and tell the user its memory may keep it (verify with a fresh-session search if it matters).
