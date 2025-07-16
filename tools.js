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
import { ApiError } from './troubleshooting/api/errors.js';
import { InvestigationViewer } from './troubleshooting/formatting_utils.js';
import { createInitialInvestigation } from './troubleshooting/api/utils.js';

export const registerTools = (server) => {
    server.tool(
        "fetch_investigation",
        `/**
 * Fetches Gemini Cloud Assist troubleshooting investigations.
 *
 * This function serves as a versatile entry point for retrieving investigation data.
 * It can operate in two modes:
 *
 * 1.  **List Mode:** If only a projectId is provided, it will list all
 *     troubleshooting investigations associated with that project. It can be
 *     optionally filtered by title using the filter_expression parameter.
 *
 * 2.  **Get Mode:** If an investigationId is provided, it will fetch the
 *     detailed report for that specific investigation. If a revisionId is
 *     also provided, it fetches that particular revision; otherwise, it
 *     retrieves the latest version.
 *
 * The function handles constructing the correct API request based on the
 * presence of investigationId and revisionId.
 */`,
        {
            projectId: z.string().describe("The Google Cloud Project ID."),
            investigationId: z.string().optional().describe("The ID of a specific investigation to fetch. If omitted, the function will list all investigations for the project."),
            revisionId: z.string().optional().describe("The revision ID of a specific investigation to fetch. Requires `investigationId` to be set."),
            filter_expression: z.string().optional().describe('A string to filter investigations by title. The filter format is `title:"<your_title>"`.'),
        },
        async ({ projectId, investigationId, revisionId, filter_expression }) => {
            if (revisionId && !investigationId) {
                return {
                    content: [{
                        type: 'text',
                        text: "The 'revisionId' parameter cannot be used without 'investigationId'."
                    }]
                };
            }

            const client = new GeminiCloudAssistClient();
            try {
                const result = await client.fetchInvestigation({ projectId, investigationId, revisionId, filter_expression });
                return {
                    content: [{
                        type: 'text',
                        text: result
                    }]
                };
            } catch (error) {
                if (error.name === 'ApiError') {
                    return {
                        content: [{
                            type: 'tool-error',
                            code: error.code,
                            message: error.message,
                            details: error.details
                        }]
                    };
                }
                // Fallback for generic errors
                return {
                    content: [{
                        type: 'tool-error',
                        code: 'UNEXPECTED_ERROR',
                        message: error.message
                    }]
                };
            }
        },
        {
            'mcp:tool-class': 'read-only'
        }
    );

    server.tool(
        'create_investigation',
        `/**
 * Creates a new Gemini Cloud Assist Investigation.
 *
 * This is the first and mandatory step.
 *
 * This tool is the primary entry point for starting any new troubleshooting
 * analysis.
 *
 * **Prerequisites: Argument Resolution**
 * Before calling this tool, you **MUST** resolve all user-provided information
 * into the required, specific formats using your available tools.
 * - **Resource URIs ('relevant_resources')**: Convert vague names (e.g., "my
 *   GKE cluster", "the default nodepool") into full resource URIs. Use
 *   'gcloud', 'kubectl', or 'Memorybank' to find the exact paths.
 * - **Timestamp ('start_time')**: Convert relative times (e.g., "30 minutes
 *   ago", "yesterday at 5pm") into the absolute 'YYYY-MM-DDTHH:mm:ssZ'
 *   (UTC) format. Use the 'Shell' tool (e.g., with the 'date' command).
 * - **Project ID ('project_id')**: If the user doesn't specify a project,
 *   determine the correct one from context or by using 'gcloud config get-value
 *   project'.
 * **If you cannot resolve any of this information, you MUST ask the user for
 * clarification before proceeding.**
 *
 * @param {string} projectId [REQUIRED] The fully-resolved Google Cloud Project ID.
 * @param {string} title [REQUIRED] A human-readable title. You MUST prefix the title with "[Gemini CLI]".
 * @param {string} issue_description [REQUIRED] A detailed description of the issue.
 * @param {Array<string>} relevant_resources [REQUIRED] A list of fully-resolved resource URIs.
 * @param {string} start_time [REQUIRED] The investigation start time, formatted as 'YYYY-MM-DDTHH:mm:ssZ' (UTC).
 * @returns {string} A summary of the new investigation, structured with markdown. You
 *      **MUST**
 *           parse this output to find the '**Investigation Path**' and
 *           '**Revision Path**'
 *           fields. The final segment of the 'Investigation Path' is the
 *           'investigation_id',
 *           and the final segment of the 'Revision Path' is the 'revision_id'.
 *           These
 *           are required for subsequent tool calls.
 */`,
        {
            projectId: z.string().describe('The Google Cloud Project ID.'),
            title: z.string().describe('The title of the investigation.'),
            issue_description: z.string().describe('A description of the issue.'),
            relevant_resources: z.array(z.string()).describe('A list of relevant resources.'),
            start_time: z.string().describe('The start time of the issue in RFC3339 UTC "Zulu" format.')
        },
        async ({
            projectId,
            title,
            issue_description,
            relevant_resources,
            start_time
        }) => {
            const client = new GeminiCloudAssistClient();
            const investigation = createInitialInvestigation(
                title,
                projectId,
                issue_description,
                relevant_resources,
                start_time
            );

            try {
                const result = await client.createInvestigation(projectId, investigation);
                const viewer = new InvestigationViewer(result);
                const formattedOutput = viewer.render();

                return {
                    content: [{
                        type: 'text',
                        text: formattedOutput
                    }]
                };
            } catch (error) {
                if (error.name === 'ApiError') {
                    return {
                        content: [{
                            type: 'tool-error',
                            code: error.code,
                            message: error.message,
                            details: error.details
                        }]
                    };
                }
                // Fallback for generic errors
                return {
                    content: [{
                        type: 'tool-error',
                        code: 'UNEXPECTED_ERROR',
                        message: error.message
                    }]
                };
            }
        }
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
 * 'create_investigation'
 * or 'add_observation'. The string returned by this function is the final,
 * detailed report. There is no need to call any other tool after this to get the
 * results.
 *
 * @param {string} projectId [REQUIRED] The GCP Project ID where the investigation resides.
 * @param {string} investigationId [REQUIRED] The ID of the investigation to run.
 * @param {string} revisionId [REQUIRED] The specific revision ID to run.
 * @returns {string} A detailed troubleshooting report in a structured string format. The
 *           report is organized with '##' headers for sections like 'Issue',
 *           'Hypotheses', 'Relevant Observations', and 'Remediation'.
 *           **Note:** Some sections may be empty and will state "No hypotheses
 *           found." or similar. Your job is to parse this report and present
 *           a clear summary of the findings (or lack thereof) to the user.
 */`,
        {
            projectId: z.string().describe('The Google Cloud Project ID.'),
            investigationId: z.string().describe('The ID of the investigation to run.'),
            revisionId: z.string().describe('The revision ID of the investigation to run.'),
        },
        async ({
            projectId,
            investigationId,
            revisionId
        }) => {
            const client = new GeminiCloudAssistClient();

            try {
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
            } catch (error) {
                if (error.name === 'ApiError') {
                    return {
                        content: [{
                            type: 'tool-error',
                            code: error.code,
                            message: error.message,
                            details: error.details
                        }]
                    };
                }
                // Fallback for generic errors
                return {
                    content: [{
                        type: 'tool-error',
                        code: 'UNEXPECTED_ERROR',
                        message: error.message
                    }]
                };
            }
        },
        {
            'mcp:tool-class': 'idempotent'
        }
    );

    server.tool(
        'add_observation',
        `/**
 * Adds a new user observation to an existing investigation.
 *
 * **Prerequisites: Argument Resolution**
 * Before calling this tool, you **MUST** resolve any new resource names
 * mentioned in the user's observation.
 * - **Resource URIs ('relevant_resources')**: If the user's 'observation'
 *   mentions new resources, convert their vague names into full resource URIs
 *   using 'gcloud', 'kubectl', or 'Memorybank'. If no new resources are
 *   mentioned, provide an empty list '[]'.
 * **If you cannot resolve a resource name, you MUST ask the user for
 * clarification before proceeding.**
 *
 * **Workflow:** After adding an observation, you **MUST** call
 * 'run_investigation'
 * on the new revision to re-analyze with the added context.
 *
 * @param {string} projectId [REQUIRED] The GCP Project ID where the investigation resides.
 * @param {string} investigationId [REQUIRED] The ID of the investigation.
 * @param {string} observation [REQUIRED] The new information or question from the user.
 * @param {Array<string>} relevant_resources [REQUIRED] A list of fully-resolved resource URIs for any new resources mentioned in the observation.
 * @returns {string} A string summary of the updated investigation, structured with markdown.
 *           You **MUST** parse this output to find the '**Revision Path**' field.
 *           The final segment of this path is the new 'revision_id' that you must
 *           use for the subsequent 'run_investigation' call.
 */`,
        {
            projectId: z.string().describe('The Google Cloud Project ID.'),
            investigationId: z.string().describe('The ID of the investigation.'),
            observation: z.string().describe('The new information or question from the user.'),
            relevant_resources: z.array(z.string()).describe('A list of fully-resolved resource URIs for any new resources mentioned in the observation.'),
        },
        async ({ projectId, investigationId, observation, relevant_resources }) => {
            const client = new GeminiCloudAssistClient();
            try {
                const result = await client.addObservation({
                    projectId,
                    investigationId,
                    observation,
                    relevant_resources,
                });
                const viewer = new InvestigationViewer(result);
                const formattedOutput = viewer.render();
                return {
                    content: [{
                        type: 'text',
                        text: formattedOutput
                    }]
                };
            } catch (error) {
                if (error.name === 'ApiError') {
                    return {
                        content: [{
                            type: 'tool-error',
                            code: error.code,
                            message: error.message,
                            details: error.details
                        }]
                    };
                }
                // Fallback for generic errors
                return {
                    content: [{
                        type: 'tool-error',
                        code: 'UNEXPECTED_ERROR',
                        message: error.message
                    }]
                };
            }
        }
    );
};

