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

This server connects [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) clients such as the [Gemini CLI](https://github.com/google-gemini/gemini-cli) to the [**Gemini Cloud Assist APIs**](https://cloud.google.com/gemini/docs/api-and-reference). It allows you to use natural language to understand, manage, and troubleshoot your Google Cloud environment directly from the local command line.

> [!NOTE]
> The **Google Cloud Platform Terms of Service** (available at https://cloud.google.com/terms/) and the **Data Processing and Security Terms** (available at https://cloud.google.com/terms/data-processing-terms) do not apply to any component of the Gemini Cloud Assist MCP Server software.

To learn more about Gemini Cloud Assist, see the [Gemini Cloud Assist overview](https://cloud.google.com/gemini/docs/cloud-assist/) in the Google Cloud documentation.

## ✨ Key features

- **Design infrastructure:** Create and architect infrastructure configurations for Google Cloud.
- **Troubleshoot issues:** Run deep investigations to find the root cause of complex issues in your Google Cloud environment.
- **Manage resources:** Create, update, and delete Google Cloud resources directly from your chat workflow (requires Agent Actions).
- **Optimize costs:** Analyze your spend, track costs, and identify opportunities for efficiency such as idle resources.
- **Get general assistance:** Ask questions and get guidance on Google Cloud best practices, architectures, and operations.

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

### Gemini CLI

Install the MCP server as a [Gemini CLI extension](https://github.com/google-gemini/gemini-cli/blob/main/docs/extension.md):

```shell
gemini extensions install https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp
```

Alternatively, you can manually add the configuration to your **_~/.gemini/settings.json_**:

```json
"mcpServers": {
  "gemini_cloud_assist": {
    "httpUrl": "https://geminicloudassist.googleapis.com/mcp",
    "authProviderType": "google_credentials",
    "oauth": {
      "scopes": ["https://www.googleapis.com/auth/cloud-platform"]
    },
    "timeout": 600000
  },
  "application_design_center": {
    "httpUrl": "https://designcenter.googleapis.com/mcp",
    "authProviderType": "google_credentials",
    "oauth": {
      "scopes": ["https://www.googleapis.com/auth/cloud-platform"]
    },
    "timeout": 600000
  }
}
```

### Antigravity

Add the following to your `mcp_config.json`:

```json
"mcpServers": {
  "gemini_cloud_assist": {
    "serverUrl": "https://geminicloudassist.googleapis.com/mcp",
    "headers": {},
    "authProviderType": "google_credentials"
  },
  "application_design_center": {
    "serverUrl": "https://designcenter.googleapis.com/mcp",
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
      "url": "https://geminicloudassist.googleapis.com/mcp",
      "auth": {
        "CLIENT_ID": "${env:OAUTH_CLIENT_ID}",
        "CLIENT_SECRET": "${env:OAUTH_CLIENT_SECRET}",
        "scopes": ["https://www.googleapis.com/auth/cloud-platform"]
      }
    },
    "application_design_center": {
      "url": "https://designcenter.googleapis.com/mcp",
      "auth": {
        "CLIENT_ID": "${env:OAUTH_CLIENT_ID}",
        "CLIENT_SECRET": "${env:OAUTH_CLIENT_SECRET}",
        "scopes": ["https://www.googleapis.com/auth/cloud-platform"]
      }
    }
  }
}
```



## MCP Tools

Gemini Cloud Assist is an agent accessible through a set of MCP tools. The agent invoked by MCP tool calls makes its own tool calls internally to Google Cloud. The following MCP tools are published for agents to consume:

| Tool | Description |
| :--- | :--- |
| **[`ask_cloud_assist`](https://cloud.google.com/gemini/docs/geminicloudassist/reference/mcp/tools_list/ask_cloud_assist)** | The primary interface for Google Cloud assistance and for the Gemini Cloud Assist agent. All functionality is accessible through this tool. |
| **[`design_infra`](https://cloud.google.com/gemini/docs/geminicloudassist/reference/mcp/tools_list/design_infra)** | Supports workflows for designing and architecting infrastructure on Google Cloud. |
| **[`investigate_issue`](https://cloud.google.com/gemini/docs/geminicloudassist/reference/mcp/tools_list/investigate_issue)** | Supports workflows for troubleshooting in Google Cloud. Can do quick troubleshooting or deeper troubleshooting through an Investigation resource. |
| **[`invoke_operation`](https://cloud.google.com/gemini/docs/geminicloudassist/reference/mcp/tools_list/invoke_operation)** | Supports workflows for creating, updating, and deleting resources in Google Cloud. Only functional when Agent Actions are enabled. |
| **[`optimize_costs`](https://cloud.google.com/gemini/docs/geminicloudassist/reference/mcp/tools_list/optimize_costs)** | Supports workflows for analyzing, tracking, and optimizing Google Cloud costs. Provides breakdowns of spend and identifies opportunities for cost efficiency. |

> **Note:** These tools should not be treated as stable APIs. Parameters might be renamed or modified to account for the evolving capabilities of Gemini Cloud Assist.

## Agent Skills

The Gemini Cloud Assist MCP tools leverage `SKILL.md` files to instruct your agent on how to properly use the tools. The skills help to guide your agent on chaining together multiple tools into a workstream, passing relevant local information to Gemini Cloud Assist, and enabling explicit invocation.

| Skill | Description |
| :--- | :--- |
| **`designing-and-deploying-infrastructure`** | Guides the agent on how to design, assess, deploy, and troubleshoot cloud infrastructure using the Application Design Center (ADC) and Gemini Cloud Assist tools. |
| **`operating-google-cloud`** | Provides instructions for managing Google Cloud Platform (GCP) resources and Kubernetes using specialized MCP tools. |

## **Contributing**

- If you encounter a bug, please file an issue on our [GitHub Issues](https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/issues) page.
- Before sending a pull request, please review our [Contributing Guide](./docs/CONTRIBUTING.md).

## **License**

This project is licensed under the Apache 2.0 License and provided as-is, without warranty or representation for any use or purpose. For details, see the [LICENSE](./LICENSE) file.
