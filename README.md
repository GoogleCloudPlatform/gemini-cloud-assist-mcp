# Gemini Cloud Assist MCP server

> [!IMPORTANT]
> **Private Preview Notice**
> The Gemini Cloud Assist MCP server APIs are currently in Private Preview and are behind an allowlist. Please contact your Google Cloud account team to request access.

[![](https://img.shields.io/github/license/GoogleCloudPlatform/gemini-cloud-assist-mcp)](./LICENSE)

This repository connects AI coding agents and other [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) clients to Cloud Operator, part of the [**Gemini Cloud Assist APIs**](https://cloud.google.com/gemini/docs/api-and-reference), through the remote Gemini Cloud Assist MCP server. It allows you to use natural language to understand, manage, and troubleshoot your Google Cloud environment from your agent.

The configurations in this repository connect to the Cloud Operator endpoint, `https://geminicloudassist.googleapis.com/mcp/autocloud`, which serves the Cloud Operator tools (`ask_cloud_operator`, `search_operator_sessions`, `fetch_operator_session`). The other Gemini Cloud Assist tools listed in the [reference documentation](https://docs.cloud.google.com/gemini/docs/geminicloudassist/reference/mcp) stay on `https://geminicloudassist.googleapis.com/mcp` and are not reachable through these configurations.

> [!NOTE]
> The **Google Cloud Platform Terms of Service** (available at https://cloud.google.com/terms/) and the **Data Processing and Security Terms** (available at https://cloud.google.com/terms/data-processing-terms) do not apply to any component of the Gemini Cloud Assist MCP Server software.

To learn more about Gemini Cloud Assist, see the [Gemini Cloud Assist overview](https://cloud.google.com/gemini/docs/cloud-assist/) in the Google Cloud documentation.

## ✨ Key features

Cloud Operator is an operator agent with live project context. Through `ask_cloud_operator` it handles:

- **Troubleshoot issues:** Incident and root-cause investigation in your Google Cloud environment.
- **Review rollouts:** Rollout readiness and monitoring review.
- **Design and review infrastructure:** Terraform best-practices review and generation, Kubernetes and Helm manifests, with results applied as reviewable file edits.
- **Optimize costs:** Analyze your spend and identify opportunities for efficiency.
- **Get general assistance:** Documentation-grounded how-to answers and guidance on Google Cloud best practices, architectures, and operations.

## Quick start

Before you begin, ensure you have the following set up:

- [**Google Cloud SDK**](https://cloud.google.com/sdk/docs/install) installed and configured.
- A **Google Cloud project** on the Private Preview allowlist.
- The following **IAM roles** on your user account:
  - `roles/serviceusage.serviceUsageAdmin`: Required to enable the Cloud Assist APIs.
  - `roles/geminicloudassist.user`: Required to make requests to the Cloud Assist APIs.

### Step 1: Authenticate to Google Cloud

The Cloud Operator plugin and the Antigravity configuration below sign in with your local Application Default Credentials (ADC). To set up ADC, run the following `gcloud` commands:

```shell
# Authenticate your user account to the gcloud CLI
gcloud auth login

# Set up Application Default Credentials for the same account
gcloud auth application-default login

# Set the project that those credentials' calls are billed to, usually the one where your operator agent is
gcloud auth application-default set-quota-project PROJECT_ID
```

Setting the quota project needs `serviceusage.services.use` on that project; project Owners and Editors have it.

### Step 2: Enable the API

Enable the Gemini Cloud Assist API in the project where your operator agent is:

```shell
gcloud services enable geminicloudassist.googleapis.com --project=PROJECT_ID
```

### Step 3: Connect your agent

In Claude Code, Codex, or Antigravity, install the [Cloud Operator plugin](#cloud-operator-plugin-claude-code-chatgpt-codex-and-google-antigravity). For other MCP clients, use one of the configurations below.

## Configure your MCP client

The client-agent configuration depends on which agent you are using.

### Cloud Operator plugin: Claude Code, ChatGPT Codex and Google Antigravity

The Cloud Operator plugin, in [`plugins/cloud-operator`](plugins/cloud-operator/README.md), connects Claude Code, ChatGPT Codex or Google Antigravity to Cloud Operator (`ask_cloud_operator`). It:

- connects the `autocloud` MCP server, signed in with your ADC, with a 20-minute tool timeout (in Codex, you add the server to `~/.codex/config.toml` yourself);
- adds the `cloud-operator` skill, which helps your agent decide when and how to use Cloud Operator, and asks which project to use the first time.

To install it, see [`plugins/cloud-operator`](plugins/cloud-operator/README.md#step-3-install-the-plugin). If you installed Cloud Operator with one of the earlier per-client installers, [remove that copy first](plugins/cloud-operator/README.md#step-2-remove-an-earlier-install). In these agents, the plugin replaces the `gemini-cloud-assist-mcp` plugin at the root of this repository, so don't install both.

### Antigravity

To add only the server, without the plugin's skill, add the following to your `mcp_config.json`:

```json
"mcpServers": {
  "autocloud": {
    "serverUrl": "https://geminicloudassist.googleapis.com/mcp/autocloud",
    "authProviderType": "google_credentials",
    "timeoutSeconds": 1200
  }
}
```

### Cursor

1. In your Google Cloud project, create an OAuth 2.0 client ID for a desktop app.
2. Configure `URI://anysphere.cursor-mcp/oauth/callback` as the redirect URL.
3. Add or merge the following configuration block:

```json
{
  "mcpServers": {
    "autocloud": {
      "url": "https://geminicloudassist.googleapis.com/mcp/autocloud",
      "auth": {
        "CLIENT_ID": "${env:OAUTH_CLIENT_ID}",
        "CLIENT_SECRET": "${env:OAUTH_CLIENT_SECRET}",
        "scopes": ["https://www.googleapis.com/auth/cloud-platform"]
      }
    }
  }
}
```

### Claude

Follow the configuration instructions for your specific application:

- [Claude.ai](https://docs.cloud.google.com/mcp/configure-mcp-ai-application#claude-ai)
- Claude Code: see [Cloud Operator plugin](#cloud-operator-plugin-claude-code-chatgpt-codex-and-google-antigravity).

## MCP Tools

### Cloud Operator MCP tools

Cloud Operator is an agent accessible through a set of MCP tools. The agent invoked by MCP tool calls makes its own tool calls internally to Google Cloud. The `/mcp/autocloud` endpoint serves the following tools. They are in **Private Preview** and restricted to allowlisted projects.

| Tool | Description |
| :--- | :--- |
| **`ask_cloud_operator`** | Delegates multi-step operational work to the Cloud Operator agent: incident and root-cause investigation, rollout review, cost optimization, Terraform best-practices review and generation, and documentation-grounded how-to answers. Returns a `contextId` that continues the session on follow-up calls. |
| **`search_operator_sessions`** | Lists your Cloud Operator sessions in a project. Each session's `contextId` names the operator agent that served it. |
| **`fetch_operator_session`** | Fetches a Cloud Operator session by its `contextId`, including its turns. |

The other Gemini Cloud Assist tools (`ask_cloud_assist`, `design_infra`, `investigate_issue`, `invoke_operation`, `optimize_costs`) are served by `https://geminicloudassist.googleapis.com/mcp` and are documented in the [Gemini Cloud Assist MCP reference](https://docs.cloud.google.com/gemini/docs/geminicloudassist/reference/mcp). They are not available through the configurations in this repository.

> **Note:** These tools should not be treated as stable APIs. Parameters might be renamed or modified to account for the evolving capabilities of Gemini Cloud Assist.

## Agent Skills

The Cloud Operator plugin uses a `SKILL.md` file to instruct your agent on how to properly use the tools. The skill guides your agent on when to delegate to Cloud Operator, passing relevant local information to it, and working with the files it returns.

| Skill | Description |
| :--- | :--- |
| **[`cloud-operator`](plugins/cloud-operator/skills/cloud-operator/SKILL.md)** | Delegates Google Cloud work to the Cloud Operator agent (`ask_cloud_operator`): how-to questions, architecture design, Terraform, Kubernetes and Helm generation and review, resource management, rollouts, incidents, and costs, with generated and changed files written as reviewable edits. Requires Private Preview access. |

## Deprecated local Node.js server

The Gemini Cloud Assist MCP server has migrated from a local Node.js architecture (the [`@google-cloud/gemini-cloud-assist-mcp`](https://www.npmjs.com/package/@google-cloud/gemini-cloud-assist-mcp) npm package) to a Remote MCP Server architecture. The older local Node.js server will lose support in the coming months.

To use the new Remote MCP Servers, please use version `v0.8.0` or later. If you wish to continue using the legacy local server during the transition, please pin your configuration to older versions.

## **Contributing**

- If you encounter a bug, please file an issue on our [GitHub Issues](https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/issues) page.
- Before sending a pull request, please review our [Contributing Guide](./docs/CONTRIBUTING.md).

## **License**

This project is licensed under the Apache 2.0 License and provided as-is, without warranty or representation for any use or purpose. For details, see the [LICENSE](./LICENSE) file.
