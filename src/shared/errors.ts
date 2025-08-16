/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { CallToolResult } from '@modelcontextprotocol/sdk/types.js';
export class ApiError extends Error {
  code: number;
  details: unknown;
  constructor(message: string, code: number, details: unknown) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.details = details;
  }
  toToolResult(): CallToolResult {
    return {
      content: [
        {
          type: 'text',
          text: `Error Message: ${this.message}\nDetails: ${this.details} (error_code: ${this.code})`,
        },
      ],
    };
  }
}
