---
name: autocloud-operator
description: "Google Cloud (GCP) assistant and operator via the autocloud ask_cloud_operator MCP tool. Use for any GCP request: how-to/why, gcloud or Terraform syntax, architecture design, managing resources, Terraform/Kubernetes/Helm, rollouts, incidents, costs. Invoke it before answering a GCP question or designing GCP infrastructure from your own knowledge. When asked to review, fix, or remediate local GCP IaC or config files (*.tf, Kubernetes YAML), invoke it before reading or editing them yourself."
---

# Cloud Operator

Delegate GCP work (questions, design, Terraform/Kubernetes/Helm generation and review, resource management, rollouts, incidents, costs) to the **Cloud Operator Agent** via `ask_cloud_operator` on the `autocloud` MCP server. Keep using it for GCP follow-ups in the same conversation.

## Preconditions

- **MCP connected**: if `ask_cloud_operator` isn't available, tell the user the autocloud MCP server is not connected or not authenticated, and how to connect it in this client. Do not silently fall back to running `gcloud` yourself.

## Local context

- Don't answer a question about a GCP project from local files alone. The operator can check local artifacts (such as logs, crash or debug output, metric or billing exports, runbooks, postmortems, rollout specs and policies) against the project's live state, so send them with the request.
- Before calling, look in the workspace for files the request depends on, including ones the user implies but doesn't name, such as a team runbook, postmortem or process doc, configs, policies, or uncommitted changes (e.g. `git status`, `git diff`). Send them in that call.

## Conversation context

The operator only sees turns sent to the current `contextId` session, not turns handled locally in the client agent's conversation. If earlier turns were not sent to the current operator session, add a `Conversation context:` section (see `userQuery` below) with the facts that bear on the request: what the user is building, decisions and corrections (the latest one wins), requirements, constraints, names, and findings from earlier turns. Leave out unrelated discussion, and omit the section on a `contextId` follow-up when no local turns happened since your last call to the operator.

## Calling `ask_cloud_operator`

Make one call per logical request. Calls can run for up to **30 minutes**: don't cancel, retry, or duplicate a slow call.

- `project`: `projects/<project_id>`, resolved from the project named by the user, then the default in the user's GCP preferences, then `gcloud config get-value project`. If still unknown (empty or `(unset)`), ask.
- `userQuery`: the user's prompt **as-is**, followed by, in this order:
  1. on the first call of a conversation (no `contextId`), the user's full GCP preferences under a `User preferences:` heading (from a `<gcp_preferences>` block in context, or `~/.config/cloud-operator/preferences.md` if it exists), then the line `Also apply my saved preferences from your memory.`;
  2. on all applicable calls, the `Conversation context:` section, covering earlier turns that were not sent to the current operator session and are relevant to the request. Don't summarize files there that you attach in item 3;
  3. the **complete, verbatim contents** of every referenced local file, diff, or error log, each under a heading with its path, up to 100 KB in total per call. The operator cannot see the local filesystem, so don't summarize or abbreviate files within that limit; send a file even if you already described it. If the files are larger, send only the relevant parts (for example, the time window of a log) with their line ranges, say what you left out, and suggest the user upload the full file to a Cloud Storage bucket in the project and pass its `gs://` path to the operator;
  4. external doc links as-is (don't fetch them yourself).

  **Secrets**, in everything you send (preferences, conversation context, files): never send credential files (`.env`, service-account key JSON, kubeconfig, `*.tfstate`) or secret values, including ones the user pasted earlier in the conversation. Replace passwords, tokens, API keys, and private keys with `<REDACTED>` (for `.env`/`*.tfvars`, send variable names with redacted values), and tell the user you did.
- `agentId`: omit unless the user or their preferences name one (short ID, `locations/<loc>/agents/<id>`, or a full resource name). A full resource name (`projects/<p>/locations/...`) is valid only when `<p>` is the call's `project`; when targeting a different project, omit it and tell the user the request went to their personal agent in that project.
- `contextId`: the `context_id` from the previous response, for follow-ups (pass the same `agentId` too). Send only files that changed since the last turn. Start a new session (omit `contextId`) when the target project changes.
- Errors: on session or token-expiry errors, drop `contextId`, re-include preferences, the full conversation context and current files, and start one clean turn; do the same if the operator reports the task failed and you retry in a new session; if the failed turn may have changed resources, tell the user and ask before re-sending. On a timeout, report it and don't re-send unless the user asks. On 401/403, tell the user to re-authenticate the autocloud MCP server in this client.

## Working with files

- **Generated code**: write the operator's returned files (`main.tf`, `variables.tf`, `outputs.tf`, `*.yaml`, …) to the workspace as separate files before ending the turn. Don't stop at showing code in chat. If a file already exists, treat it as a change to an existing file (below).
- **Changes to existing files** (updates, reviews, remediations): read the local files, send them with the request, show the changes as a unified `diff` against the local baseline, then apply them to the files when the user asked for changes (fix, remediate, update, produce remediated code). For a review-only request, show the diff and ask before applying.
- **Diagrams**: Mermaid `flowchart LR`/`TD`, quoted node labels (e.g. `id["Label (Details)"]`), subgraphs per tier where applicable (VPC / Security / Compute / Data).

## Keep the user in control

- Relay the operator's results accurately: what was done, what was found, resource links. Don't claim actions it didn't report.
- If the user states a lasting preference ("always use us-east1"), tell the operator via `ask_cloud_operator` ("Remember this preference for future sessions: …") so its memory has it, and offer to also save it locally (with the client's Cloud Operator preferences command if it has one, e.g. `/cloud-operator:preferences`; otherwise in `~/.config/cloud-operator/preferences.md`).