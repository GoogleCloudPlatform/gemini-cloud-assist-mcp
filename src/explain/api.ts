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
    ApiError
} from '../shared/errors.js';
import {
    BaseClient
} from '../shared/base_client.js';

export interface RetrieveResourceParams {
    request: string;
}

interface TaskCompletionMessage {
    content: string;
    author: string;
}

interface TaskCompletionOutput {
    messages: TaskCompletionMessage[];
}

interface TaskCompletionResponse {
    output: TaskCompletionOutput;
}

export class CloudAiCompanionClient extends BaseClient {
    async retrieveResource(params: RetrieveResourceParams): Promise<any> {
        const {
            request
        } = params;
        try {
            const client = await this.auth.getClient();
            const projectId = await this.auth.getProjectId();

            const apiRequest = {
                input: {
                    messages: [{
                        content: request,
                        author: "user"
                    }]
                },
                experienceContext: {
                    experience: "/cloud-assist/chat",
                    agent: "planandact"
                },
                inputDataContext: {
                    additionalContext: {
                        "@type": "type.googleapis.com/google.cloud.cloudaicompanion.v1main.ChatInputDataContext",
                        sourceUri: "mcp",
                        projectId: projectId
                    }
                }
            };

            await this._writeLog('retrieveResource', 'input', apiRequest);
            const url = `https://cloudaicompanion.googleapis.com/v1/projects/${projectId}/locations/global/instances/default:completeTask`;
            const res = await client.request({
                url,
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(apiRequest),
            })
            await this._writeLog('retrieveResource', 'output', res.data);

            return (res.data as TaskCompletionResponse).output.messages[0].content;

        } catch (error: any) {
            this.logger.error('Error retrieving resource: ', error.message);
            if (error instanceof ApiError) {
                throw error;
            }
            const details = error.response ? error.response.data : 'No details available.';
            throw new ApiError(`Error retrieving resource: ${error.message}`, 500, details);
        }
    }
}
