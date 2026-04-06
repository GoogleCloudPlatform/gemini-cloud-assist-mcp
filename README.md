# Gemini Cloud Assist MCP server

> [!WARNING]
> **Deprecation Notice & Migration to Remote MCP Server**
>
> The Gemini Cloud Assist MCP server is migrating from a local Node.js architecture to a Remote MCP Server architecture. The older local Node.js server (`v0.2.0`) will lose support in the coming months.
>
> If you wish to continue using the legacy local server during the transition, please pin your configuration to version `v0.2.0` as shown in the instructions below.

[![npm @google-cloud/gemini-cloud-assist-mcp package](https://img.shields.io/npm/v/@google-cloud/gemini-cloud-assist-mcp.svg)](https://www.npmjs.com/package/@google-cloud/gemini-cloud-assist-mcp)
[![](https://img.shields.io/github/license/GoogleCloudPlatform/gemini-cloud-assist-mcp)](./LICENSE)

This server connects [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) clients such as the [Gemini CLI](https://github.com/google-gemini/gemini-cli) to the [**Gemini Cloud Assist APIs**](https://cloud.google.com/gemini/docs/api-and-reference). It allows you to use natural language to understand, manage, and troubleshoot your Google Cloud environment directly from the local command line.

> [!NOTE]
> The **Google Cloud Platform Terms of Service** (available at https://cloud.google.com/terms/) and the **Data Processing and Security Terms** (available at https://cloud.google.com/terms/data-processing-terms) do not apply to any component of the Gemini Cloud Assist MCP Server software.

To learn more about Gemini Cloud Assist, see the [Gemini Cloud Assist overview](https://cloud.google.com/gemini/docs/cloud-assist/) in the Google Cloud documentation.

## ✨ Key features

- **Create and run investigations:** Create and run Cloud Assist investigations to find the root cause of complex issues.
- **Dig deeper and iterate on investigations:** Get more details about investigation outcomes and add observations to refine the analysis.

## Quick start

Before you begin, ensure you have the following set up:

- [**Node.js**](https://nodejs.org/en/download) (v20 or later).
- [**Git**](https://git-scm.com/downloads).
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
# This allows the MCP server to securely make Google Cloud API calls on your behalf.
gcloud auth application-default login
```

### Step 2: Configure your MCP client

Below is the standard configuration snippet you will use. It tells the client to use `npx` to download and run the latest version of the MCP server on demand. Paste the MCP configuration to an MCP client of your choosing. We recommend using the [Gemini CLI](https://github.com/google-gemini/gemini-cli) for the best experience.

#### MCP config

```json
"mcpServers" : {
   "GeminiCloudAssist": {
     "command": "npx",
     "args": ["-y", "@google-cloud/gemini-cloud-assist-mcp@0.2.0"],
     "timeout": 600000
   }
}
```

## Setup instructions for MCP clients

### Gemini CLI

#### Option 1 (recommended): Extension installation

Install the MCP server as a [Gemini CLI extension](https://github.com/google-gemini/gemini-cli/blob/main/docs/extension.md):

```shell
gemini extensions install https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp
```

Validate successful installation by running:

```shell
gemini extensions list
```

#### Option 2: Global installation

Add the [MCP config](#mcp-config) to the **_\~/.gemini/settings.json_**. This gives you access to MCP Tools in every Gemini CLI session.

#### Option 3: Project-level installation

Add the [MCP config](#mcp-config) to your **_/path/to/project/.gemini/settings.json_** file. This gives you access to the MCP Tools in Gemini CLI sessions created under this project folder only.

### Cursor

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/install-mcp?name=GeminiCloudAssist&config=eyJ0aW1lb3V0Ijo2MDAwMDAsImNvbW1hbmQiOiJucHggLXkgQGdvb2dsZS1jbG91ZC9nZW1pbmktY2xvdWQtYXNzaXN0LW1jcEBsYXRlc3QifQ%3D%3D)

### Claude Desktop

- Launch the Claude Desktop application.
- Navigate to Settings > Developer.
- Click the Edit config button to open the **claude_desktop_config.json** file.
- Add the [MCP config](#mcp-config) to the **claude_desktop_config.json** file.
- Save the file and restart Claude Desktop.

### Claude Code

```shell
claude mcp add GeminiCloudAssist npx -y @google-cloud/gemini-cloud-assist-mcp@0.2.0
```

Follow [detailed instructions](https://docs.anthropic.com/en/docs/claude-code/mcp#installing-mcp-servers) on Anthropic's documentation for more information.

### Cline

Update **cline_mcp_settings.json** with the [MCP config](#mcp-config).

Follow [detailed instructions](https://docs.cline.bot/mcp/adding-mcp-servers-from-github) on Cline's website for more information.

## 🛠️ MCP tools

- **`create_investigation`**: Creates a new Gemini Cloud Assist investigation.
- **`run_investigation`**: Runs an existing Gemini Cloud Assist investigation that you created.
- **`add_observation`**: Adds a new observation to an existing investigation to refine its analysis.
- **`fetch_investigation`**: Get investigation details or list investigations in your project.

## Examples

This section shows examples of the tasks you can perform with the Cloud Assist MCP server with the Gemini CLI, including example prompts and responses.

<details>
<summary>Create and run investigations</summary>

```shell
Using 1 MCP server (Ctrl+T to view descriptions)

╭───────────────────────────────────────────────────────────────────────────────────╮
│  > Investigate the pending pods issue in my test-cluster-1 cluster                │
╰───────────────────────────────────────────────────────────────────────────────────╯

✦ I can help with that. I'll start an investigation into the pending pods issue in
  your test-cluster-1 cluster. To do that, I'll run a few commands to get the
  information I need to start the investigation.
 ╭──────────────────────────────────────────────────────────────────────────────────╮
 │ ✔  Shell gcloud config get-value project (Getting the configured GCP project.)   |
 ...                                                                                |
 ...                                                                                |
 ╰──────────────────────────────────────────────────────────────────────────────────╯

✦ I'll now create an investigation into the pending pods issue in your test-cluster-1 GKE cluster.
 ╭──────────────────────────────────────────────────────────────────────────────────╮
 │ ✔  create_investigation (gemini-cloud-assist-mcp MCP Server) create_investigati… │
 │                                                                                  │
 │    ## Gemini Cloud Assist Investigation                                          │
 │                                                                                  │
 │    **Name**: [Gemini CLI] Pending pods in test-cluster-1 GKE cluster             │
 ...                                                                                |
 ...                                                                                |
 ╰──────────────────────────────────────────────────────────────────────────────────╯

✦ I've created the investigation. Now I'll run it to analyze the issue.
 ╭──────────────────────────────────────────────────────────────────────────────────╮
 │ ✔  run_investigation (gemini-cloud-assist-mcp MCP Server) run_investigation (ge… │
 ...                                                                                |
 ...                                                                                |
 ╰──────────────────────────────────────────────────────────────────────────────────╯

✦ The investigation is complete. Here's what I found:

  The main problem is that your GKE cluster `test-cluster-1` is out of resources. It
  has only one node, and that node is full. This is causing new pods to get stuck in
  a "pending" state because there's no room for them.

  The investigation also revealed that Node Auto-Provisioning (NAP) is disabled. This
   is a key feature that allows the cluster to automatically add more nodes when it's
   running low on resources. Because NAP is disabled, the cluster can't scale up to
  meet the demand.

  I have two recommendations to fix this:
   1. Enable Node Auto-Provisioning for the test-cluster-1 cluster. This is the best
      long-term solution because it will allow the cluster to automatically scale up
      and down as needed.
   2. Manually add more nodes to the cluster. This is a good short-term solution that
       will immediately relieve the resource pressure and allow the pending pods to
      be scheduled.

  I recommend that you start by enabling Node Auto-Provisioning. I can do this for
  you now, or you can do it yourself by following the instructions in the official
  documentation (https://cloud.google.com/kubernetes-engine/docs/how-to/node-auto-pro
  visioning#enable).

  What would you like to do?
```

</details>

<details>
<summary>Dig deeper and iterate on investigations</summary>

```shell
✦ The investigation is complete. Here's a summary of the findings:

  Primary Cause:

   * Ephemeral Storage Exhaustion: The main reason for the pod crashes is
     that the GKE nodes are running out of ephemeral storage. This is
     causing a DiskPressure condition on the nodes, which in turn leads to
     the kubelet evicting pods to free up space.

 ╭───────────────────────────────────────────────────────────────────────────────────╮
 │  > Do you know which pod is consuming all the storage space?                      │
 ╰───────────────────────────────────────────────────────────────────────────────────╯

✦ That's a great question. The investigation points to the emptyDir volume
  in the gke-001-deployment pods. I can check the storage usage
  inside one of the running pods to confirm this.

  First, I'll list the pods to find one that is currently running.
 ╭───────────────────────────────────────────────────────────────────────────────────╮
 │ ✔  Shell kubectl get pods -n gke-001-namespace (This command will list..          │
 ...                                                                                 |
 ...                                                                                 |
 ╰───────────────────────────────────────────────────────────────────────────────────╯


✦ That's unexpected. The /data directory in that pod is only using 4.0K,
  which is negligible. This contradicts the hypothesis that the emptyDir
  volume is the primary consumer of ephemeral storage.

  This means something else on the node is consuming the storage. It could
  be logs, or another process running on the node that isn't immediately
  obvious.

  To figure this out, I'll need to get a shell on the node itself and
  investigate the storage usage from there. I'll start by getting an
  interactive shell on the node
  gke-001-cluster-gke-001-node-pool-001.
 ╭───────────────────────────────────────────────────────────────────────────────────╮
 │ ✔  Shell gcloud compute ssh gke-001-cluster-gke-001-node-pool-001…                │
 ...                                                                                 |
 ...                                                                                 |
 │    ERROR: (gcloud.compute.ssh) [/usr/local/bin/ssh] exited                        │
 │    with return code [255].                                                        |
 ╰───────────────────────────────────────────────────────────────────────────────────╯

✦ It seems I can't directly SSH into the node. This is likely due to
  firewall rules or the node not having an external IP address.

  However, I can still investigate the node's storage. I'll add an
  observation to the investigation, noting that the emptyDir volume is not
  the cause of the storage issue, and then re-run the investigation. This
  will allow Gemini to analyze the node's logs and other signals to
  pinpoint the true source of the storage consumption.
 ╭───────────────────────────────────────────────────────────────────────────────────╮
 │ ✔  add_observation (gemini-cloud-assist MCP Server) {"observation":"Fu…           │
 │                                                                                   │
 │    ## Gemini Cloud Assist Investigation                                           │
 │                                                                                   │
 │    **Name**: [Gemini CLI] GKE pods crashing due to ephemeral storage issues       │
 ...                                                                                 |
 ...                                                                                 |
 ╰───────────────────────────────────────────────────────────────────────────────────╯

✦ I've added the new information to the investigation. Now I'll re-run the
  analysis. This will take the new observation into account and should help
  us identify the real source of the storage consumption.
 ╭───────────────────────────────────────────────────────────────────────────────────╮
 │ ✔  run_investigation (gemini-cloud-assist MCP Server) {"investigationI…           │
 │                                                                                   │
 ...                                                                                 |
 ...                                                                                 |
 ╰───────────────────────────────────────────────────────────────────────────────────╯


✦ The new investigation results are in.

  Key Findings:

   * `emptyDir` Ruled Out: The investigation confirms our finding that the
     emptyDir volume is not the cause of the storage pressure.
   * Container Logs are the Likely Culprit: The analysis strongly suggests
     that the ephemeral storage is being consumed by container logs. The
     kubelet is failing to reopen log files due to "no space left on
     device," which is a clear indicator of this issue.
   * Another Deployment is Implicated: The investigation also points to
     another deployment, gke-002-deployment, as a potential source of the
     problem. The logs mention that this deployment is "configured to fill
     up disk."
```

</details>

<details>
<summary>Search and analyze Cloud resources </summary>

```shell
 ╭───────────────────────────────────────────────────────────────────────────────────╮
 │  > Give me an overview of my GKE node pools. For each one, show me its            │
 │    cluster and MIGs                                                               │
 ╰───────────────────────────────────────────────────────────────────────────────────╯

 ╭───────────────────────────────────────────────────────────────────────────────────╮
 │ ✔  search_and_analyze_gcp_resources (gemini-cloud-assist-mcp MCP Server) s…       │
 │                                                                                   │
 │    Based on the output of the `container.googleapis.com` API                      │
 │    calls, here is an overview of your GKE node pools, including                   │
 │    their associated clusters and Managed Instance Groups (MIGs):                  │
 │                                                                                   │
 │    *   **Cluster: `cluster-1` (Zone: `us-central1-a`)**                           │
 │        *   **Node Pool:** `default-pool`                                          │
 │            *   **Machine Type:** `custom-1-3840`                                  │
 │            *   **Initial Node Count:** 3                                          │
 │            *   **Autoscaling:** Enabled (min: 1, max: 5)                          │
 │            *   **MIGs:**  `gke-cluster-1-default-pool-001-grp`                    │
 │                                                                                   │
 │    *   **Cluster: `anthos-cluster-1` (Zone: `us-central1-c`)**                    |
 │        *   **Node Pool:** `default-pool`                                          │
 │            *   **Machine Type:** `e2-standard-2`                                  │
 │            *   **Initial Node Count:** 3                                          │
 │            *   **Autoscaling:** Enabled (min: 2, max: 3)                          │
 │            *   **MIGs:** `gke-anthos-cluster-default-pool-001-grp`                |
 │                                                                                   │
 │    *   **Cluster: `cluster-2` (Zone: `us-central1-c`)**                           │
 │        *   **Node Pool:** `default-pool-1`                                        │
 │            *   **Machine Type:** `e2-micro`                                       │
 │            *   **Initial Node Count:** 3                                          │
 │            *   **Autoscaling:** Enabled (max: 5)                                  │
 │            *   **MIGs:**  `gke-cluster-2-default-pool-001-grp`                    │
 ╰───────────────────────────────────────────────────────────────────────────────────╯
✦ OK. Here's an overview of your GKE node pools, their clusters, and MIGs. Is
  there anything else I can help you with?
 ╭───────────────────────────────────────────────────────────────────────────────────╮
 │  > Tell me details about each MIG                                                 │
 ╰───────────────────────────────────────────────────────────────────────────────────╯

 ╭───────────────────────────────────────────────────────────────────────────────────╮
 │ ✔  search_and_analyze_gcp_resources (gemini-cloud-assist-mcp MCP Server) s…       │
 │                                                                                   │
 │    I found the following details for the requested Managed                        │
 │    Instance Groups (MIGs):                                                        │
 │                                                                                   │
 │    *   **gke-cluster-1-default-pool-001-grp**:                                    │
 │        *   **Region/Zone**: us-central1-a                                         │
 │        *   **Creation Timestamp**: 2024-03-25T13:57:25.588-07:00                  │
 │        *   **Current Actions**: 2 instances with no current                       │
 │    action                                                                         │
 │        *   **Target Size**: 2                                                     │
 │        *   **Status**: Stable                                                     │
 │        *   **Instance Template**:                                                 │
 │    `gke-cluster-1-default-pool-001`                                               │
 │        *   **Update Policy**: Opportunistic, minimal action                       │
 │    REPLACE, max surge 1, max unavailable 1                                        │
 │                                                                                   │
 │    *   **gke-anthos-cluster-default-pool-001-grp**:                               │
 │        *   **Region/Zone**: us-central1-c                                         │
 │        *   **Creation Timestamp**: 2024-04-03T09:09:32.058-07:00                  │
 │        *   **Current Actions**: 2 instances with no current                       │
 │    action                                                                         │
 │        *   **Target Size**: 2                                                     │
 │        *   **Status**: Stable                                                     │
 │        *   **Instance Template**:                                                 │
 │    `gke-anthos-cluster-default-pool-001`                                          │
 │        *   **Update Policy**: Opportunistic, minimal action                       │
 │    REPLACE, max surge 1, max unavailable 1                                        │
 │        *   **Named Ports**: http (port 3337)                                      │
 │                                                                                   │
 │    *   **gke-cluster-2-default-pool-001-grp**:                                    │
 │        *   **Region/Zone**: us-central1-c                                         │
 │        *   **Creation Timestamp**: 2024-11-13T21:46:01.072-08:00                  │
 │        *   **Current Actions**: 5 instances with no current                       │
 │    action                                                                         │
 │        *   **Target Size**: 5                                                     │
 │        *   **Status**: Stable                                                     │
 │        *   **Instance Template**:                                                 │
 │    `gke-cluster-2-default-pool-001`                                               │
 │        *   **Update Policy**: Opportunistic, minimal action                       │
 │    REPLACE, max surge 1, max unavailable 1                                        │
 │                                                                                   │
 │    These details were retrieved by calling the Compute Engine                     │
 │    API's `instanceGroupManagers.get` and                                          │
 │    `instanceGroupManagers.aggregatedList` methods.                                │
 ╰───────────────────────────────────────────────────────────────────────────────────╯
✦ Here are the details for each MIG. Let me know if you need anything else.

```

</details>

## **Contributing**

- If you encounter a bug, please file an issue on our [GitHub Issues](https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/issues) page.
- Before sending a pull request, please review our [Contributing Guide](./docs/CONTRIBUTING.md).

## **License**

This project is licensed under the Apache 2.0 License and provided as-is, without warranty or representation for any use or purpose. For details, see the [LICENSE](./LICENSE) file.
