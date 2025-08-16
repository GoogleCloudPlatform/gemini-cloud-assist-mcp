/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { ApiError } from '../shared/errors.js';
import { BaseClient } from '../shared/base_client.js';
import { RetrieveResourceToolInput } from './types.js';

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
  async retrieveResource(params: RetrieveResourceToolInput): Promise<string> {
    const { request } = params;
    try {
      const client = await this.auth.getClient();
      const projectId = await this.auth.getProjectId();

      const apiRequest = {
        input: {
          messages: [
            {
              content: request,
              author: 'user',
            },
          ],
        },
        experienceContext: {
          experience: '/cloud-assist/chat',
          agent: 'planandact',
        },
        inputDataContext: {
          additionalContext: {
            '@type':
              'type.googleapis.com/google.cloud.cloudaicompanion.v1main.ChatInputDataContext',
            sourceUri: 'mcp',
            projectId: projectId,
          },
        },
      };

      await this._writeLog('retrieveResource', 'input', apiRequest);
      const url = `https://cloudaicompanion.googleapis.com/v1/projects/${projectId}/locations/global/instances/default:completeTask`;
      const res = await client.request({
        url,
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(apiRequest),
      });
      await this._writeLog('retrieveResource', 'output', res.data);

      return (res.data as TaskCompletionResponse).output.messages[0].content;
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        throw error;
      }

      // For any other type of error, wrap it in a generic ApiError.
      throw new ApiError(
        'An unexpected error occurred while retrieving the resource.',
        500,
        error
      );
    }
  }
}
