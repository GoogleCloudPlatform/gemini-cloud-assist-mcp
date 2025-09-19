/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { BaseClientOptions, Logger } from './types.js';
import packageJson from '../../package.json' with { type: 'json' };
import { GoogleAuth } from 'google-auth-library';

export const productName = 'gemini-cloud-assist-mcp';
export const productVersion = packageJson.version;
export const userAgent = `${productName}/${productVersion}`;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export class BaseClient {
  protected logger: Logger;
  protected enableDebugLogging: boolean;
  protected auth: GoogleAuth;

  constructor(options: BaseClientOptions = {}) {
    const { logger = console, enableDebugLogging = false } = options;

    this.logger = logger;
    this.enableDebugLogging = enableDebugLogging;
    this.auth = this._initAuth();
  }

  protected _initAuth(): GoogleAuth {
    const authOptions = {
      scopes: 'https://www.googleapis.com/auth/cloud-platform',
    };

    this.logger.error(
      'Authenticating with Application Default Credentials (ADC).'
    );
    return new GoogleAuth(authOptions);
  }

  protected async _writeLog(
    methodName: string,
    type: string,
    data: Record<string, unknown>
  ): Promise<void> {
    if (!this.enableDebugLogging) {
      return;
    }
    const dir = path.join(__dirname, '..', '..', 'raw_logs');
    try {
      await fs.promises.mkdir(dir, {
        recursive: true,
      });
      const filePath = path.join(dir, `${methodName}_${type}.json`);

      const dataForLog = {
        ...data,
      };
      if (dataForLog.auth) {
        delete dataForLog.auth;
      }

      await fs.promises.writeFile(
        filePath,
        JSON.stringify(dataForLog, null, 2)
      );
    } catch (error: unknown) {
      this.logger.warn('Failed to write log for', methodName, error);
    }
  }
}
