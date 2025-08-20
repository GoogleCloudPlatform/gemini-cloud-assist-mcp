/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @fileoverview Tests for utils.ts using hardcoded realistic data.
 */

import { describe, it, expect } from 'vitest';
import {
  createInitialInvestigationRequestBody,
  getRevisionWithNewObservation,
  InvestigationPath,
  validateGcpResources,
} from './utils.js';
import { Investigation } from './types.js';

const realisticBasePayload: Investigation = {
  name: 'projects/test-project/locations/global/investigations/529d3d15-5371-420a-bea6-b518f02bf046',
  createTime: '2025-07-11T07:27:50.664567366Z',
  updateTime: '2025-07-11T07:28:48.762878706Z',
  revision:
    'projects/test-project/locatiofs/global/investigations/529d3d15-5371-420a-bea6-b518f02bf046/revisions/fefd4d24-dd35-49f5-9ff7-af303beb8551',
  executionState: 'INVESTIGATION_EXECUTION_STATE_COMPLETED',
  title:
    'automated_eval_canonical_example_gke_00009_nodepool_unable_to_scale_due_to_ip_exhaustion',
  observations: {
    'user.input.text': {
      id: 'user.input.text',
      timeIntervals: [
        {
          startTime: '2025-05-20T00:30:00Z',
        },
      ],
      observationType: 'OBSERVATION_TYPE_TEXT_DESCRIPTION',
      observerType: 'OBSERVER_TYPE_USER',
      text: "I am unable to scale the nodepool in my GKE cluster 'gke-cluster-009' using the `gcloud` command. The command ran successfully without error, but the number of nodes in the nodepool did not change, even after waiting a long time.",
      relevantResources: [
        '//container.googleapis.com/projects/test-project/locations/us-east4/clusters/gke-cluster-009',
      ],
    },
    'user.project': {
      id: 'user.project',
      observationType: 'OBSERVATION_TYPE_STRUCTURED_INPUT',
      observerType: 'OBSERVER_TYPE_USER',
      text: 'test-project',
    },
  },
};

describe('API Utils', () => {
  it('createInitialInvestigation should create a valid payload.', () => {
    const initialPayload = createInitialInvestigationRequestBody(
      '[Gemini CLI] Minimal Test Case',
      'test-project',
      'My GKE cluster is broken.',
      [
        '//container.googleapis.com/projects/test-project/locations/us-central1-a/clusters/cluster-abc',
      ],
      '2025-07-10T12:00:00Z'
    );
    expect(initialPayload.title).toBe('[Gemini CLI] Minimal Test Case');
    expect(initialPayload.observations['user.project']).toBeDefined();
    expect(initialPayload.observations['user.input.text']).toBeDefined();
    expect(
      initialPayload.observations['user.input.text'].relevantResources
    ).toHaveLength(1);
  });

  it('getRevisionWithNewObservation should append text and resources.', () => {
    const newObservationText1 = 'The pods are all in a CrashLoopBackOff state.';
    const newResource1 =
      '//container.googleapis.com/projects/test-project/locations/us-central1-a/clusters/cluster-abc/pods/pod-123';
    const revision1 = getRevisionWithNewObservation(
      realisticBasePayload,
      newObservationText1,
      [newResource1]
    );
    const originalUserObsCount = Object.values(
      realisticBasePayload.observations!
    ).filter((o) => o.observerType === 'OBSERVER_TYPE_USER').length;
    const newUserObsCount = Object.values(
      revision1!.snapshot.observations!
    ).filter((o) => o.observerType === 'OBSERVER_TYPE_USER').length;
    expect(newUserObsCount).toBe(originalUserObsCount);
    const updatedObservation =
      revision1!.snapshot.observations!['user.input.text'];
    expect(updatedObservation.text).toContain(newObservationText1);
    expect(updatedObservation.relevantResources).toContain(newResource1);
  });

  it('getRevisionWithNewObservation should handle back-to-back calls.', () => {
    const newObservationText1 = 'The pods are all in a CrashLoopBackOff state.';
    const newResource1 =
      '//container.googleapis.com/projects/test-project/locations/us-central1-a/clusters/cluster-abc/pods/pod-123';
    const revision1 = getRevisionWithNewObservation(
      realisticBasePayload,
      newObservationText1,
      [newResource1]
    );
    const newObservationText2 =
      'I also noticed that the node pool is at maximum capacity.';
    const revision2 = getRevisionWithNewObservation(
      revision1!.snapshot,
      newObservationText2,
      []
    );
    const originalUserObsCount = Object.values(
      realisticBasePayload.observations!
    ).filter((o) => o.observerType === 'OBSERVER_TYPE_USER').length;
    const finalUserObsCount = Object.values(
      revision2!.snapshot.observations!
    ).filter((o) => o.observerType === 'OBSERVER_TYPE_USER').length;
    expect(finalUserObsCount).toBe(originalUserObsCount);
    const finalText = revision2!.snapshot.observations!['user.input.text'].text;
    expect(finalText).toContain(newObservationText1);
    expect(finalText).toContain(newObservationText2);
  });

  describe('Edge Cases', () => {
    it('Handle null payload gracefully.', () => {
      const nullPayloadResult = getRevisionWithNewObservation(null, 'test', []);
      expect(nullPayloadResult).toBeNull();
    });

    it('Handle payload with no observations property.', () => {
      const noObsPayload: Investigation = { title: 'Test' };
      const noObsResult = getRevisionWithNewObservation(
        noObsPayload,
        'test',
        []
      );
      expect(noObsResult!.snapshot.observations).toBeDefined();
      expect(Object.keys(noObsResult!.snapshot.observations!)).toHaveLength(1);
    });
  });
});

describe('InvestigationPath', () => {
  it('Constructor and basic getters should work.', () => {
    const path = new InvestigationPath(
      'project-123',
      'investigation-abc',
      'revision-xyz'
    );
    expect(path.getProjectId()).toBe('project-123');
    expect(path.getInvestigationId()).toBe('investigation-abc');
    expect(path.getParent()).toBe('projects/project-123/locations/global');
    expect(path.getInvestigationName()).toBe(
      'projects/project-123/locations/global/investigations/investigation-abc'
    );
    expect(path.getRevisionName()).toBe(
      'projects/project-123/locations/global/investigations/investigation-abc/revisions/revision-xyz'
    );
  });

  it('Constructor with missing revision should work.', () => {
    const path = new InvestigationPath('project-456', 'investigation-def');
    expect(path.getInvestigationName()).toBe(
      'projects/project-456/locations/global/investigations/investigation-def'
    );
    expect(() => path.getRevisionName()).toThrow(
      /Investigation ID and\/or Revision ID are not set/
    );
  });

  it('fromInvestigationName should parse full path.', () => {
    const fullName =
      'projects/project-789/locations/global/investigations/investigation-ghi/revisions/revision-jkl';
    const path = InvestigationPath.fromInvestigationName(fullName);
    expect(path).toBeDefined();
    expect(path!.getProjectId()).toBe('project-789');
    expect(path!.getInvestigationId()).toBe('investigation-ghi');
    expect(path!.getRevisionName()).toBe(fullName);
  });

  it('fromInvestigationName should parse investigation path.', () => {
    const investigationNameOnly =
      'projects/project-101/locations/global/investigations/investigation-mno';
    const path = InvestigationPath.fromInvestigationName(investigationNameOnly);
    expect(path).toBeDefined();
    expect(path!.getProjectId()).toBe('project-101');
    expect(path!.getInvestigationId()).toBe('investigation-mno');
    expect(path!.revisionId).toBeUndefined();
  });

  it('fromInvestigationName should parse project path.', () => {
    const projectPathOnly = 'projects/project-202/locations/global';
    const path = InvestigationPath.fromInvestigationName(projectPathOnly);
    expect(path).toBeDefined();
    expect(path!.getProjectId()).toBe('project-202');
    expect(path!.getInvestigationId()).toBeUndefined();
  });

  it('fromInvestigationName should handle invalid paths.', () => {
    expect(InvestigationPath.fromInvestigationName('')).toBeNull();
    expect(InvestigationPath.fromInvestigationName('invalid/path')).toBeNull();
  });
});

describe('isValidGcpResource', () => {
  it('Valid resource should return an empty array.', () => {
    const validResources = [
      '//compute.googleapis.com/projects/my-project/zones/us-central1-a/instances/my-instance',
    ];
    expect(validateGcpResources(validResources)).toEqual([]);
  });

  it('Multiple valid resources should return an empty array.', () => {
    const validResources = [
      '//compute.googleapis.com/projects/my-project/zones/us-central1-a/instances/my-instance',
      '//storage.googleapis.com/my-bucket/my-object',
      '//bigquery.googleapis.com/projects/my-project/datasets/my-dataset',
    ];
    expect(validateGcpResources(validResources)).toEqual([]);
  });

  it('Valid storage bucket resource should return an empty array.', () => {
    const validResources = ['//storage.googleapis.com/bucket_id'];
    expect(validateGcpResources(validResources)).toEqual([]);
  });

  it('Invalid resource (missing //) should return the invalid resource.', () => {
    const invalidResources = ['/compute.googleapis.com/projects/my-project'];
    expect(validateGcpResources(invalidResources)).toEqual(invalidResources);
  });

  it('Invalid resource (http://) should return the invalid resource.', () => {
    const invalidResources = [
      'http://compute.googleapis.com/projects/my-project',
    ];
    expect(validateGcpResources(invalidResources)).toEqual(invalidResources);
  });

  it('Mixed valid and invalid resources should return only the invalid ones.', () => {
    const mixedResources = [
      '//compute.googleapis.com/projects/my-project/zones/us-central1-a/instances/my-instance',
      'invalid-resource',
      '//storage.googleapis.com/my-bucket/my-object',
      'another-invalid-resource',
    ];
    const expectedInvalid = ['invalid-resource', 'another-invalid-resource'];
    expect(validateGcpResources(mixedResources)).toEqual(expectedInvalid);
  });

  it('Empty array should return an empty array.', () => {
    expect(validateGcpResources([])).toEqual([]);
  });

  it('Array with empty string should return the empty string.', () => {
    expect(validateGcpResources([''])).toEqual(['']);
  });
});
