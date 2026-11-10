# Gemini Cloud Assist MCP server

> [!IMPORTANT]
> **Private Preview Notice**
> The Gemini Cloud Assist MCP server APIs are currently in Private Preview and are behind an allowlist. Please contact your Google Cloud account team to request access.

[![](https://img.shields.io/github/license/GoogleCloudPlatform/gemini-cloud-assist-mcp)](./LICENSE)

This repository connects AI coding agents to **Cloud Operator**, the operator agent of [Gemini Cloud Assist](https://cloud.google.com/gemini/docs/cloud-assist/). Cloud Operator sees your live Google Cloud resources, logs, metrics, billing and policies, and helps you:

- **Troubleshoot** incidents and find root causes.
- **Review rollouts** for readiness and monitor them.
- **Design and review infrastructure:** Terraform, Kubernetes and Helm, with changes written as reviewable file edits.
- **Optimize costs.**
- **Answer how-to questions**, grounded in the Google Cloud documentation.

> [!NOTE]
> The **Google Cloud Platform Terms of Service** (available at https://cloud.google.com/terms/) and the **Data Processing and Security Terms** (available at https://cloud.google.com/terms/data-processing-terms) do not apply to any component of the Gemini Cloud Assist MCP Server software.

## How it works

The [`cloud-operator` plugin](plugins/cloud-operator/README.md) adds Cloud Operator to your agent. It installs:

- the **`cloud-operator` skill**, which tells your agent when to hand Google Cloud work to Cloud Operator and how to send it the context it needs;
- the **`autocloud` MCP server** (`https://geminicloudassist.googleapis.com/mcp/autocloud`), signed in with your Google credentials (Application Default Credentials).

## Install

Follow the [installation guide](plugins/cloud-operator/README.md#get-started): it takes you through the prerequisites, removing an earlier install, installing the plugin in your agent, and your first call.

The plugin works in:

- Claude Code
- Codex
- Antigravity
- Gemini CLI
- OpenCode
- Pi

## MCP tools

The `/mcp/autocloud` endpoint serves these Cloud Operator tools:

| Tool | Description |
| :--- | :--- |
| **`ask_cloud_operator`** | Hands Google Cloud work to the Cloud Operator agent: incident and root-cause investigation, rollout review, cost optimization, Terraform review and generation, and how-to answers. Returns a `contextId` that continues the session on follow-up calls. |
| **`search_operator_sessions`** | Lists your Cloud Operator sessions in a project. |
| **`fetch_operator_session`** | Fetches a Cloud Operator session by its `contextId`, including its turns. |

> **Note:** These tools should not be treated as stable APIs. Parameters might be renamed or modified as Gemini Cloud Assist evolves.

## Contributing

- If you encounter a bug, please file an issue on our [GitHub Issues](https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/issues) page.
- Before sending a pull request, please review our [Contributing Guide](./docs/CONTRIBUTING.md).

## License

This project is licensed under the Apache 2.0 License and provided as-is, without warranty or representation for any use or purpose. For details, see the [LICENSE](./LICENSE) file.
