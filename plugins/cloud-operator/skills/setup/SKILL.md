---
name: setup
description: >-
  Sets up Cloud Operator: picks the operator project, creates or checks the
  user's operator agent, saves the project, and offers to share the user's
  existing Google Cloud operating context with the operator's memory. Use when
  the user runs /cloud-operator:setup, asks to set up Cloud Operator or create
  their operator agent, or chooses setup when the cloud-operator skill asks.
  Not for ordinary GCP requests or installing gcloud.
---

# Set up Cloud Operator

Walk the user through setting up Cloud Operator one step at a time. Follow the
`cloud-operator` skill's connection, `agentId`, usage attribution, and
troubleshooting rules.

1. **Choose the project:** ask which Google Cloud project their operator agent
   is in, or will be in (unless already named). Suggest their default `gcloud`
   project or the project in local memory only as an option; don't use either
   without asking.
2. **Check or create the agent:**
   - Unless the user said they have no agent in `{project_id}`, check first:
     call `ask_cloud_operator` with `projects/{project_id}` and "In one line,
     what can you help me with in this project? Don't create anything." Tell
     the user first that it can take 1–3 minutes.
   - If it fails with "personal operator agent … has not been initialized yet"
     (or they said they have none), walk them through creating it one step at a
     time and wait for confirmation: open
     `https://console.cloud.google.com/autocloud/home?project={project_id}`,
     click **Create operator agent**, then click **Get started** when it says
     the agent is ready. Once they confirm, run the check call above (waiting
     about a minute and retrying up to 3 times if the new agent isn't ready
     yet).
3. **Save and offer to share context:** once the check call works, save
   `{project_id}` in local memory (and `agentId` if not their own) and tell the
   user Cloud Operator works, with `{project_id}` and the agent. In that same
   reply, unless local memory has a "Cloud Operator context: shared on" or
   "declined on" note, ask in one line whether to scan agent instruction files,
   local memory, skills and workflows, and the repository's GCP docs for
   context they or their team already have about operating in Google Cloud
   (environments, projects, product preferences, best practices, architecture
   guidance, runbooks) and share it with the operator's memory — noting they'll
   see the list first. Read nothing else until they agree.
   - **Yes:** run the `share-context` skill (from its collection step).
   - **No:** note "Cloud Operator context: declined on {date}" in local memory.
   - **No answer:** note nothing.
   Then return to any request that was waiting when setup started.
