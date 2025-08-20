# **Gemini Cloud Assist MCP Server**

[![](https://img.shields.io/github/license/GoogleCloudPlatform/gemini-cloud-assist-mcp)](./LICENSE)
[![](https://img.shields.io/github/discussions/GoogleCloudPlatform/gemini-cloud-assist-mcp?style=social&logo=github)](https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/discussions)
[![](https://img.shields.io/github/stars/GoogleCloudPlatform/gemini-cloud-assist-mcp?style=social)](https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp)

This server connects [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) clients such as the [Gemini CLI](https://github.com/google-gemini/gemini-cli) to the [**Gemini Cloud Assist APIs**](https://cloud.google.com/gemini/docs/api-and-reference). It allows you to use natural language to understand, manage, and troubleshoot your Google Cloud environment directly from the local command line.

To learn more about Gemini Cloud Assist, see the [Gemini Cloud Assist overview](https://cloud.google.com/gemini/docs/cloud-assist/) in the Google Cloud documentation.

### **Key features**

- **Create and run investigations:** Create and run Cloud Assist investigations to find the root cause of complex issues.
- **Dig deeper and iterate on investigations:** Get more details about investigation outcomes and add observations to refine the analysis.
- **Find and analyze Google Cloud resources**: Quickly check the status and performance of your Cloud resources and applications.

### **MCP configuration**

```

"mcpServers" : {
   "gemini-cloud-assist": {
     "command": "npx",
     "args": ["-y", "https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp"]
   }
}
```

## **Get started**

Before you begin, make sure you have the following:

- [**Node.js**](https://nodejs.org/en/download) v20 or later.
- [**Google Cloud SDK**](https://cloud.google.com/sdk/docs/install).
- Google Cloud project.
- Service Usage Admin (`roles/serviceusage.serviceUsageAdmin`) role on your user account in order to enable the Cloud Assist APIs.
- Gemini Cloud Assist User (`roles/geminicloudassist.user`) role on your user account in order to make requests to Cloud Assist APIs.

### **Authenticate to Google Cloud**

The Cloud Assist MCP server uses your Application Default Credentials (ADC). To set up ADC, run the following `gcloud` commands:

```shell
# Authenticate your user account to the gcloud CLI
gcloud auth login

# Set up Application Default Credentials for the server.
# This allows the MCP server to securely make Google Cloud API calls on your behalf.
gcloud auth application-default login
```

### **Configure with Gemini CLI**

To use the Cloud Assist MCP server with the Gemini CLI, add the following to your `settings.json` file:

```json
"mcpServers": {
  "gemini-cloud-assist": {
    "command": "npx",
    "args": ["-y", "https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp"]
  }
}
```

## **MCP tools**

- **`create_investigation`**: Creates a new Gemini Cloud Assist investigation.
- **`run_investigation`**: Run a Gemini Cloud Assist investigation that you created.
- **`add_observation`**: Adds new information to an investigation that you ran before.
- **`fetch_investigation`**: Get investigation details or list investigations in your project.
- **`search_and_analyze_gcp_resources`**: Find specific Cloud resources with natural language queries.

## **Examples**

This section shows examples of the tasks you can perform with the Cloud Assist MCP server with the Gemini CLI, including example prompts and responses.

<details>
<summary>Create and run investigations</summary>

```shell
Using 1 MCP server (Ctrl+T to view descriptions)

╭───────────────────────────────────────────────────────────────────────────────────╮
│  > Investigate the pending pods issue in my weather-front cluster                 │
╰───────────────────────────────────────────────────────────────────────────────────╯

✦ I can help with that. I'll start an investigation into the pending pods issue in
  your weather-front cluster. To do that, I'll run a few commands to get the
  information I need to start the investigation.
 ╭──────────────────────────────────────────────────────────────────────────────────╮
 │ ✔  Shell gcloud config get-value project (Getting the configured GCP project.)   |
 ...                                                                                |
 ...                                                                                |
 ╰──────────────────────────────────────────────────────────────────────────────────╯

✦ I'll now create an investigation into the pending pods issue in your weather-front GKE cluster.
 ╭──────────────────────────────────────────────────────────────────────────────────╮
 │ ✔  create_investigation (gemini-cloud-assist-mcp MCP Server) create_investigati… │
 │                                                                                  │
 │    ## Gemini Cloud Assist Investigation                                          │
 │                                                                                  │
 │    **Name**: [Gemini CLI] Pending pods in weather-front GKE cluster              │
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

  The main problem is that your GKE cluster `weather-front` is out of resources. It
  has only one node, and that node is full. This is causing new pods to get stuck in
  a "pending" state because there's no room for them.

  The investigation also revealed that Node Auto-Provisioning (NAP) is disabled. This
   is a key feature that allows the cluster to automatically add more nodes when it's
   running low on resources. Because NAP is disabled, the cluster can't scale up to
  meet the demand.

  I have two recommendations to fix this:
   1. Enable Node Auto-Provisioning for the weather-front cluster. This is the best
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
  in the gke-001-html-server-deployment pods. I can check the storage usage
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
  gke-gke-001-cluster-gke-001-node-pool-c67232ca-5gqk.
 ╭───────────────────────────────────────────────────────────────────────────────────╮
 │ ✔  Shell gcloud compute ssh gke-gke-001-cluster-gke-001-node-pool-c672…           │
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
     another deployment, gke-001-deployment, as a potential source of the
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
 │            *   **MIGs:**                                                          │
 │    `gke-cluster-1-default-pool-1fadf212-grp`                                      │
 │                                                                                   │
 │    *   **Cluster: `anthos-sample-cluster1` (Zone:                                 │
 │    `us-central1-c`)**                                                             │
 │        *   **Node Pool:** `default-pool`                                          │
 │            *   **Machine Type:** `e2-standard-2`                                  │
 │            *   **Initial Node Count:** 3                                          │
 │            *   **Autoscaling:** Enabled (min: 2, max: 3)                          │
 │            *   **MIGs:**                                                          │
 │    `gke-anthos-sample-cluste-default-pool-123adafs-grp`                           │
 │                                                                                   │
 │    *   **Cluster: `cluster-2` (Zone: `us-central1-c`)**                           │
 │        *   **Node Pool:** `default-pool-1`                                        │
 │            *   **Machine Type:** `e2-micro`                                       │
 │            *   **Initial Node Count:** 3                                          │
 │            *   **Autoscaling:** Enabled (max: 5)                                  │
 │            *   **MIGs:**                                                          │
 │    `gke-cluster-2-default-pool-1-15135413-grp`                                    │
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
 │    *   **gke-cluster-1-default-pool-1fadf212-grp**:                               │
 │        *   **Region/Zone**: us-central1-a                                         │
 │        *   **Creation Timestamp**: 2024-03-25T13:57:25.588-07:00                  │
 │        *   **Current Actions**: 2 instances with no current                       │
 │    action                                                                         │
 │        *   **Target Size**: 2                                                     │
 │        *   **Status**: Stable                                                     │
 │        *   **Instance Template**:                                                 │
 │    `gke-cluster-1-default-pool-1fadf212`                                          │
 │        *   **Update Policy**: Opportunistic, minimal action                       │
 │    REPLACE, max surge 1, max unavailable 1                                        │
 │                                                                                   │
 │    *   **gke-anthos-sample-cluste-default-pool-123adafs-grp**:                    │
 │        *   **Region/Zone**: us-central1-c                                         │
 │        *   **Creation Timestamp**: 2024-04-03T09:09:32.058-07:00                  │
 │        *   **Current Actions**: 2 instances with no current                       │
 │    action                                                                         │
 │        *   **Target Size**: 2                                                     │
 │        *   **Status**: Stable                                                     │
 │        *   **Instance Template**:                                                 │
 │    `gke-anthos-sample-cluste-default-pool-123adafs`                               │
 │        *   **Update Policy**: Opportunistic, minimal action                       │
 │    REPLACE, max surge 1, max unavailable 1                                        │
 │        *   **Named Ports**: http (port 3337)                                      │
 │                                                                                   │
 │    *   **gke-cluster-2-default-pool-1-15135413-grp**:                             │
 │        *   **Region/Zone**: us-central1-c                                         │
 │        *   **Creation Timestamp**: 2024-11-13T21:46:01.072-08:00                  │
 │        *   **Current Actions**: 5 instances with no current                       │
 │    action                                                                         │
 │        *   **Target Size**: 5                                                     │
 │        *   **Status**: Stable                                                     │
 │        *   **Instance Template**:                                                 │
 │    `gke-cluster-2-default-pool-1-15135413`                                        │
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
- For questions and discussions, please use [GitHub Discussions](https://github.com/GoogleCloudPlatform/gemini-cloud-assist-mcp/discussions).
- Before sending a pull request, please review our [Contributing Guide](./docs/CONTRIBUTING.md).

## **License**

This project is licensed under the Apache 2.0 License and provided as-is, without warranty or representation for any use or purpose. For details, see the [LICENSE](./LICENSE) file.
