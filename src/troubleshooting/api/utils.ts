/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @fileoverview Utilities for creating and modifying investigation payloads for
 * the Gemini Cloud Assist API.
 */

import {
  PRIMARY_USER_OBSERVATION_ID,
  PROJECT_OBSERVATION_ID,
} from './constants.js';
import { Investigation, CreateInvestigationRequest } from './types.js';

/**
 * A utility class to manage the various formats of investigation resource names.
 *
 * GCP Resource Name Format:
 * `projects/{project}/locations/{location}/investigations/{investigation_id}/revisions/{revision_id}`
 */
export class InvestigationPath {
  projectId: string;
  investigationId?: string;
  revisionId?: string;
  location: string;

  /**
   * @param {string} projectId The Google Cloud Project ID.
   * @param {string} [investigationId] The ID of a specific investigation.
   * @param {string} [revisionId] The revision ID of a specific investigation.
   */
  constructor(
    projectId: string,
    investigationId?: string,
    revisionId?: string
  ) {
    if (!projectId) {
      throw new Error('A projectId is required.');
    }
    this.projectId = projectId;
    this.investigationId = investigationId;
    this.revisionId = revisionId;
    this.location = 'global'; // Assuming 'global' for now as it's hardcoded elsewhere.
  }

  /**
   * Creates an InvestigationPath instance from a full resource name string.
   * @param {string} resourceName The full GCP resource name.
   * @returns {InvestigationPath | null} A new instance of InvestigationPath or null if parsing fails.
   */
  static fromInvestigationName(resourceName: string): InvestigationPath | null {
    if (!resourceName) return null;

    const parts = resourceName.split('/');
    if (parts.length < 2 || parts[0] !== 'projects') {
      return null;
    }

    const projectId = parts[1];
    let investigationId: string | undefined = undefined;
    let revisionId: string | undefined = undefined;

    const investigationIndex = parts.indexOf('investigations');
    if (investigationIndex !== -1 && parts.length > investigationIndex + 1) {
      investigationId = parts[investigationIndex + 1];
    }

    const revisionIndex = parts.indexOf('revisions');
    if (revisionIndex !== -1 && parts.length > revisionIndex + 1) {
      revisionId = parts[revisionIndex + 1];
    }

    return new InvestigationPath(projectId, investigationId, revisionId);
  }

  /**
   * Returns the parent path for listing resources.
   * Format: `projects/{projectId}/locations/{location}`
   * @returns {string}
   */
  getParent(): string {
    return `projects/${this.projectId}/locations/${this.location}`;
  }

  /**
   * Returns the full investigation name.
   * Format: `projects/{projectId}/locations/{location}/investigations/{investigationId}`
   * @returns {string}
   */
  getInvestigationName(): string {
    if (!this.investigationId) {
      throw new Error('Investigation ID is not set.');
    }
    return `${this.getParent()}/investigations/${this.investigationId}`;
  }

  /**
   * Returns the full revision name.
   * Format: `projects/{projectId}/locations/{location}/investigations/{investigationId}/revisions/{revisionId}`
   * @returns {string}
   */
  getRevisionName(): string {
    if (!this.investigationId || !this.revisionId) {
      throw new Error('Investigation ID and/or Revision ID are not set.');
    }
    return `${this.getInvestigationName()}/revisions/${this.revisionId}`;
  }

  /**
   * Returns the project ID.
   * @returns {string}
   */
  getProjectId(): string {
    return this.projectId;
  }

  /**
   * Returns the investigation ID.
   * @returns {string | undefined}
   */
  getInvestigationId(): string | undefined {
    return this.investigationId;
  }
}

/**
 * Creates the initial investigation object for the `create_investigation` tool.
 *
 * @param {string} title The title of the investigation.
 * @param {string} projectId The Google Cloud Project ID.
 * @param {string} issue_description A description of the issue.
 * @param {string[]} relevant_resources A list of relevant resources.
 * @param {string} start_time The start time of the issue in RFC3339 UTC "Zulu" format.
 * @returns {object} The investigation object payload for the API.
 */
export function createInitialInvestigationRequestBody(
  title: string,
  projectId: string,
  issue_description: string,
  relevant_resources: string[],
  start_time: string
): CreateInvestigationRequest {
  return {
    title: title,
    dataVersion: '2',
    observations: {
      [PROJECT_OBSERVATION_ID]: {
        id: PROJECT_OBSERVATION_ID,
        observerType: 'OBSERVER_TYPE_USER',
        observationType: 'OBSERVATION_TYPE_STRUCTURED_INPUT',
        text: projectId,
      },
      [PRIMARY_USER_OBSERVATION_ID]: {
        id: PRIMARY_USER_OBSERVATION_ID,
        observerType: 'OBSERVER_TYPE_USER',
        observationType: 'OBSERVATION_TYPE_TEXT_DESCRIPTION',
        text: issue_description,
        relevantResources: relevant_resources,
        timeIntervals: [
          {
            startTime: start_time,
          },
        ],
      },
    },
  };
}

/**
 * Validates a list of strings to ensure they are syntactically correct GCP resource URIs.
 *
 * @param {string[]} resources - The list of resource strings to validate.
 * @returns {string[]} - A list of the invalid resource strings. If all are valid, the list is empty.
 */
export function validateGcpResources(resources: string[]): string[] {
  const invalidResources: string[] = [];
  const gcpResourceRegex =
    /^\/\/(?!www\.)[a-zA-Z0-9-.]+\.googleapis\.com\/((projects|folders|organizations)\/[a-zA-Z0-9-_.]+(\/(.+))?|\S+)$/;

  for (const resource of resources) {
    if (typeof resource !== 'string' || !gcpResourceRegex.test(resource)) {
      invalidResources.push(resource);
    }
  }
  return invalidResources;
}

/**
 * Creates a new revision payload from an existing investigation by adding a new
 * user observation.
 *
 * This function takes the latest revision of an investigation and appends the new
 * observation text to the primary user observation entry. It also merges any new
 * relevant resources into the same entry. This approach maintains a running log
 * of user interactions within a single observation block.
 *
 * The function performs the following steps:
 * 1. Creates a deep copy of the incoming payload to avoid side effects.
 * 2. Prunes all non-user-generated observations from the previous revision.
 * 3. Ensures a primary user observation entry exists, creating one if necessary.
 * 4. Appends the new `observationText` to the existing text in the primary
 *    observation, separated by a newline.
 * 5. Merges the `relevantResources` into the primary observation, avoiding
 *    duplicates.
 * 6. Wraps the modified payload in a `snapshot` object, as required by the
 *    `revisions.create` API method.
 *
 * @param {object} payload The existing investigation payload (latest revision).
 * @param {string} observationText The new information or question from the user.
 * @param {string[]} relevantResources A list of fully-resolved resource URIs
 *   related to the new observation.
 * @returns {object | null} The payload for the `revisions.create` API call,
 *   or null if the input payload is invalid.
 */
export function getRevisionWithNewObservation(
  payload: Investigation | null,
  observationText: string,
  relevantResources: string[]
): { snapshot: Investigation } | null {
  if (!payload) {
    return null;
  }

  const newPayload: Investigation = JSON.parse(JSON.stringify(payload));

  if (!newPayload.observations) {
    newPayload.observations = {};
  }
  const { observations } = newPayload;

  // Prune all non-user observations.
  for (const key in observations) {
    if (observations[key].observerType !== 'OBSERVER_TYPE_USER') {
      delete observations[key];
    }
  }

  if (!observations[PRIMARY_USER_OBSERVATION_ID]) {
    observations[PRIMARY_USER_OBSERVATION_ID] = {
      id: PRIMARY_USER_OBSERVATION_ID,
      observerType: 'OBSERVER_TYPE_USER',
      observationType: 'OBSERVATION_TYPE_TEXT_DESCRIPTION',
      text: '', // Start with empty text
      relevantResources: [],
    };
  }

  const primaryObs = observations[PRIMARY_USER_OBSERVATION_ID];
  if (primaryObs.text) {
    primaryObs.text += '\n\n';
  }
  primaryObs.text += `[User Observation]: ${observationText}`;

  const existingResources = primaryObs.relevantResources || [];
  for (const resource of relevantResources) {
    if (!existingResources.includes(resource)) {
      existingResources.push(resource);
    }
  }
  primaryObs.relevantResources = existingResources;

  // The API expects the modified payload to be wrapped in a "snapshot" field.
  return { snapshot: newPayload };
}
