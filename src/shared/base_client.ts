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

import fs from 'fs';
import path from 'path';
import {
    fileURLToPath
} from 'url';
import {
    BaseClientOptions,
    Logger
} from './types.js';
import packageJson from '../../package.json' with {
    type: 'json'
};
import {
    GoogleAuth
} from 'google-auth-library';

export const userAgent = `gemini-cloud-assist-mcp/${packageJson.version}`;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export class BaseClient {
    protected logger: Logger;
    protected enableDebugLogging: boolean;
    protected auth: GoogleAuth;

    constructor(options: BaseClientOptions = {}) {
        const {
            logger = console,
                enableDebugLogging = false,
        } = options;

        this.logger = logger;
        this.enableDebugLogging = enableDebugLogging;
        this.auth = this._initAuth();
    }

    protected _initAuth(): GoogleAuth {
        const authOptions = {
            scopes: 'https://www.googleapis.com/auth/cloud-platform',
        };

        this.logger.error('Authenticating with Application Default Credentials (ADC).');
        return new GoogleAuth(authOptions);
    }

    protected async _writeLog(methodName: string, type: string, data: any): Promise<void> {
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
}
