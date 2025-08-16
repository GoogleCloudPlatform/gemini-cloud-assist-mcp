/*
Copyright 2025 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

import { z } from 'zod';
import { GeminiCloudAssistClient } from './troubleshooting/api/api.js';
import { ApiError } from './shared/errors.js';
import { InvestigationViewer } from './troubleshooting/formatting_utils.js';
import {
    createInitialInvestigation,
    validateGcpResources
} from './troubleshooting/api/utils.js';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { CallToolResult } from '@modelcontextprotocol/sdk/types.js';
import { CloudAiCompanionClient, RetrieveResourceParams } from './explain/api.js'



import {
    AddObservationParams,
    CreateInvestigationParams,
    FetchInvestigationParams,
    RunInvestigationParams
} from './troubleshooting/api/types.js';

const _validateGcpResourcesAndThrow = (resources: string[]) => {
    const invalid_resources = validateGcpResources(resources);
    if (invalid_resources.length > 0) {
        let error_message = `Error: Invalid resource format for the following resources:\n`;
        for (const resource of invalid_resources) {
            error_message += `- "${resource}"\n`;
        }
        error_message += "Resources must be a fully-qualified GCP Resource URI, for example: '//compute.googleapis.com/projects/my-gcp-project/zones/us-central1-a/instances/my-vm-instance'";
        throw new ApiError(error_message, 400, 'INVALID_ARGUMENT');
    }
};

async function toolWrapper<T>(
    cb: () => Promise<CallToolResult>
): Promise<CallToolResult> {
    try {
        return await cb();
    } catch (error: any) {
        if (error instanceof ApiError) {
            return error.toToolResult();
        }
        return {
            content: [
                {
                    type: 'text',
                    text: error instanceof Error ? error.message : String(error),
                },
            ],
        };
    }
}

export const registerTools = (server: McpServer): void => {
    server.tool(
        "fetch_investigation",
        `/**
 * Fetches Gemini Cloud Assist Investigations.
 *
 * This function serves as a versatile entry point for retrieving investigation data.
 * It can operate in two modes:
 *
 * 1.  **List Mode:** If only a projectId is provided, it will list all
 *     troubleshooting investigations associated with that project. It can be
 *     optionally filtered by title using the filter_expression parameter. If the user indicates to fetch more pages, use the next_page_token parameter.
 *
 * 2.  **Get Mode:** If an investigationId is also provided, it will fetch the
 *     detailed report for that specific investigation. If a revisionId is
 *     also provided, it fetches that particular revision; otherwise, it
 *     retrieves the latest version.
 *
 */`,
        {
            projectId: z.string().describe("The Google Cloud Project ID."),
            investigationId: z.string().optional().describe("The ID of a specific investigation to fetch. If omitted, the function will list all investigations for the project."),
            revisionId: z.string().optional().describe("The revision ID of a specific investigation to fetch. Requires `investigationId` to be set."),
            filter_expression: z.string().optional().describe('A string to filter investigations by title. The filter format is `title:"<your_title>"`.'),
            next_page_token: z.string().optional().describe("A page token to retrieve a specific page of results."),
        },
        (params: FetchInvestigationParams) => toolWrapper(async () => {
            const { projectId, investigationId, revisionId, filter_expression, next_page_token } = params;
            if (revisionId && !investigationId) {
                throw new ApiError(
                    "The 'revisionId' parameter cannot be used without 'investigationId'.",
                    400,
                    'INVALID_ARGUMENT'
                );
            }
            if (next_page_token && investigationId) {
                throw new ApiError(
                    "The 'next_page_token' parameter cannot be used with 'investigationId'.",
                    400,
                    'INVALID_ARGUMENT'
                );
            }

            const client = new GeminiCloudAssistClient();
            const result = await client.fetchInvestigation({ projectId, investigationId, revisionId, filter_expression, next_page_token });
            return {
                content: [{
                    type: 'text',
                    text: result
                }]
            };
        })
    );

    server.tool(
        'create_investigation',
        `/**
 * Creates a new Gemini Cloud Assist Investigation. This tool is the primary entry point for initiating any new troubleshooting analysis.
 *
 * Prerequisites:
 * Argument Resolution: Before invoking this tool, you **MUST** resolve all user-provided information into the specific formats required by the arguments.
 *
 * Resource URI Mandate: The 'relevant_resources' parameter requires a list of full Google Cloud Platform (GCP) resource URIs.
 * - **Format:** Each URI **MUST** strictly adhere to the format: //<service>.googleapis.com/<resource-path>.
 * - **Validation:** The tool will fail if the provided strings are not well-formed URIs in this exact format.
 * - **Resolution:** You are responsible for converting any partial, ambiguous, or incomplete resource names (e.g., "my GKE cluster", "the default nodepool", or "project/zone/resource_type/resource_name") into their full URI representation. Utilize available tools like 'gcloud', 'kubectl', or your internal knowledge base to discover the complete and accurate resource URIs.
 * - **GCP Resource URI Reference**: https://cloud.google.com/asset-inventory/docs/asset-names
 *
 * Example of a correct GCP Resource URI:
 * - //compute.googleapis.com/projects/my-gcp-project/zones/us-central1-a/instances/my-vm-instance
 *
 * Additional Argument Formatting:
 * - **Timestamp ('start_time'):** Convert all relative time expressions (e.g., "30 minutes ago", "yesterday at 5pm") into the absolute 'YYYY-MM-DDTHH:mm:ssZ' UTC format. The 'Shell' tool with the 'date' command can be used for this conversion.
 * - **Project ID ('project_id'):** If a project is not explicitly mentioned by the user, you must determine the correct one from the context of the conversation or by using the command 'gcloud config get-value project'.
 *
 * **Crucial:** If you are unable to resolve any of this information into the required formats, you **MUST** seek clarification from the user before proceeding to call this tool.
 *
 * @returns {string} A summary of the new investigation, structured with Markdown.
*           You **MUST** parse this output to find the '**Investigation Path**' and '**Revision Path**'
*           fields. The final segment of the 'Investigation Path' is the 'investigation_id' and the
*           final segment of the 'Revision Path' is the 'revision_id'. These are required for subsequent tool calls.
 */`,
        {
            projectId: z.string().describe("The Google Cloud Project ID."),
            title: z.string().describe("A human-readable title. You MUST prefix the title with \"[Gemini CLI]\""),
            issue_description: z.string().describe("A detailed comprehensive description of the issue including relevant tool outputs."),
            relevant_resources: z.array(z.string()).describe("A list of fully-resolved GCP resource URIs, each starting with '//<service>.googleapis.com/...'. For example: '//compute.googleapis.com/projects/my-project/zones/us-central1-a/instances/my-instance-name'."),
            start_time: z.string().describe("The investigation start time, formatted as 'YYYY-MM-DDTHH:mm:ssZ' (UTC).")
        },
        (params: CreateInvestigationParams) => toolWrapper(async () => {
            const {
                projectId,
                title,
                issue_description,
                relevant_resources,
                start_time
            } = params;
            _validateGcpResourcesAndThrow(relevant_resources);

            const client = new GeminiCloudAssistClient();
            const investigation = createInitialInvestigation(
                title,
                projectId,
                issue_description,
                relevant_resources,
                start_time
            );

            const result = await client.createInvestigation(projectId, investigation);
            const viewer = new InvestigationViewer(result);
            const formattedOutput = viewer.render({ showObservationsAndHypotheses: false });

            return {
                content: [{
                    type: 'text',
                    text: formattedOutput
                }]
            };
        })
    );

    server.tool(
        'run_investigation',
        `/**
 * Triggers the Gemini analysis, waits for completion, and returns the final report.
 *
 * This is a **synchronous, blocking call** that runs the full analysis.
 * The tool will not return a response until the investigation is complete.
 *
 * **Workflow:** This tool **MUST** be called immediately after
 * 'create_investigation' or 'add_observation'. The string returned by this function is the final,
 * detailed report. There is no need to call any other tool after this to get the
 * results.
 *
 * **Interpreting the Output:** The output of this tool represents a set of observations & hypotheses based on the data,
 * not a definitive conclusion. NEVER treat the output as a confirmed root cause without further validation.
 * Your job is to analyze the returned hypotheses and use other tools at your disposal to gather evidence that proves or disproves them.
 *
 * @returns {string} A detailed troubleshooting report in a structured string format. The
 *           report is organized with '##' headers for sections like 'Issue',
 *           'Hypotheses', 'Relevant Observations', and 'Remediation'.
 *           **Note:** Some sections may be empty and will state "No hypotheses
 *           found." or similar. Your job is to parse this report and present

 *           a clear summary of the findings (or lack thereof) to the user.
 */`,
        {
            projectId: z.string().describe("The GCP Project ID where the investigation resides."),
            investigationId: z.string().describe("The ID of the investigation to run."),
            revisionId: z.string().describe("The specific revision ID to run."),
        },
        (params: RunInvestigationParams) => toolWrapper(async () => {
            const {
                projectId,
                investigationId,
                revisionId
            } = params;
            const client = new GeminiCloudAssistClient();

            // This is a blocking call that waits for the LRO to complete
            // and returns the final investigation object.
            const finalInvestigation = await client.runInvestigation({ projectId, investigationId, revisionId });

            // The run is complete. Now, format the final investigation report
            // using the object we already have.
            const viewer = new InvestigationViewer(finalInvestigation);
            const formattedOutput = viewer.render();


            return {
                content: [{
                    type: 'text',
                    text: formattedOutput
                }]
            };
        })
    );

    server.tool(
        'add_observation',
        `/**
 * Adds a new user observation to an existing investigation.
 *
 * Prerequisites:
 * Argument Resolution: Before invoking this tool, you **MUST** resolve any new resource names mentioned in the user's observation into the specific formats required by the arguments.
 *
 * Resource URI Mandate: If the user's 'observation' mentions new resources, the 'relevant_resources' parameter requires a list of full Google Cloud Platform (GCP) resource URIs. If no new resources are mentioned, provide an empty list '[]'.
 * - **Format:** Each URI **MUST** strictly adhere to the format: //<service>.googleapis.com/<resource-path>.
 * - **Validation:** The tool will fail if any provided strings are not well-formed URIs in this exact format.
 * - **Resolution:** You are responsible for converting any partial, ambiguous, or incomplete resource names into their full URI representation. Utilize available tools like 'gcloud', 'kubectl', or your internal knowledge base to discover the complete and accurate resource URIs.
 * - **GCP Resource URI Reference**: https://cloud.google.com/asset-inventory/docs/asset-names
 *
 * Example of a correct GCP Resource URI:
 * - //compute.googleapis.com/projects/my-gcp-project/zones/us-central1-a/instances/my-vm-instance
 *
 * **Crucial:** If you cannot resolve a new resource name into the required format, you **MUST** seek clarification from the user before proceeding to call this tool.
 *
 * Workflow: After adding an observation, you **MUST** call 'run_investigation' on the new revision to re-analyze with the added context.
 *
 * @returns {string} A string summary of the updated investigation, structured with Markdown.
 *           You **MUST** parse this output to find the '**Revision Path**' field.
 *           The final segment of this path is the new 'revision_id' that you must
 *           use for the subsequent 'run_investigation' call.
 */`,
        {
            projectId: z.string().describe("The GCP Project ID where the investigation resides."),
            investigationId: z.string().describe("The ID of the investigation."),
            observation: z.string().describe("A detailed description of the observation. This can be a direct observation from the user or the result of a previous tool call. When the user asks to add an observation, add relevant tool calls that were run after the previous run_investigation as the observation. You MUST format the observation to include a brief summary of the finding, the full command that was executed, and the complete, verbatim stdout from the command's result."),
            relevant_resources: z.array(z.string()).describe("A list of fully-resolved GCP resource URIs for any new resources mentioned in the observation, each starting with '//<service>.googleapis.com/...'. Provide an empty list if no new resources are mentioned."),
        },
        (params: AddObservationParams) => toolWrapper(async () => {
            const { projectId, investigationId, observation, relevant_resources } = params;
            _validateGcpResourcesAndThrow(relevant_resources);

            const client = new GeminiCloudAssistClient();
            const result = await client.addObservation({
                projectId,
                investigationId,
                observation,
                relevant_resources,
            });
            const viewer = new InvestigationViewer(result);
            const formattedOutput = viewer.render({ showObservationsAndHypotheses: false });
            return {
                content: [{
                    type: 'text',
                    text: formattedOutput
                }]
            };
        })
    );

    server.tool(
        'search_and_analyze_gcp_resources',
        `/**
 * An intelligent tool for querying, analyzing, and summarizing information
 * about the user's Google Cloud Platform (GCP) environment.
 * This tool delegates the request to a specialized backend agent capable of
 * complex reasoning, multi-step analysis, and searching across a large number
 * of GCP services, including but not limited to: Compute, CloudSQL, Containers.
 *
 * Limitations:
 * - DO NOT use this tool for resource metrics or usage related request. This
 *     tool cannot access the Cloud Monitoring service.
 * - DO NOT use this tool for BigQuery related request. This tool cannot access
 *     Bigquery API.
 *
 * This tool provides a comprehensive, human-readable answer synthesized by the
 * backend agent, not raw resource data.
 *
 * <important>
 * VERY IMPORTANT: The resource type is REQUIRED to be included in this query,
 * if the query type is NOT KNOWN, you MUST first ask a follow-up question to
 * identify the resource type then pass that into this tool's request.
 * </important>
 *
 * - Due to the powerful nature of this tool, simple queries such as
 * "list my VMs" which can be solved by one gcloud command should be handled by
 * the gcloud shell tool. HOWEVER, if the gcloud shell tool fails for retrieving
 * resources, you may use this tool.
 *
 * @param {string} request [REQUIRED] The user's full natural language question
 * or request regarding GCP resources. This should be detailed, include the
 * resource type and capture the exact intent of the user. The backend agent
 * will interpret this query.
 * It is very crucial that the resource type is included in this query
 * otherwise the Agent will not know where to start looking.
 *
 * @returns {string} A comprehensive, synthesized answer generated by the
 * backend agent that directly addresses the user's query. This is a narrative
 * response, which may include detailed analysis, summaries, lists of resources
 * with context, and explanations of findings.
 */`,
        {
            request: z.string().describe("The user's full natural language question or request regarding GCP resources."),
        },
        (params: RetrieveResourceParams) => toolWrapper(async () => {
            const {
                request
            } = params;
            const client = new CloudAiCompanionClient();

            // This is a blocking call that waits for the LRO to complete
            // and returns the resource.
            const retrievedResource = await client.retrieveResource({ request });

            return {
                content: [{
                    type: 'text',
                    text: retrievedResource
                }]
            };
        })
    );
};