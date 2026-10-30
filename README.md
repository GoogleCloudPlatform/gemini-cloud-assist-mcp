[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/googlecloudplatform-gemini-cloud-assist-mcp-badge.png)](https://mseep.ai/app/googlecloudplatform-gemini-cloud-assist-mcp)

# Gemini Cloud Assist MCP server

> [!IMPORTANT]
> **Private Preview Notice**
> The Gemini Cloud Assist MCP server APIs are currently in Private Preview and are behind an allowlist. Please contact your Google Cloud account team to request access.

> [!WARNING]
> **Deprecation Notice & Migration to Remote MCP Server**
>
> The Gemini Cloud Assist MCP server has migrated from a local Node.js architecture to a Remote MCP Server architecture. The older local Node.js server will lose support in the coming months.
>
> To use the new Remote MCP Servers, please use version `v0.8.0` or later. If you wish to continue using the legacy local server during the transition, please pin your configuration to older versions.

[![npm @google-cloud/gemini-cloud-assist-mcp package](https://img.shields.io/npm/v/@google-cloud/gemini-cloud-assist-mcp.svg)](https://www.npmjs.com/package/@google-cloud/gemini-cloud-assist-mcp)
[![](https://img.shields.io/github/license/GoogleCloudPlatform/gemini-cloud-assist-mcp)](./LICENSE)

This server connects [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) clients to the [**Gemini Cloud Assist APIs**](https://cloud.google.com/gemini/docs/api-and-reference). It allows you to use natural language to understand, manage, and troubleshoot your Google Cloud environment directly from the local command line.

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
- A **Google Cloud project**.
- The following **IAM roles** on your user account:
  - `roles/serviceusage.serviceUsageAdmin`: Required to enable the Cloud Assist APIs.
  - `roles/geminicloudassist.user`: Required to make requests to the Cloud Assist APIs.

### Step 1: Authenticate to Google Cloud

The Gemini Cloud Assist MCP server uses local Application Default Credentials (ADC) to securely authenticate to Google Cloud. To set up ADC, run the following `gcloud` commands:

```shell
# Authenticate your user account to the gcloud CLI
gcloud auth login

# Set up Application Default Credentials for the server.
gcloud auth application-default login
```

## Configure your MCP client

The client-agent configuration depends on which agent you are using.

### Cloud Operator plugin: Claude Code, ChatGPT Codex and Google Antigravity

> [!IMPORTANT]
> **Private Preview.** Cloud Operator and its MCP server are in Private Preview.

The Cloud Operator plugin (in `plugins/cloud-operator`; it installs as
`cloud-operator`, so its commands are `/cloud-operator:…`) connects Claude Code, ChatGPT
Codex or Google Antigravity to Cloud Operator (`ask_cloud_operator`). It:

- sets up the MCP connection to Cloud Operator, with a 30-minute tool timeout;
- asks which operator agent to use and checks it answers;
- saves your Google Cloud preferences and passes them to Cloud Operator;
- adds a skill that helps your agent decide when and how to use Cloud Operator.

To install it, see [`plugins/cloud-operator`](plugins/cloud-operator/README.md).
In these agents, the plugin replaces the `gemini-cloud-assist-mcp` plugin at the
root of this repository, so don't install both.

### Antigravity

Add the following to your `mcp_config.json`:

```json
"mcpServers": {
  "gemini_cloud_assist": {
    "serverUrl": "https://geminicloudassist.googleapis.com/mcp/autocloud",
    "headers": {},
    "authProviderType": "google_credentials"
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
    "gemini_cloud_assist": {
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

The Gemini Cloud Assist MCP tools leverage `SKILL.md` files to instruct your agent on how to properly use the tools. The skills help to guide your agent on when to delegate to Cloud Operator, passing relevant local information to it, and enabling explicit invocation.

| Skill | Description |
| :--- | :--- |
| **`autocloud-operator`** | Delegates Google Cloud operations to the Cloud Operator agent (`ask_cloud_operator`): incident investigation, rollout review, cost optimization, Terraform review and generation, and how-to questions, with Terraform results applied as reviewable file edits. Requires Private Preview access. |

## **Contributing**

- If you encounter a bug, please file an issue on our [GitHub Issues](https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/issues) page.
- Before sending a pull request, please review our [Contributing Guide](./docs/CONTRIBUTING.md).

## **License**

This project is licensed under the Apache 2.0 License and provided as-is, without warranty or representation for any use or purpose. For details, see the [LICENSE](./LICENSE) file.
