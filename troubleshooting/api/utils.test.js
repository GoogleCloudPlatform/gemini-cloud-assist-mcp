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

/**
 * @fileoverview Tests for utils.js using hardcoded realistic data.
 */

import { strict as assert } from 'assert';
import {
    createInitialInvestigation,
    getRevisionWithNewObservation,
    InvestigationPath,
    validateGcpResources,
} from './utils.js';

const realisticBasePayload = {
    "name": "projects/test-project/locations/global/investigations/529d3d15-5371-420a-bea6-b518f02bf046",
    "createTime": "2025-07-11T07:27:50.664567366Z",
    "updateTime": "2025-07-11T07:28:48.762878706Z",
    "revision": "projects/test-project/locatiofs/global/investigations/529d3d15-5371-420a-bea6-b518f02bf046/revisions/fefd4d24-dd35-49f5-9ff7-af303beb8551",
    "executionState": "INVESTIGATION_EXECUTION_STATE_COMPLETED",
    "title": "automated_eval_canonical_example_gke_00009_nodepool_unable_to_scale_due_to_ip_exhaustion",
    "observations": {
        "user.input.text": {
            "id": "user.input.text",
            "timeRanges": [{
                "startTime": "2025-05-20T00:30:00Z"
            }],
            "observationType": "OBSERVATION_TYPE_TEXT_DESCRIPTION",
            "observerType": "OBSERVER_TYPE_USER",
            "text": "I am unable to scale the nodepool in my GKE cluster 'gke-cluster-009' using the `gcloud` command. The command ran successfully without error, but the number of nodes in the nodepool did not change, even after waiting a long time.",
            "relevantResources": [
                "//container.googleapis.com/projects/test-project/locations/us-east4/clusters/gke-cluster-009"
            ]
        },
        "user.project": {
            "id": "user.project",
            "observationType": "OBSERVATION_TYPE_STRUCTURED_INPUT",
            "observerType": "OBSERVER_TYPE_USER",
            "text": "test-project"
        }
    }
}

let totalTests = 0;
let testsPassed = 0;
const errors = [];

function runTest(description, testFn) {
    totalTests++;
    try {
        testFn();
        console.log(`  ✅ ${description}`);
        testsPassed++;
    } catch (error) {
        console.error(`  ❌ ${description}`);
        errors.push({ description, error });
    }
}

function runApiUtilsTests() {
    console.log('\n--- Testing API Utils ---');

    runTest('createInitialInvestigation should create a valid payload.', () => {

        const initialPayload = createInitialInvestigation(
            '[Gemini CLI] Minimal Test Case',
            'test-project',
            'My GKE cluster is broken.',
            ['//container.googleapis.com/projects/test-project/locations/us-central1-a/clusters/cluster-abc'],
            '2025-07-10T12:00:00Z'
        );
        assert.strictEqual(initialPayload.title, '[Gemini CLI] Minimal Test Case');
        assert.ok(initialPayload.observations['user.project']);
        assert.ok(initialPayload.observations['user.input.text']);
        assert.strictEqual(initialPayload.observations['user.input.text'].relevantResources.length, 1);
    });

    runTest('getRevisionWithNewObservation should append text and resources.', () => {
        const newObservationText1 = 'The pods are all in a CrashLoopBackOff state.';
        const newResource1 = '//container.googleapis.com/projects/test-project/locations/us-central1-a/clusters/cluster-abc/pods/pod-123';
        const revision1 = getRevisionWithNewObservation(
            realisticBasePayload,
            newObservationText1,
            [newResource1]
        );
        const originalUserObsCount = Object.values(realisticBasePayload.observations).filter(o => o.observerType === 'OBSERVER_TYPE_USER').length;
        const newUserObsCount = Object.values(revision1.snapshot.observations).filter(o => o.observerType === 'OBSERVER_TYPE_USER').length;
        assert.strictEqual(newUserObsCount, originalUserObsCount, 'Should not add a new observation object.');
        const updatedObservation = revision1.snapshot.observations['user.input.text'];
        assert.ok(updatedObservation.text.includes(newObservationText1), 'The new observation text should be appended.');
        assert.ok(updatedObservation.relevantResources.includes(newResource1), 'The new resource should be added to relevantResources.');
    });

    runTest('getRevisionWithNewObservation should handle back-to-back calls.', () => {
        const newObservationText1 = 'The pods are all in a CrashLoopBackOff state.';
        const newResource1 = '//container.googleapis.com/projects/test-project/locations/us-central1-a/clusters/cluster-abc/pods/pod-123';
        const revision1 = getRevisionWithNewObservation(realisticBasePayload, newObservationText1, [newResource1]);
        const newObservationText2 = 'I also noticed that the node pool is at maximum capacity.';
        const revision2 = getRevisionWithNewObservation(revision1.snapshot, newObservationText2, []);
        const originalUserObsCount = Object.values(realisticBasePayload.observations).filter(o => o.observerType === 'OBSERVER_TYPE_USER').length;
        const finalUserObsCount = Object.values(revision2.snapshot.observations).filter(o => o.observerType === 'OBSERVER_TYPE_USER').length;
        assert.strictEqual(finalUserObsCount, originalUserObsCount, 'Should still have the same number of user observations.');
        const finalText = revision2.snapshot.observations['user.input.text'].text;
        assert.ok(finalText.includes(newObservationText1), 'The first observation text should still be present.');
        assert.ok(finalText.includes(newObservationText2), 'The second observation text should be appended.');
    });

    console.log('\n  --- Edge Cases ---');
    runTest('Handle null payload gracefully.', () => {
        const nullPayloadResult = getRevisionWithNewObservation(null, 'test', []);
        assert.strictEqual(nullPayloadResult, null);
    });

    runTest('Handle payload with no observations property.', () => {
        const noObsPayload = { title: 'Test' };
        const noObsResult = getRevisionWithNewObservation(noObsPayload, 'test', []);
        assert.ok(noObsResult.snapshot.observations);
        assert.strictEqual(Object.keys(noObsResult.snapshot.observations).length, 1);
    });
}

function testInvestigationPath() {
    console.log('\n--- Testing InvestigationPath ---');

    runTest('Constructor and basic getters should work.', () => {
        const path = new InvestigationPath('project-123', 'investigation-abc', 'revision-xyz');
        assert.strictEqual(path.getProjectId(), 'project-123');
        assert.strictEqual(path.getInvestigationId(), 'investigation-abc');
        assert.strictEqual(path.getParent(), 'projects/project-123/locations/global');
        assert.strictEqual(path.getInvestigationName(), 'projects/project-123/locations/global/investigations/investigation-abc');
        assert.strictEqual(path.getRevisionName(), 'projects/project-123/locations/global/investigations/investigation-abc/revisions/revision-xyz');
    });

    runTest('Constructor with missing revision should work.', () => {
        const path = new InvestigationPath('project-456', 'investigation-def');
        assert.strictEqual(path.getInvestigationName(), 'projects/project-456/locations/global/investigations/investigation-def');
        assert.throws(() => path.getRevisionName(), /Revision ID are not set/);
    });

    runTest('fromInvestigationName should parse full path.', () => {
        const fullName = 'projects/project-789/locations/global/investigations/investigation-ghi/revisions/revision-jkl';
        const path = InvestigationPath.fromInvestigationName(fullName);
        assert.ok(path);
        assert.strictEqual(path.getProjectId(), 'project-789');
        assert.strictEqual(path.getInvestigationId(), 'investigation-ghi');
        assert.strictEqual(path.getRevisionName(), fullName);
    });

    runTest('fromInvestigationName should parse investigation path.', () => {
        const investigationNameOnly = 'projects/project-101/locations/global/investigations/investigation-mno';
        const path = InvestigationPath.fromInvestigationName(investigationNameOnly);
        assert.ok(path);
        assert.strictEqual(path.getProjectId(), 'project-101');
        assert.strictEqual(path.getInvestigationId(), 'investigation-mno');
        assert.strictEqual(path.revisionId, null);
    });

    runTest('fromInvestigationName should parse project path.', () => {
        const projectPathOnly = 'projects/project-202/locations/global';
        const path = InvestigationPath.fromInvestigationName(projectPathOnly);
        assert.ok(path);
        assert.strictEqual(path.getProjectId(), 'project-202');
        assert.strictEqual(path.getInvestigationId(), null);
    });

    runTest('fromInvestigationName should handle invalid paths.', () => {
        assert.strictEqual(InvestigationPath.fromInvestigationName(''), null);
        assert.strictEqual(InvestigationPath.fromInvestigationName('invalid/path'), null);
    });
}

function testIsValidGcpResource() {
    console.log('\n--- Testing isValidGcpResource ---');

    runTest('Valid resource should return an empty array.', () => {
        const validResources = ['//compute.googleapis.com/projects/my-project/zones/us-central1-a/instances/my-instance'];
        assert.deepStrictEqual(validateGcpResources(validResources), []);
    });

    runTest('Multiple valid resources should return an empty array.', () => {
        const validResources = [
            '//compute.googleapis.com/projects/my-project/zones/us-central1-a/instances/my-instance',
            '//storage.googleapis.com/my-bucket/my-object',
            '//bigquery.googleapis.com/projects/my-project/datasets/my-dataset'
        ];
        assert.deepStrictEqual(validateGcpResources(validResources), []);
    });

    runTest('Valid storage bucket resource should return an empty array.', () => {
        const validResources = ['//storage.googleapis.com/bucket_id'];
        assert.deepStrictEqual(validateGcpResources(validResources), []);
    });

    runTest('Invalid resource (missing //) should return the invalid resource.', () => {
        const invalidResources = ['/compute.googleapis.com/projects/my-project'];
        assert.deepStrictEqual(validateGcpResources(invalidResources), invalidResources);
    });

    runTest('Invalid resource (http://) should return the invalid resource.', () => {
        const invalidResources = ['http://compute.googleapis.com/projects/my-project'];
        assert.deepStrictEqual(validateGcpResources(invalidResources), invalidResources);
    });

    runTest('Mixed valid and invalid resources should return only the invalid ones.', () => {
        const mixedResources = [
            '//compute.googleapis.com/projects/my-project/zones/us-central1-a/instances/my-instance',
            'invalid-resource',
            '//storage.googleapis.com/my-bucket/my-object',
            'another-invalid-resource'
        ];
        const expectedInvalid = ['invalid-resource', 'another-invalid-resource'];
        assert.deepStrictEqual(validateGcpResources(mixedResources), expectedInvalid);
    });

    runTest('Empty array should return an empty array.', () => {
        assert.deepStrictEqual(validateGcpResources([]), []);
    });

    runTest('Array with empty string should return the empty string.', () => {
        assert.deepStrictEqual(validateGcpResources(['']), ['']);
    });

    runTest('Array with null value should return the null value.', () => {
        assert.deepStrictEqual(validateGcpResources([null]), [null]);
    });

    runTest('Array with undefined value should return the undefined value.', () => {
        assert.deepStrictEqual(validateGcpResources([undefined]), [undefined]);
    });

    runTest('Array with number value should return the number value.', () => {
        assert.deepStrictEqual(validateGcpResources([123]), [123]);
    });

    runTest('Array with object value should return the object value.', () => {
        const obj = {};
        assert.deepStrictEqual(validateGcpResources([obj]), [obj]);
    });
}

function runAllTests() {
    runApiUtilsTests();
    testInvestigationPath();
    testIsValidGcpResource();

    console.log('\n====================================');
    if (testsPassed === totalTests) {
        console.log(`✅ All ${totalTests} tests passed!`);
    } else {
        const testsFailed = totalTests - testsPassed;
        console.error(`❌ ${testsFailed}/${totalTests} tests failed.\n`);
        errors.forEach(({ description, error }) => {
            console.error(`FAIL: ${description}`);
            console.error(error);
            console.error('---');
        });
    }
    console.log('====================================');
    return (testsPassed !== totalTests);
}

runAllTests();

