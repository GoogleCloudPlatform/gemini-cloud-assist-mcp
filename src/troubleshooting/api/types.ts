/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

export interface FetchInvestigationToolInput {
  projectId: string;
  investigationId?: string;
  revisionId?: string;
  filter_expression?: string;
  next_page_token?: string;
}

export interface GetInvestigationParams {
  projectId: string;
  investigationId: string;
  revisionId?: string;
}

export interface CreateInvestigationToolInput {
  projectId: string;
  title: string;
  issue_description: string;
  relevant_resources: string[];
  start_time: string;
}

export interface RunInvestigationToolInput {
  projectId: string;
  investigationId: string;
  revisionId: string;
}

export interface AddObservationToolInput {
  projectId: string;
  investigationId: string;
  observation: string;
  relevant_resources: string[];
}

export interface ListInvestigationsParams {
  projectId: string;
  filter?: string;
  page_token?: string;
}

export interface ListInvestigationsApiRequest {
  parent: string;
  auth: unknown;
  filter: string;
  pageSize: number;
  fields: string;
  pageToken?: string;
}

export interface CreateInvestigationApiRequest {
  parent: string;
  auth: unknown;
  requestBody: unknown;
}

export interface RunInvestigationApiRequest {
  name: string;
  auth: unknown;
}

export interface GetOperationApiRequest {
  name: string;
  auth: unknown;
}

export interface GetInvestigationApiRequest {
  name: string;
  auth: unknown;
}

// --- Core Investigation API Types ---

export interface Status {
  code?: number;
  message?: string;
  details?: unknown[];
}

export interface Interval {
  startTime?: string;
  endTime?: string;
}

export interface InvestigationAnnotations {
  followUp?: boolean;
  newlyCreated?: boolean;
  supportCase?: string;
  uiReadOnly?: boolean;
  uiHidden?: boolean;
  extrasMap?: Record<string, string>;
  componentVersions?: Record<string, string>;
  revisionLastRunInterval?: Interval;
  featureFlags?: Record<string, string>;
  pagePath?: string;
}

export interface KnowledgeUrl {
  [key: string]: string;
}

export interface Observation {
  id?: string;
  timeIntervals?: Interval[];
  title?: string;
  observationType?: string;
  observerType?: string;
  text?: string;
  data?: Record<string, unknown>;
  dataUrls?: Record<string, string>;
  knowledgeUrls?: Record<string, string>;
  baseObservations?: string[];
  relevantResources?: string[];
  recommendation?: string;
  systemRelevanceScore?: number;
  relevanceOverride?: string;
  observationCompletionState?: string;
  observedNormalOperation?: boolean;
}

export interface GeneralAbsentObservation {
  id?: string;
  title?: string;
  validationRegex?: string;
}

export interface AbsentObservation {
  param?: string;
  generalMissingObservation?: GeneralAbsentObservation;
  pendingObservation?: string;
}

export interface ObserverStatus {
  observer?: string;
  observerExecutionState?: string;
  observerDisplayName?: string;
  updateTime?: string;
  startTime?: string;
  updateComment?: string;
  absentObservations?: AbsentObservation[];
  observerErrors?: Status[];
}

export interface RunbookParameter {
  id?: string;
  displayName?: string;

  description?: string;
  exampleValues?: string[];
  value?: string;
  associatedAssetTypes?: string[];
}

export interface ClarificationNeeded {
  runbookParameter?: RunbookParameter;
  generalMissingObservation?: GeneralAbsentObservation;
  parentObserverNames?: string[];
}

export interface Investigation {
  name?: string;
  createTime?: string;
  updateTime?: string;
  labels?: Record<string, string>;
  revision?: string;
  revisionIndex?: number;
  revisionPredecessor?: string;
  annotations?: InvestigationAnnotations;
  executionState?: string;
  error?: Status;
  operation?: string;
  title?: string;
  observations?: Record<string, Observation>;
  observerStatuses?: Record<string, ObserverStatus>;
  dataVersion?: number;
  clarificationsNeeded?: Record<string, ClarificationNeeded>;
  snapshot?: Investigation;
}

export interface CreateInvestigationRequest {
  title: string;
  dataVersion: string;
  observations: {
    [key: string]: Observation;
  };
}

export interface InvestigationRevision {
  name?: string;
  snapshot?: Investigation;
  createTime?: string;
  labels?: Record<string, string>;
  index?: number;
}

export interface ListInvestigationsResponse {
  investigations?: Investigation[];
  nextPageToken?: string;
  unreachable?: string[];
}

export interface Operation {
  name?: string;
  done?: boolean;
  error?: unknown;
}
