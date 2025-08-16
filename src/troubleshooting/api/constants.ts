/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

// Constants for the polling mechanism in runInvestigation
export const INITIAL_BACKOFF_SECONDS: number = 1;
export const MAX_BACKOFF_SECONDS: number = 32;
export const BACKOFF_FACTOR: number = 2;
export const MAX_POLLING_ATTEMPTS: number = 20;

// URL for the Gemini Cloud Assist API discovery document
export const DISCOVERY_API_URL: string =
  'https://geminicloudassist.googleapis.com/$discovery/rest?version=v1alpha';

// Observation IDs for User Input & User Project.
export const PRIMARY_USER_OBSERVATION_ID: string = 'user.input.text';
export const PROJECT_OBSERVATION_ID: string = 'user.project';
