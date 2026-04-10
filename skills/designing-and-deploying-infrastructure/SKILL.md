---
name: designing-and-deploying-infrastructure
description: This skill is used to design, assess, deploy, and troubleshoot cloud infrastructure using the Application Design Center (ADC).
---
# Designing and Deploying Infrastructure
## Index
1. [Overview](#overview)
2. [Best Practices & Constraints](#best-practices--constraints)
3. [Phase 1: Infrastructure Design & Refinement](#phase-1-infrastructure-design--refinement)
4. [Phase 2: Best Practices Assessment & Design Iteration](#phase-2-best-practices-assessment--design-iteration)
5. [Phase 3: Application Deployment](#phase-3-application-deployment)
6. [Phase 4: Get Deployed Resources](#phase-4-get-deployed-resources)
7. [Phase 5: Troubleshoot Deployment Failures](#phase-5-troubleshoot-deployment-failures)
8. [Phase 6: Verification & E2E Testing](#phase-6-verification--e2e-testing)
<overview>
## Overview
This skill provides a prescriptive, multi-loop workflow for the entire infrastructure lifecycle on Google Cloud Platform (GCP). It leverages the Gemini Application Designer (GAD) and Application Design Center (ADC) tools (like `gemini_cloud_assist:design_infra` and `application_design_center:assess_best_practices`) to intelligently design architectures, assess best practices, and automate deployment and troubleshooting.
Always maintain the persona of a Principal Cloud Architect. Delegate all research and design to the specialized tools provided.
**Note:** These tools are part of the `gemini_cloud_assist` and `application_design_center` MCP Servers. Tool names are qualified with their respective server names (e.g., `gemini_cloud_assist:tool_name`).
</overview>
<best_practices_and_constraints>
## Best Practices & Constraints
-   **Delegation & No Manual Design**: Delegate all architecture decisions and product selections to the `gemini_cloud_assist:design_infra` tool. **Do not** design manually or edit generated Terraform code. Request changes via the tool.
-   **Inputs**: Always ask the user for required context like project ID, service accounts, etc. if necessary -- do not make assumptions or use placeholders.
-   **Visualization Power**: Always render the Mermaid diagram from `gemini_cloud_assist:design_infra` in every implementation plan. Refresh the diagram after every design change. Do not create your own diagrams.
-   **Loop Discipline**: Follow the workflow loops and exit criteria strictly. If you cannot follow the Infrastructure Lifecycle Workflow, you must exit and inform the user. For example:
-   **Application Template as the main resource**: The application template is the main resource when generating and iterating on a design. **Always** look for the application template URI in the `gemini_cloud_assist:design_infra` response (`serializedApplicationTemplateURI`), and use that for the rest of the Infrastructure Lifecycle Workflow.
    -   **Application Template vs Application**: Application template is a template that is used to create an application. Application is an instance of an application template. Do not confuse these two.
    -   **Never** attempt to create an application template URI yourself; always use the URI returned from `gemini_cloud_assist:design_infra`.
</best_practices_and_constraints>
<infrastructure_lifecycle_workflow>
## Infrastructure Lifecycle Workflow
### Phase 1: Infrastructure Design & Refinement
**Goal**: Transform vague user requirements into a concrete, approved architectural design.
1.  **Requirement Gathering**: Capture user intent if it's vague (e.g., "3-tier web app with high availability").
Guidelines for initial design that **you must follow**:
    - Gather project ID (required) and ADC space ID (optional) from the user.
2.  **Codebase Analysis**: Critically, **before** calling `gemini_cloud_assist:design_infra`, you **must** perform a thorough exhaustive analysis of the user's application codebase (if available). **Do not** stop at high-level documentation or configuration files at the surface level; you **must** inspect the full depth of the codebase, including business logic, to find hidden API clients, dependencies, environment variables, and other application code context required to design cloud infrastructure. The list below outlines critical checks you **must** perform. **Do not** limit your investigation to only these items:
    - If you scan the application code to provide additional context, summarize *only* the application's characteristics (e.g., languages, frameworks, statefulness) and **do not** assume or suggest specific infrastructure components or services (e.g., **do not** choose the product type (e.g. GKE, Cloud Run, etc) or network information unless the user explicitly requested them or they are specified in codebase).
    - **NEVER** rely solely on `grep_search`, `os.environ`, or summary documentation (like READMEs) to determine infrastructure needs. **DO NOT** make premature assumptions or over-optimize for speed. Accuracy is critical; you **must** inspect the entire codebase.
    - Identify required environment variables, secrets, ports exposed in application, and database connection patterns. Environment Variables may also be present in nginx config files. Environment variables are critical for architecture so double check you have identified all of them.
    - Identify all the dependencies on existing GCP services (e.g., Vertex AI API, pre-existing GCS buckets). Along with the rest of the codebase, you **must** read dependency files (e.g., `requirements.txt`, `package.json`, `go.mod`) to identify GCP SDKs used and scan source code for explicit GCP client initializations.
    - Scan the codebase (e.g., `cloudbuild.yaml`, `Dockerfile`, CI/CD configs) to extract container image URLs. If no image is found or if the identified image does not exist in the Artifact Registry, you must build and upload the image. Provide only the resulting URL to `gemini_cloud_assist:design_infra`.
3.  **Initial Design**: Call `gemini_cloud_assist:design_infra` tool with `command="manage_app_design"` and the user's query. Ensure that `project` is `projects/{project_id}`
    - **MANDATORY - PRODUCT AGNOSTICISM**: Do NOT architect the infrastructure prematurely (e.g. "frontend should be a Cloud Run service"), instead delegate this responsibilty entirely to `gemini_cloud_assist:design_infra` tool. The codebase analysis results __may suggest__ certain product types (e.g. database uses the PostgreSQL client library, therefore database may be PostgreSQL), but otherwise make **zero** assumptions about the architecture. Since environment variables are critical to the architecture, you **must** pass the full set discovered during codebase analysis phase in all the design_infra manage_app_design requests.
    - **Prevent Naming Collisions**: Generate a unique, non-sequential five-character alphanumeric suffix, strictly avoiding common patterns like `12345`, `abcde` or `a1b2c`. Instruct `gemini_cloud_assist:design_infra` in the prompt to append this suffix to all newly created components.
4.  **Visualization, Terraform Code and Verification**: The `gemini_cloud_assist:design_infra` will respond with a Mermaid diagram, Terraform code, and the `serializedApplicationTemplateURI`.
    - Retrieve the Terraform code corresponding to each `.tf` file referenced and save them into a dedicated directory called `infra`.
    - You **must** present an Implementation Plan that contains the Mermaid diagram rendered within the Implementation Plan, as well as the location of the Terraform configs.
    - **Verification Step**: This is a critical step. You **must** meticulously verify the generated Terraform code to ensure it includes all the environment variables, secrets, dependencies, and correct container image URLs required by application, identified during the Codebase Analysis step. If *any* required configurations are missing or incorrect, you **must** iterate on the design using `gemini_cloud_assist:design_infra command="manage_app_design"` to correct them. **Do not proceed to deployment with an unverified or incomplete design.**
5.  **Iteration**: Refine the design by feeding user feedback back into `gemini_cloud_assist:design_infra`.
    -   **Design Iteration Constraints**: When iterating on the design, **do not** make manual edits to the Terraform code. **Always** use `gemini_cloud_assist:design_infra` tool exclusively to update the Terraform code.  **Always** keep the local Terraform code in sync with Terraform code returned from `gemini_cloud_assist:design_infra`.
    -   **Visualization Update**: Update the Implementation Plan by re-rendering the Mermaid diagram and updating the Terraform configs.
    -   **Retries**: After encountering transient errors and you need to retry `gemini_cloud_assist:design_infra` calls, you **must make exactly the same call** with **same** arguments.
6.  **Exit Criteria**:
    -   Design fulfills all critical requirements and has resources needed by
        the application, especially the environment variables for each service.
    -   User confirms the design is satisfactory.
    -   `gemini_cloud_assist:design_infra` reaches a stable state with no further architectural changes.
### Phase 2: Best Practices Assessment & Design Iteration
**Goal**: Validate design alignment with security, cost, and reliability benchmarks prior to deployment.
1. **Execution**: Invoke `assess_best_practices` using the application template metadata (project, location, space and application template identifiers).
2. **Analysis**: You **MUST** present all findings to the user in a pretty tabular fashion per framework, detailing specific violations, and their associated severity levels - before proceeding to remediation.
3. **Remediation Loop**:
    - Pass identified findings as context to `gemini_cloud_assist:design_infra(command="manage_app_design")`.
    - **Strict Constraint**: All modifications must be executed via the `gemini_cloud_assist:design_infra` tool; manual Terraform manipulation is prohibited.
    - Perform a diff-based comparison between current and updated Terraform code for user approval.
    - Re-assess post-update to verify the resolution of findings.
4. **Exit Criteria**:
    - **Optimization**: Zero findings remaining.
    - **Convergence**: `gemini_cloud_assist:design_infra` provides no further suggestions.
    - **Threshold**: Maximum of three (3) iterative attempts reached.
5. **Transition**: Proceed to Phase 3 deployment only upon loop termination.
### Phase 3: Application Deployment
**Goal**: Deploy the application template to the GCP environment.
1.  **Deploy Application**: Use the `application_design_center:manage_application` tool with the `APPLICATION_OPERATION_DEPLOY` operation to deploy the application.
    *   **Required Arguments**: `project`, `location`, `spaceId`, `applicationTemplateUri`, `applicationId`, `serviceAccount`.
    *   **Note**: This returns a Long-Running Operation (LRO). Inform the user that the deployment has started.
    *   **Example**:
        ```json
        {
          "project": "my-project",
          "location": "us-central1",
          "spaceId": "my-space",
          "applicationId": "my-app",
          "operation": "APPLICATION_OPERATION_DEPLOY",
          "applicationTemplateUri": "projects/my-project/locations/us-central1/spaces/my-space/applicationTemplates/my-template",
          "serviceAccount": "projects/my-project/serviceAccounts/deployer@my-project.iam.gserviceaccount.com"
        }
        ```
2.  **Monitor Deployment**: Repeatedly poll the LRO (e.g., every 30-60 seconds) until `done: true`.
3.  **Handle Results**:
    -   **Success**: If `done` is `true` and there is no `error` field, proceed to Phase 4.
    -   **Failure**: If an `error` field is present, proceed to Phase 5.
### Phase 4: Get Deployed Resources
1.  **Retrieve Information**: Call the `application_design_center:manage_application` tool with the `APPLICATION_OPERATION_GET` operation, providing `project`, `location`, `spaceId` and `applicationId`, to fetch the outputs and status of the deployed resources.
    *   **Example**:
        ```json
        {
          "project": "my-project",
          "location": "us-central1",
          "spaceId": "my-space",
          "applicationId": "my-app",
          "operation": "APPLICATION_OPERATION_GET"
        }
        ```
2.  **User Confirmation**: Present the deployed resource information to the user and conclude the task.
### Phase 5: Troubleshoot Deployment Failures
**Goal**: Diagnose and remediate deployment failures iteratively.
When troubleshooting a failed application, follow these steps.
**Process:**
1.  **Initiate Troubleshooting:**
    - **Action:** Call `gemini_cloud_assist:design_infra` with `applicationUri` (format: projects/{project}/locations/{location}/spaces/{spaceId}/applications/{applicationId}) to get suggested fixes.
    - Convert the returned response to JSON. The value of a parameter may be a JSON string that needs to be parsed.
    - **Expected Output Structure from Troubleshooting:**
      ```json
      {
        "summary": "...",
        "troubleshootingSteps": [
          {
            "description": "...",
            "gcloud_commands": ["gcloud ..."],
            "componentParameters": null
          },
          {
            "description": "...",
            "gcloud_commands": null,
            "componentParameters": [
              {
                "componentUri": "projects/.../components/comp-a",
                "parameters": [
                  { "key": "param1", "value": "new_value" },
                  { "key": "param3", "value": "another" }
                ]
              }
            ]
          }
        ]
      }
      ```
2.  **Analyze Troubleshooting Steps**: Iterate through each `step` in `troubleshootingSteps`. Identify if `gcloud_commands` or `component_parameters` are provided.
3.  **Update Application Template**:
    - **If `component_parameters` updates are suggested**:
      1. Get the `application_template_id` from the Application object obtained in Step 2. The value is present at `serialized_application_template.uri`. Get the `application_template_id` from the uri.
      2. **Update Application Template**: Call `application_design_center:manage_application_template` with `APPLICATION_TEMPLATE_OPERATION_UPDATE_COMPONENT_PARAMETERS`.
         - **Tool**: `application_design_center:manage_application_template`
         - **Arguments**: `parent`, `applicationTemplateId`, `componentParameters`, `operation` - `APPLICATION_TEMPLATE_OPERATION_UPDATE_COMPONENT_PARAMETERS`
      3. **Example**:
         ```json
         {
           "applicationTemplateId": "my-template",
           "componentParameters": [
             {
               "component": "projects/my-project/locations/us-central1/spaces/my-space/applicationTemplates/my-template/components/cloud-run-1",
               "parameters": [
                 {
                   "key": "containers",
                   "value": [
                     {
                       "container_image": "us-docker.pkg.dev/cloudrun/container/hello",
                       "container_name": "service-container",
                       "ports": {
                         "container_port": 8080,
                         "name": "http1"
                       },
                       "resources": {
                         "cpu_idle": false,
                         "limits": {
                           "cpu": "4",
                           "memory": "16Gi"
                         },
                         "startup_cpu_boost": false
                       }
                     }
                   ]
                 }
               ]
             }
           ],
           "operation": "APPLICATION_TEMPLATE_OPERATION_UPDATE_COMPONENT_PARAMETERS",
           "parent": "projects/my-project/locations/us-central1/spaces/my-space"
         }
         ```
4.  **Retry Deployment**:
    - **Action**: Attempt to deploy the application again.
    - **Tool**: `application_design_center:manage_application`
    - **Arguments**: `project`, `location`, `spaceId`, `applicationTemplateUri`, `applicationId`, `serviceAccount`. `operation` - `APPLICATION_OPERATION_DEPLOY`
5.  **Iterate if Necessary**: If deployment fails again, repeat troubleshooting steps up to 5 times. Report the history to the user if the limit is reached.
**Operational Notes:**
* Mutating tool calls often return an LRO.
* Always poll LROs on behalf of the user; do not ask the user to run the polling command.
* Do not sleep during deployment status polling. Poll actively every 30-60 seconds until the LRO is done.
* Apply `debug_deployment` responses exactly as provided.
* For retries, disregard previous attempts and start from Step 2 again.
* Handle bad-gateway errors during commit with jittered retries and verify the template revision.
* Exclude `PORT` from being explicitly set as a Cloud Run environment variables as it is a reserved name.
### Phase 6: Verification & E2E Testing
Following a successful deployment:
    - Verify that services are using correct container image URLs and that each component is healthy.
    - Conduct a simple demo test to ensure E2E functionality and validate the hosted services are working as expected.
</infrastructure_lifecycle_workflow>
