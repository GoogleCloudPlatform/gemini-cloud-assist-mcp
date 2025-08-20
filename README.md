# **Gemini Cloud Assist MCP Server**

[![](https://img.shields.io/github/license/GoogleCloudPlatform/gemini-cloud-assist-mcp)](./LICENSE)
[![](https://img.shields.io/github/discussions/GoogleCloudPlatform/gemini-cloud-assist-mcp?style=social&logo=github)](https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/discussions)
[![](https://img.shields.io/github/stars/GoogleCloudPlatform/gemini-cloud-assist-mcp?style=social)](https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp)

This server connects [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) clients (like the [Gemini CLI](https://github.com/google-gemini/gemini-cli)) to the **Gemini in Cloud Assist API**. It allows you to use natural language to **understand, manage, and troubleshoot** your Google Cloud environment directly from your local command line.

This initial release features a powerful suite of **Investigation Tools**. These tools are designed to help you identify the root causes of complex issues, accelerate troubleshooting, and receive actionable recommendations.

### **Key Features**

- **🤖 Natural Language Commands:** Describe a problem or task in plain English and let Gemini Cloud Assist take care of the rest.
- **🔍 Automated Root Cause Analysis:** Automatically analyze GCP configurations, logs, and metrics to find the source of complex issues.
- **💻 Seamless CLI Integration:** Integrates directly into your command-line workflow via clients like the Gemini CLI.
- **💡 Iterative Troubleshooting:** Add new observations to existing investigations to refine the analysis as you learn more.

---

### **How It Works**

This server acts as a local bridge between your MCP client and Google Cloud. The typical investigation workflow is:

1.  **Create an Investigation:** You start by describing a problem, which creates a new investigation session.
2.  **Add Observations (Optional):** You can provide additional context, logs, or findings to the investigation. Each new piece of information creates a new revision.
3.  **Run the Analysis:** Gemini analyzes the investigation's context and returns a report with findings, root causes, and recommended actions.

> To learn more about the product, see the official **[Gemini in Cloud Assist Investigations Documentation](https://cloud.google.com/gemini/docs/cloud-assist/investigations)**.

---

## **🚀 Getting Started**

Follow these steps to get the server running and connected to your client.

### **1. Prerequisites**

Before you begin, ensure you have the following:

- [**Node.js**](https://nodejs.org/en/download) (v20 or later).
- [**Google Cloud SDK**](https://cloud.google.com/sdk/docs/install) installed and initialized.
- A **Google Cloud Project**.
- An **MCP Client**, such as the [**Gemini CLI**](https://github.com/google-gemini/gemini-cli).
- Your user account must have the following **IAM roles** in your project:
  - `roles/serviceusage.serviceUsageAdmin` (Service Usage Admin)
  - `roles/geminicloudassist.user` (Gemini Cloud Assist User)

### **2. Authenticate with Google Cloud**

You need to authenticate twice: once for your user account and once for the application itself.

```shell
# Authenticate your user account to the gcloud CLI
gcloud auth login

# Set up Application Default Credentials for the server.
# This allows the MCP server to securely make Google Cloud API calls on your behalf.
gcloud auth application-default login
```

### **3. Configure Your MCP Client**

Add the Gemini Cloud Assist MCP Server to your client's configuration. For the Gemini CLI, add the following to your `settings.json` file.

```json
"mcpServers": {
  "gemini-cloud-assist": {
    "command": "npx",
    "args": ["-y", "https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp"]
  }
}
```

That's it\! The next time you run your MCP client in interactive mode (e.g., by running `gemini`), it will automatically start this server.

---

## **Tools Reference**

The server exposes the following tools, with more planned for future releases.

### **Current Tools**

- **`create_investigation`**: Starts a new troubleshooting session for a specific issue.
- **`run_investigation`**: Triggers a root cause analysis on an investigation and returns the final report.
- **`add_observation`**: Adds new context to an investigation, creating a new revision for analysis.
- **`fetch_investigation`**: Retrieves the history, findings, and revisions for a specific investigation.

> **Coming Soon**: Future releases will expand the toolset to include resource finding, cost optimization and more.

---

## **API Access and Quotas**

This server uses the Gemini in Cloud Assist API. While a [Gemini Code Assist subscription](https://cloud.google.com/gemini/docs/codeassist/overview#supported-features) is optional, it is highly recommended for increased request quotas.

| License                | Requests per user per minute | Requests per user per day |
| ---------------------- | ---------------------------- | ------------------------- |
| No license             | 5 (Pro) to 10 (Flash)        | 100 (Pro) to 250 (Flash)  |
| Code Assist Standard   | 120 (both models)            | 1500 (both models)        |
| Code Assist Enterprise | 120 (both models)            | 2000 (both models)        |

---

## **Community & Contributing**

- **🐛 Report Issues:** If you encounter a bug, please file an issue on our [GitHub Issues](https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/issues) page.
- **💬 Ask Questions:** For questions and discussions, please use [GitHub Discussions](https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/discussions).
- **🤝 Contribute:** Before sending a pull request, please review our [Contributing Guide](./docs/CONTRIBUTING.md).

### **License**

This project is licensed under the Apache 2.0 License - see the [LICENSE](./LICENSE) file for details.
