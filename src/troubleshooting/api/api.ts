/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { google } from 'googleapis';
import {
  InvestigationViewer,
  getInvestigationLink,
} from '../formatting_utils.js';
import { ApiError } from '../../shared/errors.js';
import {
  createInitialInvestigationRequestBody,
  getRevisionWithNewObservation,
  InvestigationPath,
} from './utils.js';
import {
  DISCOVERY_API_URL,
  INITIAL_BACKOFF_SECONDS,
  MAX_BACKOFF_SECONDS,
  BACKOFF_FACTOR,
  MAX_POLLING_ATTEMPTS,
} from './constants.js';
import {
  AddObservationToolInput,
  CreateInvestigationApiRequest,
  GetOperationApiRequest,
  FetchInvestigationToolInput,
  GetInvestigationApiRequest,
  GetInvestigationParams,
  ListInvestigationsApiRequest,
  ListInvestigationsParams,
  RunInvestigationApiRequest,
  RunInvestigationToolInput,
  Investigation,
  CreateInvestigationRequest,
  CreateInvestigationToolInput,
} from './types.js';
import {
  BaseClient,
  productName,
  productVersion,
} from '../../shared/base_client.js';
import { BaseClientOptions } from '../../shared/types.js';

export class GeminiCloudAssistClient extends BaseClient {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private geminicloudassist: any;
  private isInitialized: boolean;
  private licenseValidated: boolean;

  constructor(options: BaseClientOptions = {}) {
    super(options);
    this.isInitialized = false;
    this.licenseValidated = false;
    this.geminicloudassist = null;

    google.options({
      userAgentDirectives: [
        {
          product: productName,
          version: productVersion,
        },
      ],
    });
  }

  private async _ensureReady({
    requireLicense = false,
  }: {
    requireLicense?: boolean;
  }): Promise<void> {
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
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError(
        'An unexpected error occurred during authentication. Have you run `gcloud auth application-default login`?',
        401,
        error
      );
    }
  }

  private async _validateLicense(): Promise<void> {
    if (this.licenseValidated) {
      return;
    }
    this.licenseValidated = true;
  }

  private async _discoverApi(): Promise<void> {
    try {
      this.geminicloudassist = await google.discoverAPI(DISCOVERY_API_URL);
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError(
        'An unexpected error occurred while discovering the API.',
        500,
        error
      );
    }
  }

  private async _getInvestigationRaw(
    params: GetInvestigationParams,
    logSuffix = ''
  ): Promise<Investigation> {
    const { projectId, investigationId, revisionId } = params;
    const path = new InvestigationPath(projectId, investigationId, revisionId);
    const investigationName = revisionId
      ? path.getRevisionName()
      : path.getInvestigationName();

    try {
      const request: GetInvestigationApiRequest = {
        name: investigationName,
        auth: this.auth,
      };
      await this._writeLog(`_getInvestigationRaw${logSuffix}`, 'input', {
        ...request,
      });
      const res =
        await this.geminicloudassist.projects.locations.investigations.get(
          request
        );
      await this._writeLog(`_getInvestigationRaw${logSuffix}`, 'output', {
        ...res.data,
      });
      return res.data;
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError(
        `Could not find Investigation ID: ${investigationId}'`,
        404,
        error
      );
    }
  }

  async _getInvestigation(params: GetInvestigationParams): Promise<string> {
    await this._ensureReady({ requireLicense: true });
    try {
      const rawInvestigation = await this._getInvestigationRaw(
        params,
        'getInvestigation'
      );
      const viewer = new InvestigationViewer(rawInvestigation);
      return viewer.render();
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError('Error getting investigation.', 500, error);
    }
  }

  private async _listInvestigations(
    params: ListInvestigationsParams
  ): Promise<string> {
    const { projectId, filter = '', page_token } = params;
    const path = new InvestigationPath(projectId);

    try {
      const request: ListInvestigationsApiRequest = {
        parent: path.getParent(),
        auth: this.auth,
        filter: filter,
        pageSize: 20,
        fields: 'investigations(name,title,executionState),nextPageToken',
      };

      if (page_token) {
        request.pageToken = page_token;
      }

      await this._writeLog('_listInvestigations', 'input', { ...request });
      const res =
        await this.geminicloudassist.projects.locations.investigations.list(
          request
        );
      await this._writeLog('_listInvestigations', 'output', { ...res.data });

      const investigations = res.data.investigations;
      if (!investigations || investigations.length === 0) {
        return 'No investigations found.';
      }

      let formattedOutput = investigations
        .map((inv: Investigation) => {
          const invPath = InvestigationPath.fromInvestigationName(
            inv.name || ''
          );
          const invId = invPath ? invPath.getInvestigationId() : 'N/A';
          const link = getInvestigationLink(projectId, invId || '');
          return `Investigation ID: ${invId}\nTitle: ${inv.title}\nState: ${inv.executionState}\nLink: ${link}`;
        })
        .join('\n\n');

      if (res.data.nextPageToken) {
        formattedOutput += `\n\nMore investigations available. Use the page_token parameter to view the next page: "${res.data.nextPageToken}"`;
      }

      return formattedOutput;
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError(
        `An unexpected error occurred while listing investigations.`,
        500,
        error
      );
    }
  }

  async fetchInvestigation(
    params: FetchInvestigationToolInput
  ): Promise<string> {
    await this._ensureReady({
      requireLicense: true,
    });
    const {
      projectId,
      investigationId,
      revisionId,
      filter_expression,
      next_page_token,
    } = params;
    if (revisionId && !investigationId) {
      throw new ApiError(
        'revisionId cannot be provided without investigationId.',
        400,
        'INVALID_ARGUMENT'
      );
    }

    if (investigationId) {
      return this._getInvestigation({
        projectId,
        investigationId,
        revisionId,
      });
    } else {
      return this._listInvestigations({
        projectId,
        filter: filter_expression,
        page_token: next_page_token,
      });
    }
  }

  async createInvestigation(
    params: CreateInvestigationToolInput
  ): Promise<Investigation> {
    await this._ensureReady({
      requireLicense: true,
    });
    const {
      projectId,
      title,
      issue_description,
      relevant_resources,
      start_time,
    } = params;
    const path = new InvestigationPath(projectId);
    const investigationRequest: CreateInvestigationRequest =
      createInitialInvestigationRequestBody(
        title,
        projectId,
        issue_description,
        relevant_resources,
        start_time
      );

    try {
      const investigationForRequest = JSON.parse(
        JSON.stringify(investigationRequest)
      );
      const request: CreateInvestigationApiRequest = {
        parent: path.getParent(),
        auth: this.auth,
        requestBody: investigationForRequest,
      };

      await this._writeLog('createInvestigation', 'input', { ...request });
      const res =
        await this.geminicloudassist.projects.locations.investigations.create(
          request
        );
      await this._writeLog('createInvestigation', 'output', { ...res.data });
      return res.data;
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError(
        'An unexpected error occurred while creating the investigation.',
        500,
        error
      );
    }
  }

  async runInvestigation(
    params: RunInvestigationToolInput
  ): Promise<Investigation> {
    await this._ensureReady({ requireLicense: true });
    const { projectId, investigationId, revisionId } = params;
    const path = new InvestigationPath(projectId, investigationId, revisionId);

    try {
      const request: RunInvestigationApiRequest = {
        name: path.getRevisionName(),
        auth: this.auth,
      };

      await this._writeLog('runInvestigation_run', 'input', { ...request });
      const runResponse =
        await this.geminicloudassist.projects.locations.investigations.revisions.run(
          request
        );
      await this._writeLog('runInvestigation_run', 'output', {
        ...runResponse.data,
      });

      const operationName = runResponse.data.name;

      let attempt = 0;
      let backoffSeconds = INITIAL_BACKOFF_SECONDS;

      while (attempt < MAX_POLLING_ATTEMPTS) {
        attempt++;

        const jitter = Math.random();
        const delaySeconds =
          Math.min(backoffSeconds, MAX_BACKOFF_SECONDS) + jitter;

        await new Promise((resolve) =>
          setTimeout(resolve, delaySeconds * 1000)
        );

        const opRequest: GetOperationApiRequest = {
          name: operationName,
          auth: this.auth,
        };

        await this._writeLog(
          `runInvestigation_poll_op_attempt_${attempt}`,
          'input',
          { ...opRequest }
        );
        const opRes =
          await this.geminicloudassist.projects.locations.operations.get(
            opRequest
          );
        await this._writeLog(
          `runInvestigation_poll_op_attempt_${attempt}`,
          'output',
          { ...opRes.data }
        );

        if (opRes.data.done) {
          if (opRes.data.error) {
            throw new ApiError(
              'Investigation operation failed',
              500,
              opRes.data.error
            );
          }
          return this._getInvestigationRaw({
            projectId,
            investigationId,
            revisionId,
          });
        }
        backoffSeconds *= BACKOFF_FACTOR;
      }

      const investigationData = await this._getInvestigationRaw({
        projectId,
        investigationId,
      });
      throw new ApiError(
        'Investigation did not complete within the timeout period.',
        504,
        {
          currentStatus: investigationData,
        }
      );
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError(
        'An unexpected error occurred while running the investigation.',
        500,
        error
      );
    }
  }

  async addObservation(
    params: AddObservationToolInput
  ): Promise<Investigation> {
    await this._ensureReady({ requireLicense: true });
    const { projectId, investigationId, observation, relevant_resources } =
      params;
    try {
      const latestRevision = await this._getInvestigationRaw({
        projectId,
        investigationId,
      });

      const newRevisionPayload = getRevisionWithNewObservation(
        latestRevision,
        observation,
        relevant_resources
      );

      if (!newRevisionPayload) {
        throw new ApiError(
          'Failed to create new revision payload.',
          500,
          'PAYLOAD_CREATION_FAILED'
        );
      }

      const path = new InvestigationPath(projectId, investigationId);
      const request = {
        parent: path.getInvestigationName(),
        auth: this.auth,
        requestBody: newRevisionPayload,
      };

      await this._writeLog('addObservation', 'input', request);
      const res =
        await this.geminicloudassist.projects.locations.investigations.revisions.create(
          request
        );
      await this._writeLog('addObservation', 'output', res.data);

      return res.data;
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError(
        `Error adding an observation to investigation: ${investigationId}.`,
        500,
        error
      );
    }
  }
}
