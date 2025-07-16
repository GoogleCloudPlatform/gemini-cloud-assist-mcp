# Gemini Cloud Assist MCP Server

MCP Server for GCP environment understanding & troubleshooting using the Gemini Cloud Assist API.

This server provides a set of tools to interact with the Gemini Cloud Assist API, allowing AI agents to create, manage, and run troubleshooting investigations.

## Detailed Guide

1.  [Set up your Google Cloud project](#set-up-your-cloud-project). This currently takes \~20 minutes for a new user who’s using a Gemini Code Assist subscription to increase their [quota limits](#increase-gemini-cli-quota-limits).
2.  [Install and set up the Gemini CLI](#install-and-set-up-the-gemini-cli). This currently takes \~5 minutes.
3.  [Install and set up the Cloud Assist MCP server](#install-and-set-up-the-cloud-assist-mcp-server). This currently takes \~15 minutes for a new user—10 minutes to set up `gcloud` and 5 minutes to set up the server.

## Set up your Cloud project {#set-up-your-cloud-project}

1.  Select or create a Cloud project.
2.  (Optional) In your Cloud project, purchase a Gemini Code Assist subscription. When Cloud Assist starts hard license enforcement, this step will be required in order to create and update investigations via the MCP server. A Code Assist subscription also gives you [higher Gemini CLI quota limits](#increase-gemini-cli-quota-limits).
    1.  In the Cloud console, go to the [**Admin for Gemini**](https://console.cloud.google.com/gemini-admin) page.
    2.  Select **Get Gemini Code Assist**.
    3.  In **Select Gemini Code Assist subscription edition**, select a Gemini Code Assist edition > **Continue**.
    4.  In **Configure subscription**, complete the fields to configure the subscription and select the number of licenses that you want to purchase.
    5.  Select **Continue** > **I agree to the terms of this purchase** > **Confirm subscription**.
    6.  Select **Manage Gemini license assignments** > **Assign licenses**. You must have permissions to manage billing accounts, procurement orders, or license pools.
    7.  Click **Assign licenses** > Select one or more users from the list > click **Next**.
    8.  Select the Gemini Code Assist edition that you subscribed to > click **Assign licenses**.
3.  (Optional) Opt in to data sharing. Your prompts and Gemini's responses are not used to improve Google's models unless you opt in. For more information, see [Configure prompt and response data sharing](https://cloud.google.com/gemini/docs/configure-prompt-response-sharing).

### Increase Gemini CLI quota limits {#increase-gemini-cli-quota-limits}

The following table details the Gemini CLI quota limits. Only requests that the Gemini CLI itself makes count against these quotas. For example, if the Gemini CLI makes a 1 request to a Cloud Assist MCP tool and the Cloud Assist tool makes 5 internal requests before providing the tool response, only 1 request counts against your quota.

| License                  | Requests per user per minute | Requests per user per day  |
| :----------------------- | :--------------------------- | :------------------------- |
| No license               | 5 (Pro) to 10 (Flash)        | 100 (Pro) to 250 (Flash)   |
| Code Assist Standard     | 120 (both models)            | 1500 (both models)         |
| Code Assist Enterprise   | 120 (both models)            | 2000 (both models)         |

## Install and set up the Gemini CLI {#install-and-set-up-the-gemini-cli}

1.  Install [Node.js version 20](https://nodejs.org/en/download) (LTS version recommended).
2.  Install the Gemini CLI.
    1.  Option 1: [Install the Gemini CLI with npx](#install-the-gemini-cli-with-npx).
    2.  Option 2: [Install the Gemini CLI with npm](#install-the-gemini-cli-with-npm).
3.  Authenticate to the Gemini CLI.
    1.  Option 1: [Authenticate with your Cloud project](#authenticate-with-your-cloud-project) to use your free tier, pay-per-request [pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing), or your Gemini Code Assist quota.
    2.  Option 2: [Authenticate with the Gemini API](#authenticate-with-the-gemini-api) to use your free tier quota or pay-per-request [pricing](https://ai.google.dev/gemini-api/docs/pricing).

### Install the Gemini CLI with npx {#install-the-gemini-cli-with-npx}

```shell
npx https://github.com/google-gemini/gemini-cli
```

### Install the Gemini CLI with npm

```shell
npm install -g @google/gemini-cli
```

### Authenticate with your Cloud project {#authenticate-with-your-cloud-project}

```shell
echo 'export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"' >> ~/.bashrc
source ~/.bashrc # or ~/.zshrc, or ~/.profile
```

### Authenticate with the Gemini API {#authenticate-with-the-gemini-api}

```shell
echo 'export GEMINI_API_KEY="YOUR_API_KEY"' >> ~/.bashrc
source ~/.bashrc # or ~/.zshrc, or ~/.profile
```

## Install and set up the Cloud Assist MCP server {#install-and-set-up-the-cloud-assist-mcp-server}

1.  Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install).
2.  [Authenticate to your Google Account](#authenticate-to-your-google-account).
3.  Set up application credentials, which the Cloud Assist MCP server will use by default
4.  Configure the Cloud Assist MCP server.
    1.  Option 1: [Set the server in the extension configuration](#set-the-server-in-the-extension-configuration).
    2.  Option 2: [Set the server in the MCP configuration](#set-the-server-in-the-mcp-configuration).

### Authenticate to your Google Account {#authenticate-to-your-google-account}

```shell
gcloud auth login
```

### Set up application credentials

```shell
gcloud auth application-default login
```

### Set the server in the extension configuration {#set-the-server-in-the-extension-configuration}

```json
{
  "name": "gemini-cloud-assist",
  "version": "1.0.0",
  "mcpServers": {
    "gemini-cloud-assist": {
      "command": "npx -y https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp"
    }
  }
}
```

### Set the server in the MCP configuration {#set-the-server-in-the-mcp-configuration}

```json
   "gemini-cloud-assist": {
     "command": "npx",
     "args": ["-y", "https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp"]
   }
```

## Cloud Assist MCP tools

The following tools are available:

-   `fetch_investigation`: Fetches existing Gemini Cloud Assist troubleshooting investigations. This can be used to list all investigations for a project or get the details of a specific one.
-   `create_investigation`: Creates a new troubleshooting investigation. This is the starting point for any new analysis.
-   `run_investigation`: Triggers the analysis for an investigation. This is a blocking call that will wait for the investigation to complete.
-   `add_observation`: Adds a new user observation to an existing investigation, creating a new revision of it.

## Usage Examples

Once the CLI is running, you can start interacting with Gemini from your shell.

You can start a project from a new directory:

```shell
cd new-project/
gemini
> Write me a Gemini Discord bot that answers questions using a FAQ.md file I will provide
```

Or work with an existing project:

```shell
git clone https://github.com/google-gemini/gemini-cli
cd gemini-cli
gemini
> Give me a summary of all of the changes that went in yesterday
```

## Development

### Running Tests

The project includes unit tests for the API and formatting utilities. To run the tests, use the following commands:

```bash
# Run tests for API utilities
npm run test:utils_unit

# Run tests for formatting utilities
npm run test:formatting_utils_unit
```