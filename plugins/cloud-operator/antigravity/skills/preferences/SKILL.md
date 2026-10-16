---
name: preferences
description: Save or update the user's standing GCP preferences (environments, regions, conventions, IaC tooling, compliance, change policy, cost guardrails) in the Cloud Operator preferences file, which is sent to the Cloud Operator Agent at the start of every session. Use only when the user runs /cloud-operator:preferences or explicitly asks to save preferences, not for GCP tasks that merely mention these topics.
---

# Remember GCP operating preferences

Preferences live in a Markdown file outside the plugin,
`~/.config/cloud-operator/preferences.md`, which the other Cloud Operator client plugins
share. The operator skill reads it and sends it with the first
`ask_cloud_operator` call of every Operator session. Keep it short,
declarative and free of secrets.

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

## Then tell the user

- Where the file is, and that the preferences go to the Operator Agent at the
  start of every new Operator session from now on.
- `/cloud-operator:preferences <text>` updates one item; they can also edit or
  delete the file directly.
