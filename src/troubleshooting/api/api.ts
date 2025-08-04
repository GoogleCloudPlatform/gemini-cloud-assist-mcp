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
    InvestigationViewer,
    getInvestigationLink
} from '../formatting_utils.js';
import {
    ApiError
} from '../../shared/errors.js';
import {
    getRevisionWithNewObservation,
    InvestigationPath,
    InvestigationPayload
} from './utils.js';
import {
    DISCOVERY_API_URL,
    INITIAL_BACKOFF_SECONDS,
    MAX_BACKOFF_SECONDS,
    BACKOFF_FACTOR,
    MAX_POLLING_ATTEMPTS
} from './constants.js';
import {
    AddObservationParams,
    FetchInvestigationParams,
    GetInvestigationParams,
    ListInvestigationsParams,
    RunInvestigationParams
} from './types.js';
import {
    BaseClient
} from '../../shared/base_client.js';
import {
    BaseClientOptions
} from '../../shared/types.js';

export class GeminiCloudAssistClient extends BaseClient {
    private geminiassist: any;
    private isInitialized: boolean;
    private licenseValidated: boolean;

    constructor(options: BaseClientOptions = {}) {
        super(options);
        this.isInitialized = false;
        this.licenseValidated = false;
        this.geminiassist = null;
    }

    protected _initAuth() {
        return super._initAuth();
    }

    private async _ensureReady({
        requireLicense = false
    }: {
        requireLicense?: boolean
    }): Promise < void > {
        if (this.isInitialized) {
            if (requireLicense) {
                await this._validateLicense();
            }
            return;
        }

        try {
            await this._validateAuth();
            await this._discoverApi();
            this.isInitialized = true;

            if (requireLicense) {
                await this._validateLicense();
            }
        } catch (error) {
            this.isInitialized = false;
            throw error;
        }
    }

    private async _validateAuth(): Promise<void> {
        try {
            await this.auth.getAccessToken();
            this.logger.error('Authentication successful.'); // Info Logs can corrupt JSON Payloads from Tool Call Response.
        } catch (error: any) {
            this.logger.error('Authentication failed:', error.message);
            throw new ApiError(`Authentication failed. Please check your Application Default Credentials. Try running 'gcloud auth application-default login'. ${error.message}`, 401, 'AUTH_FAILED');
        }
    }

    private async _validateLicense(): Promise<void> {
        if (this.licenseValidated) {
            return;
        }
        this.logger.error('Placeholder: License validation check would occur here.');
        this.licenseValidated = true;
    }

    private async _discoverApi(): Promise<void> {
        try {
            this.geminiassist = await google.discoverAPI(DISCOVERY_API_URL);
        } catch (error: any) {
            this.logger.error('Error discovering Gemini Cloud Assist API:', error.message);
            throw new ApiError(`Failed to discover API. ${error.message}`, 500, 'API_DISCOVERY_FAILED');
        }
    }

    async fetchInvestigation(params: FetchInvestigationParams): Promise<string> {
        await this._ensureReady({
            requireLicense: true
        });
        const {
            projectId,
            investigationId,
            revisionId,
            filter_expression
        } = params;
        if (revisionId && !investigationId) {
            return Promise.reject(new ApiError("revisionId cannot be provided without investigationId.", 400, 'INVALID_ARGUMENT'));
        }

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

    private async _listInvestigations(params: ListInvestigationsParams): Promise<string> {
        const {
            projectId,
            filter = ""
        } = params;
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

            let formattedOutput = investigations.map((inv: any) => {
                const invPath = InvestigationPath.fromInvestigationName(inv.name);
                const invId = invPath ? invPath.getInvestigationId() : 'N/A';
                const link = getInvestigationLink(projectId, invId || '');
                return `Investigation ID: ${invId}\nTitle: ${inv.title}\nState: ${inv.executionState}\nLink: ${link}`;
            }).join('\n\n');

            if (res.data.nextPageToken) {
                formattedOutput += `\n\nMore investigations available. Use the page_token parameter to view the next page: "${res.data.nextPageToken}"`;
            }

            return formattedOutput;

        } catch (error: any) {
            this.logger.error('Error fetching investigations:', error.message);
            const details = error.response ? error.response.data : 'No details available.';
            throw new ApiError(`Error listing investigations: ${error.message}`, 500, details);
        }
    }

    async createInvestigation(projectId: string, investigation: InvestigationPayload): Promise<any> {
        await this._ensureReady({
            requireLicense: true
        });
        const path = new InvestigationPath(projectId);

        try {
            const investigationForRequest = JSON.parse(JSON.stringify(investigation));

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
        } catch (error: any) {
            this.logger.error('Error creating investigation:', error.message);
            const details = error.response ? error.response.data : 'No details available.';
            throw new ApiError(`Error creating investigation: ${error.message}`, 500, details);
        }
    }


    async runInvestigation(params: RunInvestigationParams): Promise<any> {
        await this._ensureReady({ requireLicense: true });
        const {
            projectId,
            investigationId,
            revisionId
        } = params;
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
                        throw new ApiError('Investigation operation failed', 500, opRes.data.error);
                    }
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
            throw new ApiError('Investigation did not complete within the timeout period.', 504, {
                currentStatus: investigationData
            });

        } catch (error: any) {
            this.logger.error('Error running investigation:', error.message);
            if (error instanceof ApiError) {
                throw error;
            }
            const details = error.response ? error.response.data : 'No details available.';
            throw new ApiError(`Error running investigation: ${error.message}`, 500, details);
        }
    }

    private async _getInvestigationRaw(params: GetInvestigationParams, logSuffix = ''): Promise<any> {
        const {
            projectId,
            investigationId,
            revisionId
        } = params;
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
        } catch (error: any) {
            this.logger.error(`Error getting raw investigation '${investigationName}':`, error.message);
            const details = error.response ? error.response.data : 'No details available.';
            throw new ApiError(`Could not find Investigation ID: ${investigationId}`, 404, details);
        }
    }

    async getInvestigation(params: GetInvestigationParams): Promise<string> {
        await this._ensureReady({ requireLicense: true });
        try {
            const rawInvestigation = await this._getInvestigationRaw(params, 'getInvestigation');
            const viewer = new InvestigationViewer(rawInvestigation);
            return viewer.render();
        } catch (error: any) {
            this.logger.error('Error getting investigation:', error.message);
            throw error;
        }
    }

    async addObservation(params: AddObservationParams): Promise<any> {
        await this._ensureReady({ requireLicense: true });
        const {
            projectId,
            investigationId,
            observation,
            relevant_resources
        } = params;
        try {
            const latestRevision = await this._getInvestigationRaw({
                projectId,
                investigationId
            });

            const newRevisionPayload = getRevisionWithNewObservation(latestRevision, observation, relevant_resources);

            if (!newRevisionPayload) {
                throw new ApiError("Failed to create new revision payload.", 500, 'PAYLOAD_CREATION_FAILED');
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

        } catch (error: any) {
            this.logger.error('Error adding observation:', error.message);
            if (error instanceof ApiError) {
                throw error;
            }
            const details = error.response ? error.response.data : 'No details available.';
            throw new ApiError(`Error adding an observation to investigation: ${error.message}`, 500, details);
        }
    }
}
