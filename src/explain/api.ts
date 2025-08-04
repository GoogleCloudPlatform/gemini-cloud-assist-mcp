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
    GoogleAuth
} from 'google-auth-library';
import fs from 'fs';
import path from 'path';
import {
    fileURLToPath
} from 'url';
import {
    ApiError
} from '../troubleshooting/api/errors.js';
import packageJson from '../../package.json' with {
    type: 'json'
};

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const userAgent = `gemini-cloud-assist-mcp/${packageJson.version}`;

interface Logger {
    info(message: string, ...args: any[]): void;
    error(message: string, ...args: any[]): void;
    warn(message: string, ...args: any[]): void;
    debug(message: string, ...args: any[]): void;
}

interface CloudAiCompanionClientOptions {
    logger?: Logger;
    enableDebugLogging?: boolean;
}

export interface RetrieveResourceParams {
    content: string;
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

export class CloudAiCompanionClient {
    private logger: Logger;
    private auth: GoogleAuth;
    private enableDebugLogging: boolean;

    constructor(options: CloudAiCompanionClientOptions = {}) {
        const {
            logger = console,
                enableDebugLogging = false,
        } = options;

        this.logger = logger;
        this.enableDebugLogging = enableDebugLogging;
        this.auth = this._initAuth(userAgent);
    }

    private _initAuth(userAgent: string): GoogleAuth {
        const authOptions = {
            scopes: 'https://www.googleapis.com/auth/cloud-platform',
        };

        this.logger.error('Authenticating with Application Default Credentials (ADC).');
        return new GoogleAuth(authOptions);
    }

    private async _writeLog(methodName: string, type: string, data: any): Promise<void> {
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
        } catch (error: any) {
            this.logger.error(`Failed to write log for ${methodName}:`, error);
        }
    }

    async retrieveResource(params: RetrieveResourceParams): Promise<any> {
        const {
            content
        } = params;
        try {
            const client = await this.auth.getClient();
            const projectId = await this.auth.getProjectId();

            const request = {
                input: {
                    messages: [{
                        content: content,
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

            await this._writeLog('retrieveResource', 'input', request);
            const url = `https://cloudaicompanion.googleapis.com/v1/projects/${projectId}/locations/global/instances/default:completeTask`;
            const res = await client.request({
                url,
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(request),
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
