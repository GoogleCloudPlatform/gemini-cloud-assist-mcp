---
name: preferences
description: Save or update the user's standing GCP preferences (environments, regions, conventions, IaC tooling, compliance, change policy, cost guardrails) in the Cloud Operator preferences file and the Cloud Operator Agent's memory. Use only when the user runs /cloud-operator:preferences or explicitly asks to save preferences, not for GCP tasks that merely mention these topics.
---

# Remember GCP operating preferences

Preferences live in a Markdown file outside the plugin,
`~/.config/cloud-operator/preferences.md`, which the other Cloud Operator client plugins
share. After saving it, send the changes to the Operator Agent's memory
(below). Keep it short, declarative and free of secrets.

Read the existing file first (create it and its folder if missing) and merge
into it: replace bullets the new answers contradict, don't add duplicates, and
keep every section the user doesn't change, including ones not listed below.

## `/cloud-operator:preferences <preference>`

Rewrite it as one imperative bullet (e.g. "Never touch prod; apply to dev only
after explicit approval.") under the matching section below, replacing any
bullet it contradicts. Show the user the stored bullet.

## `/cloud-operator:preferences` alone: interview

Ask in **one** message, pre-filling from the existing file and anything
GCP-related you already know from GEMINI.md / AGENTS.md, memories or this
conversation. The user may skip any.

1. **Projects & environments** - dev/staging/prod projects or naming pattern
   (the default project comes from gcloud config, not from here).
2. **Regions** - primary and DR regions; forbidden regions.
3. **IaC & tooling** - Terraform / Pulumi / Config Connector / gcloud;
   versions, modules, state backend.
4. **Naming & labels** - naming pattern; required labels.
5. **Security & compliance** - CMEK, VPC-SC, service accounts, public IPs,
   frameworks (PCI, HIPAA, SOC 2).
6. **Change policy** - extra limits on changes (e.g. "never touch prod",
   "no IAM changes without a ticket").
7. **Cost guardrails** - budgets, Spot, committed use.
8. **Output style** - diagrams, verbosity.

Write the answers as `###` sections with these names, in this order, one
imperative bullet per preference, omitting empty sections.

## Sync to the operator

After writing the file (either mode), send the new or changed preferences to
the Operator Agent with `ask_cloud_operator` (project: the default project from
the user's gcloud configuration, as `/cloud-operator:setup` reads it; `agentId`
if the file names one; no `contextId`): `Remember these preferences for future
sessions: <the new/changed entries>`. Relay its confirmation in one line. If
the call fails, say so: the file is still saved, but the Operator Agent won't
have these preferences until a sync succeeds, so offer to retry. When a
preference is removed or changed, also ask the operator to delete the old
entry, and tell the user its memory may keep it.

## Then tell the user

- Where the file is, and that the Operator Agent saved the preferences to its
  memory (or that the sync failed).
- `/cloud-operator:preferences <text>` updates one item; they can also edit or
  delete the file directly.
