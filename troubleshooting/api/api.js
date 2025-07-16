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

import {
    google
} from 'googleapis';
import {
    GoogleAuth
} from 'google-auth-library';
import fs from 'fs';
import path from 'path';
import {
    fileURLToPath
} from 'url';
import {
    InvestigationViewer,
    getInvestigationLink
} from '../formatting_utils.js';
import {
    ApiError
} from './errors.js';
import {
    getRevisionWithNewObservation,
    InvestigationPath
} from './utils.js';
import {
    DISCOVERY_API_URL,
    INITIAL_BACKOFF_SECONDS,
    MAX_BACKOFF_SECONDS,
    BACKOFF_FACTOR,
    MAX_POLLING_ATTEMPTS
} from './constants.js';
import packageJson from '../../package.json' with { type: 'json' };

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const userAgent = `gemini-cloud-assist-mcp/${packageJson.version}`;

export class GeminiCloudAssistClient {
    constructor(options = {}) {
        const {
            logger = null,
            enableDebugLogging = false,
        } = options;

        this.logger = logger || {
            info: () => { },
            error: () => { },
            warn: () => { },
            debug: () => { }
        };

        this.auth = this._initAuth(userAgent);
        this.geminiassist = null;
        this.enableDebugLogging = enableDebugLogging;
    }

    _initAuth(userAgent) {
        const authOptions = {
            scopes: 'https://www.googleapis.com/auth/cloud-platform',
            clientOptions: {
                headers: {
                    'User-Agent': userAgent,
                },
            }
        };

        this.logger.info('Authenticating with Application Default Credentials (ADC).');
        return new GoogleAuth(authOptions);
    }

    async _discoverApi() {
        if (this.geminiassist) return;
        let discoveryOptions = {
            url: DISCOVERY_API_URL
        }
        try {
            this.geminiassist = await google.discoverAPI(discoveryOptions);
        } catch (error) {
            this.logger.error('Error discovering Gemini Cloud Assist API:', error.message);
            throw new ApiError(`Failed to discover API. ${error.message}`, 'API_DISCOVERY_FAILED');
        }
    }

    async _writeLog(methodName, type, data) {
        if (!this.enableDebugLogging) {
            return;
        }
        const dir = path.join(__dirname, '..', 'samples');
        try {
            await fs.promises.mkdir(dir, {
                recursive: true
            });
            const filePath = path.join(dir, `${methodName}_${type}.json`);

            const dataForLog = {
                ...data
            };
            if (dataForLog.auth) {
                delete dataForLog.auth;
            }

            await fs.promises.writeFile(filePath, JSON.stringify(dataForLog, null, 2));
        } catch (error) {
            this.logger.error(`Failed to write log for ${methodName}:`, error);
        }
    }

    /**
     * Fetches Gemini Cloud Assist troubleshooting investigations.
     *
     * This function serves as a versatile entry point for retrieving investigation data.
     * It can operate in two modes:
     *
     * 1.  **List Mode:** If only a `projectId` is provided, it will list all
     *     troubleshooting investigations associated with that project. It can be
     *     optionally filtered by title using the `filter_expression` parameter.
     *
     * 2.  **Get Mode:** If an `investigationId` is provided, it will fetch the
     *     detailed report for that specific investigation. If a `revisionId` is
     *     also provided, it fetches that particular revision; otherwise, it
     *     retrieves the latest version.
     *
     * The function handles constructing the correct API request based on the
     * presence of `investigationId` and `revisionId`.
     *
     * @param {object} params The parameters for fetching investigations.
     * @param {string} params.projectId The Google Cloud Project ID.
     * @param {string} [params.investigationId] Optional. The ID of a specific
     *   investigation to fetch. If omitted, the function will list all
     *   investigations for the project.
     * @param {string} [params.revisionId] Optional. The revision ID of a specific
     *   investigation to fetch. Requires `investigationId` to be set.
     * @param {string} [params.filter_expression] Optional. A string to filter
     *   investigations by title. The filter format is `title:"<your_title>"`.
     * @returns {Promise<string>} A promise that resolves to a formatted string
     *   containing either the list of investigations or the details of a
     *   single investigation. In case of an error, it returns a formatted
     *   error message.
     */
    async fetchInvestigation({
        projectId,
        investigationId,
        revisionId,
        filter_expression
    }) {
        if (revisionId && !investigationId) {
            return Promise.reject(new ApiError("revisionId cannot be provided without investigationId.", 'INVALID_ARGUMENT'));
        }

        await this._discoverApi();

        if (investigationId) {
            return this.getInvestigation({
                projectId,
                investigationId,
                revisionId
            });
        } else {
            return this._listInvestigations({
                projectId,
                filter: filter_expression
            });
        }
    }

    /**
     * Lists all Gemini Cloud Assist troubleshooting investigations for a given project.
     * (Internal use, called by fetchInvestigation)
     * @param {string} projectId The Google Cloud Project ID.
     * @param {string} [filter=""] Optional. A filter expression to apply to the results.
     * @returns {Promise<string>} A formatted string of investigations or an error message.
     */
    async _listInvestigations({
        projectId,
        filter = ""
    }) {
        await this._discoverApi();
        const path = new InvestigationPath(projectId);

        try {
            const request = {
                parent: path.getParent(),
                auth: this.auth,
                filter: filter,
                pageSize: 20,
                fields: 'investigations(name,title,executionState),nextPageToken',
            };

            await this._writeLog('_listInvestigations', 'input', request);
            const res = await this.geminiassist.projects.locations.investigations.list(request);
            await this._writeLog('_listInvestigations', 'output', res.data);

            const investigations = res.data.investigations;
            if (!investigations || investigations.length === 0) {
                return "No investigations found.";
            }

            let formattedOutput = investigations.map(inv => {
                const invPath = InvestigationPath.fromInvestigationName(inv.name);
                const invId = invPath ? invPath.getInvestigationId() : 'N/A';
                const link = getInvestigationLink(projectId, invId);
                return `Investigation ID: ${invId}\nTitle: ${inv.title}\nState: ${inv.executionState}\nLink: ${link}`;
            }).join('\n\n');

            if (res.data.nextPageToken) {
                formattedOutput += `\n\nMore investigations available. Use the page_token parameter to view the next page: "${res.data.nextPageToken}"`;
            }

            return formattedOutput;

        } catch (error) {
            this.logger.error('Error fetching investigations:', error.message);
            // Assuming a similar error formatting as the Python version
            const details = error.response ? error.response.data : 'No details available.';
            throw new ApiError(`Error listing investigations: ${error.message}`, 'LIST_FAILED', details);
        }
    }

    /**
     * Creates a new troubleshooting investigation.
     *
     * @param {string} projectId The Google Cloud Project ID.
     * @param {object} investigation The investigation object to create.
     * @returns {Promise<object>} The created investigation object.
     */
    async createInvestigation(projectId, investigation) {
        await this._discoverApi();
        const path = new InvestigationPath(projectId);

        try {
            // Deep copy to avoid side effects
            const investigationForRequest = JSON.parse(JSON.stringify(investigation));

            // Convert deprecated timeRanges to timeIntervals for backward compatibility
            if (investigationForRequest.observations) {
                for (const key in investigationForRequest.observations) {
                    if (Object.prototype.hasOwnProperty.call(investigationForRequest.observations, key)) {
                        const obs = investigationForRequest.observations[key];
                        if (obs.timeRanges && !obs.timeIntervals) {
                            this.logger.warn(`Found deprecated 'timeRanges' in observation '${key}', converting to 'timeIntervals'.`);
                            obs.timeIntervals = obs.timeRanges;
                            delete obs.timeRanges;
                        }
                    }
                }
            }

            const request = {
                parent: path.getParent(),
                auth: this.auth,
                requestBody: investigationForRequest,
            };

            await this._writeLog('createInvestigation', 'input', request);
            const res = await this.geminiassist.projects.locations.investigations.create(request);
            await this._writeLog('createInvestigation', 'output', res.data);
            return res.data;
        } catch (error) {
            this.logger.error('Error creating investigation:', error.message);
            const details = error.response ? error.response.data : 'No details available.';
            throw new ApiError(`Error creating investigation: ${error.message}`, 'CREATE_FAILED', details);
        }
    }

    /**
     * Runs a troubleshooting investigation, which is a long-running operation (LRO).
     * This method initiates the investigation and then polls the resulting operation
     * until it is complete.
     *
     * @param {object} params The parameters for running an investigation.
     * @param {string} params.projectId The Google Cloud Project ID.
     * @param {string} params.investigationId The ID of the investigation to run.
     * @param {string} params.revisionId The revision ID of the investigation to run.
     * @returns {Promise<object>} The final, completed investigation object.
     */
    async runInvestigation({
        projectId,
        investigationId,
        revisionId
    }) {
        await this._discoverApi();

        const path = new InvestigationPath(projectId, investigationId, revisionId);

        try {
            const request = {
                name: path.getRevisionName(),
                auth: this.auth,
            };

            await this._writeLog('runInvestigation_run', 'input', request);
            const runResponse = await this.geminiassist.projects.locations.investigations.revisions.run(request);
            await this._writeLog('runInvestigation_run', 'output', runResponse.data);

            const operationName = runResponse.data.name;

            let attempt = 0;
            let backoffSeconds = INITIAL_BACKOFF_SECONDS;


            while (attempt < MAX_POLLING_ATTEMPTS) {
                attempt++;

                const jitter = Math.random();
                const delaySeconds = Math.min(backoffSeconds, MAX_BACKOFF_SECONDS) + jitter;

                await new Promise(resolve => setTimeout(resolve, delaySeconds * 1000));

                const opRequest = {
                    name: operationName,
                    auth: this.auth,
                };

                await this._writeLog(`runInvestigation_poll_op_attempt_${attempt}`, 'input', opRequest);
                const opRes = await this.geminiassist.projects.locations.operations.get(opRequest);
                await this._writeLog(`runInvestigation_poll_op_attempt_${attempt}`, 'output', opRes.data);

                if (opRes.data.done) {
                    if (opRes.data.error) {
                        throw new ApiError('Investigation operation failed', 'OPERATION_ERROR', opRes.data.error);
                    }
                    // The operation is complete, but the response field may not contain the
                    // full investigation details. Fetch the investigation explicitly to ensure
                    // we have the complete, final object.
                    return this._getInvestigationRaw({
                        projectId,
                        investigationId,
                        revisionId
                    });
                }
                backoffSeconds *= BACKOFF_FACTOR;
            }

            const investigationData = await this._getInvestigationRaw({
                projectId,
                investigationId
            });
            throw new ApiError('Investigation did not complete within the timeout period.', 'TIMEOUT_ERROR', {
                currentStatus: investigationData
            });

        } catch (error) {
            this.logger.error('Error running investigation:', error.message);
            if (error instanceof ApiError) {
                throw error;
            }
            const details = error.response ? error.response.data : 'No details available.';
            throw new ApiError(`Error running investigation: ${error.message}`, 'RUN_FAILED', details);
        }
    }

    /**
     * Gets the raw investigation object from the API.
     *
     * @param {object} params The parameters for getting an investigation.
     * @param {string} params.projectId The Google Cloud Project ID.
     * @param {string} params.investigationId The ID of the investigation to get.
     * @param {string} [params.revisionId] Optional. The revision ID of the investigation to get.
     * @param {string} [logSuffix=''] Optional suffix for the log file name.
     * @returns {Promise<object>} The raw investigation object.
     */
    async _getInvestigationRaw({
        projectId,
        investigationId,
        revisionId
    }, logSuffix = '') {
        await this._discoverApi();
        const path = new InvestigationPath(projectId, investigationId, revisionId);
        const investigationName = revisionId ? path.getRevisionName() : path.getInvestigationName();

        try {
            const request = {
                name: investigationName,
                auth: this.auth,
            };
            await this._writeLog(`_getInvestigationRaw${logSuffix}`, 'input', request);
            const res = await this.geminiassist.projects.locations.investigations.get(request);
            await this._writeLog(`_getInvestigationRaw${logSuffix}`, 'output', res.data);
            return res.data;
        } catch (error) {
            this.logger.error(`Error getting raw investigation '${investigationName}':`, error.message);
            const details = error.response ? error.response.data : 'No details available.';
            throw new ApiError(`Error getting raw investigation: ${error.message}`, 'GET_FAILED', details);
        }
    }

    /**
     * Gets a troubleshooting investigation and formats it for display.
     *
     * @param {object} params The parameters for getting an investigation.
     * @param {string} params.projectId The Google Cloud Project ID.
     * @param {string} params.investigationId The ID of the investigation to get.
     * @param {string} [params.revisionId] Optional. The revision ID of the investigation to get.
     * @returns {Promise<string>} A formatted string representing the investigation.
     */
    async getInvestigation({
        projectId,
        investigationId,
        revisionId
    }) {
        try {
            const rawInvestigation = await this._getInvestigationRaw({
                projectId,
                investigationId,
                revisionId
            }, 'getInvestigation');
            const viewer = new InvestigationViewer(rawInvestigation);
            return viewer.render();
        } catch (error) {
            this.logger.error('Error getting investigation:', error.message);
            // The error from _getInvestigationRaw is already detailed.
            // We re-throw it to ensure the caller gets a proper Promise rejection.
            throw error;
        }
    }

    /**
     * Adds a new user observation to an existing investigation, creating a new revision.
     *
     * This method fetches the latest revision of an investigation and appends the
     * new user-provided observation and resources to the primary user observation
     * entry. It then creates a new revision with this updated payload.
     *
     * @param {object} params The parameters for adding an observation.
     * @param {string} params.projectId The Google Cloud Project ID.
     * @param {string} params.investigationId The ID of the investigation.
     * @param {string} params.observation The new information or question from the user.
     * @param {string[]} params.relevant_resources A list of fully-resolved resource URIs.
     * @returns {Promise<object>} A promise that resolves to the raw API response
     *   for the newly created investigation revision.
     */
    async addObservation({
        projectId,
        investigationId,
        observation,
        relevant_resources
    }) {
        await this._discoverApi();

        try {
            const latestRevision = await this._getInvestigationRaw({
                projectId,
                investigationId
            });

            const newRevisionPayload = getRevisionWithNewObservation(latestRevision, observation, relevant_resources);

            if (!newRevisionPayload) {
                throw new ApiError("Failed to create new revision payload.", 'PAYLOAD_CREATION_FAILED');
            }

            const path = new InvestigationPath(projectId, investigationId);
            const request = {
                parent: path.getInvestigationName(),
                auth: this.auth,
                requestBody: newRevisionPayload,
            };

            await this._writeLog('addObservation', 'input', request);
            const res = await this.geminiassist.projects.locations.investigations.revisions.create(request);
            await this._writeLog('addObservation', 'output', res.data);

            return res.data;

        } catch (error) {
            this.logger.error('Error adding observation:', error.message);
            if (error instanceof ApiError) {
                throw error;
            }
            const details = error.response ? error.response.data : 'No details available.';
            throw new ApiError(`Error adding an observation to investigation: ${error.message}`, 'ADD_OBSERVATION_FAILED', details);
        }
    }
}