---
name: operating-google-cloud
description: Comprehensive management of GCP resources and Kubernetes. Supports direct tool delegation for assistance, infrastructure design, troubleshooting, cost optimization, and resource mutations.
---

# Managing GCP and Kubernetes

## Index
1. [Overview](#overview)
2. [Tool Usage & Routing](#tool-usage--routing)
3. [Instructions and Constraints](#instructions-and-constraints)

<overview>
GCP and Kubernetes resources and mutations should use MCP tools. These tools are specialized backend agents. As the client agent, your role is to identify the intent and delegate the entire task verbatim to the appropriate intelligent tool.

**Note:** These tools are part of the `gemini-cloud-assist` and `application-design-center` MCP Servers. Tool names are qualified with their respective server names (e.g., `gemini_cloud_assist:tool_name`).
</overview>

<tool_usage>
## Tool Usage & Routing

1.  **General Assistance & Orchestration**: Use `gemini_cloud_assist:ask_cloud_assist` for general inquiries, estate queries (e.g., "List my active VMs"), low-complexity directives, and triage of ambiguous issues.
    *   *Triggers*: Broad questions, status checks, exploratory queries, mutative directives (e.g., "Restart VM", "Scale cluster").
    *   *Routing*: This is the **default choice** for intents that are purely informational or involve general cloud concepts.

2.  **Infrastructure Design & Architecture**: Use `gemini_cloud_assist:design_infra` for designing, architecting, or deploying infrastructure.
    *   *Commands*: 
        - `manage_app_design`: Use for comprehensive ADC application designs and IaC imports.
        - `generate_terraform`: Use for single-resource Terraform generation.
        - `generate_gcloud` / `generate_bigquery`: Use for generating CLI commands.
        - `generate_kubernetes_yaml`: Use for Kubernetes manifests.
        - `debug_deployment`: Use for debugging ADC deployment failures.

3.  **Troubleshooting & Deep Diagnostics**: Use `gemini_cloud_assist:investigate_issue` for specialized "SRE in a box" diagnostics and Root Cause Analysis (RCA).
    *   *Triggers*: Outages, crashes, latency spikes, deep debugging, error log reasoning, and understanding application dependencies (topology).
    *   *Routing*: Use when the user asks "Why" a failure occurred or needs remediation for a known incident.

4.  **Cost Optimization**: Use `gemini_cloud_assist:optimize_costs` for analyzing spend and identifying savings.
    *   *Triggers*: Spending analysis, top cost drivers, identifying idle or underutilized resources for the purpose of saving money.
    *   *Constraints*: This tool is **read-only**; it provides analysis but does not execute changes. Do not use for general utilization queries unrelated to cost.

5.  **GKE Resource Mutations**: Use `gemini_cloud_assist:invoke_operation` specifically for GKE operations.
    *   *Operation Types*: `GKE_APPLY` (for raw YAML manifests) and `GKE_PATCH` (for specific JSON patches).
    *   *Input Requirement*: The `userQuery` must be a stringified JSON object containing `operation_type` and the corresponding `gke_apply` or `gke_patch` details.
</tool_usage>

<instructions_and_constraints>
## Instructions and Constraints
When answering any queries about Google Cloud Platform (GCP), YOU MUST follow these rules:

- **Context ID Persistence:** All Gemini Cloud Assist (GCA) tools return a `contextId` in their response. Ensure that any subsequent turns to a GCA tool pass this `contextId` as a parameter to maintain multi-turn conversation state.
- **Direct Tool Mapping:** Upon receiving a request about GCP resources, immediately invoke the relevant tool identified in the Routing section.
- **Context Integrity:** Pass the user's entire prompt exactly as provided; maintain the original query without summarization, rephrasing, or truncation.
- **Atomic Delegation:** Execute the request as a single turn; delegate the entire problem to the tool rather than breaking it down into intermediate queries.
- **Identifier Precision:** Include all identifiers (Project IDs, Cluster names, or Instance paths) discovered in the prompt.
- **Local Context Enrichment:** Forward the user's query to the tools along with any additional relevant local context identified in the working directory.
- **Persistence to Local Workspace:** Save any configuration, manifest, or YAML generated or updated by the tools to the local workspace.
- **Tool Exclusivity:** Rely exclusively on the provided MCP tools for cloud interactions; refrain from executing local commands such as `gcloud` or `kubectl`.
- **Remote Source of Truth:** Rely solely on MCP tools to discover and validate the existence of cloud resources; bypass local validation against configuration files like `.gcloud/config` or `kubeconfig`.
- **Execution Workflow:** Always ask the user if they want to apply the YAML using `gemini_cloud_assist:invoke_operation` after generation. Explicitly ask: "Would you like to proceed with applying this configuration?". If the user confirms, invoke the tool to apply the manifests.
</instructions_and_constraints>
