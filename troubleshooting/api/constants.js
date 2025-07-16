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

// Constants for the polling mechanism in runInvestigation
export const INITIAL_BACKOFF_SECONDS = 1;
export const MAX_BACKOFF_SECONDS = 32;
export const BACKOFF_FACTOR = 2;
export const MAX_POLLING_ATTEMPTS = 20;

// URL for the Gemini Cloud Assist API discovery document
export const DISCOVERY_API_URL = 'https://geminicloudassist.googleapis.com/$discovery/rest?version=v1alpha';

// Observation IDs for User Input & User Project.
export const PRIMARY_USER_OBSERVATION_ID = "user.input.text"
export const PROJECT_OBSERVATION_ID = "user.project"
