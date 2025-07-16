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
    InvestigationPath
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
};


function runApiUtilsTests() {
    console.log('Running tests for the api utils part of utils.js...');

    // Test case 1: Verifies that `createInitialInvestigation` correctly
    // constructs a valid investigation payload.
    console.log('Test 1: createInitialInvestigation should create a valid payload.');
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
    console.log('Test 1 Passed.');


    // Test case 2: Checks if `getRevisionWithNewObservation` can successfully
    // append text and resources to the primary observation.
    console.log('\nTest 2: getRevisionWithNewObservation should append text and resources to the primary observation.');
    const newObservationText1 = 'The pods are all in a CrashLoopBackOff state.';
    const newResource1 = '//container.googleapis.com/projects/test-project/locations/us-central1-a/clusters/cluster-abc/pods/pod-123';
    const revision1 = getRevisionWithNewObservation(
        realisticBasePayload,
        newObservationText1,
        [newResource1]
    );

    const originalUserObsCount = Object.values(realisticBasePayload.observations).filter(o => o.observerType === 'OBSERVER_TYPE_USER').length;
    const newUserObsCount = Object.values(revision1.snapshot.observations).filter(o => o.observerType === 'OBSERVER_TYPE_USER').length;

    // The number of observations should NOT change.
    assert.strictEqual(newUserObsCount, originalUserObsCount, 'Should not add a new observation object.');

    // The text should be appended.
    const updatedObservation = revision1.snapshot.observations['user.input.text'];
    assert.ok(updatedObservation.text.includes(newObservationText1), 'The new observation text should be appended.');

    // The new resource should be added.
    assert.ok(updatedObservation.relevantResources.includes(newResource1), 'The new resource should be added to relevantResources.');
    console.log('Test 2 Passed.');


    // Test case 3: Ensures that the system can handle multiple, sequential additions
    // of observations to the same investigation payload without errors.
    console.log('\nTest 3: getRevisionWithNewObservation should handle back-to-back calls, appending text sequentially.');
    const newObservationText2 = 'I also noticed that the node pool is at maximum capacity.';
    const revision2 = getRevisionWithNewObservation(
        revision1.snapshot,
        newObservationText2,
        [] // No new resources this time
    );

    const finalUserObsCount = Object.values(revision2.snapshot.observations).filter(o => o.observerType === 'OBSERVER_TYPE_USER').length;
    assert.strictEqual(finalUserObsCount, originalUserObsCount, 'Should still have the same number of user observations after back-to-back calls.');

    const finalText = revision2.snapshot.observations['user.input.text'].text;
    assert.ok(finalText.includes(newObservationText1), 'The first observation text should still be present.');
    assert.ok(finalText.includes(newObservationText2), 'The second observation text should be appended.');
    console.log('Test 3 Passed.');


    // --- Edge Cases ---
    console.log('\n--- Running Edge Case Tests ---');

    // Test case 4: Confirms that the function gracefully handles a `null` input
    // for the payload, which is a potential failure point.
    console.log('Test 4 (Edge Case): Handle null payload.');
    const nullPayloadResult = getRevisionWithNewObservation(null, 'test', []);
    assert.strictEqual(nullPayloadResult, null);
    console.log('Test 4 Passed.');

    // Test case 5: Verifies that the function can work with a payload object
    // that is missing the `observations` property entirely.
    console.log('Test 5 (Edge Case): Handle payload with no observations property.');
    const noObsPayload = { title: 'Test' };
    const noObsResult = getRevisionWithNewObservation(noObsPayload, 'test', []);
    assert.ok(noObsResult.snapshot.observations);
    assert.strictEqual(Object.keys(noObsResult.snapshot.observations).length, 1);
    console.log('Test 5 Passed.');

    console.log('\nAll api_utils tests passed!');
}

function testInvestigationPath() {
    console.log('Running tests for the InvestigationPath part of utils.js...');

    // Test constructor and basic getters
    const path1 = new InvestigationPath('project-123', 'investigation-abc', 'revision-xyz');
    assert.strictEqual(path1.getProjectId(), 'project-123', 'Test Case 1 Failed: getProjectId');
    assert.strictEqual(path1.getInvestigationId(), 'investigation-abc', 'Test Case 2 Failed: getInvestigationId');
    assert.strictEqual(path1.getParent(), 'projects/project-123/locations/global', 'Test Case 3 Failed: getParent');
    assert.strictEqual(path1.getInvestigationName(), 'projects/project-123/locations/global/investigations/investigation-abc', 'Test Case 4 Failed: getInvestigationName');
    assert.strictEqual(path1.getRevisionName(), 'projects/project-123/locations/global/investigations/investigation-abc/revisions/revision-xyz', 'Test Case 5 Failed: getRevisionName');

    // Test constructor with missing revision
    const path2 = new InvestigationPath('project-456', 'investigation-def');
    assert.strictEqual(path2.getInvestigationName(), 'projects/project-456/locations/global/investigations/investigation-def', 'Test Case 6 Failed: getInvestigationName without revision');
    assert.throws(() => path2.getRevisionName(), /Revision ID are not set/, 'Test Case 7 Failed: Throws on getRevisionName without revisionId');

    // Test fromInvestigationName - full path
    const fullName = 'projects/project-789/locations/global/investigations/investigation-ghi/revisions/revision-jkl';
    const path3 = InvestigationPath.fromInvestigationName(fullName);
    assert.ok(path3, 'Test Case 8 Failed: fromInvestigationName should not return null for valid full name');
    assert.strictEqual(path3.getProjectId(), 'project-789', 'Test Case 9 Failed: fromInvestigationName projectId parsing');
    assert.strictEqual(path3.getInvestigationId(), 'investigation-ghi', 'Test Case 10 Failed: fromInvestigationName investigationId parsing');
    assert.strictEqual(path3.getRevisionName(), fullName, 'Test Case 11 Failed: fromInvestigationName full path reconstruction');

    // Test fromInvestigationName - investigation path only
    const investigationNameOnly = 'projects/project-101/locations/global/investigations/investigation-mno';
    const path4 = InvestigationPath.fromInvestigationName(investigationNameOnly);
    assert.ok(path4, 'Test Case 12 Failed: fromInvestigationName should not return null for investigation name');
    assert.strictEqual(path4.getProjectId(), 'project-101', 'Test Case 13 Failed: fromInvestigationName projectId parsing (investigation only)');
    assert.strictEqual(path4.getInvestigationId(), 'investigation-mno', 'Test Case 14 Failed: fromInvestigationName investigationId parsing (investigation only)');
    assert.strictEqual(path4.revisionId, null, 'Test Case 15 Failed: fromInvestigationName revisionId should be null');

    // Test fromInvestigationName - project path only
    const projectPathOnly = 'projects/project-202/locations/global';
    const path5 = InvestigationPath.fromInvestigationName(projectPathOnly);
    assert.ok(path5, 'Test Case 16 Failed: fromInvestigationName should not return null for project path');
    assert.strictEqual(path5.getProjectId(), 'project-202', 'Test Case 17 Failed: fromInvestigationName projectId parsing (project only)');
    assert.strictEqual(path5.getInvestigationId(), null, 'Test Case 18 Failed: fromInvestigationName investigationId should be null');

    // Test fromInvestigationName - invalid paths
    assert.strictEqual(InvestigationPath.fromInvestigationName(''), null, 'Test Case 19 Failed: Handles empty string');
    assert.strictEqual(InvestigationPath.fromInvestigationName('invalid/path'), null, 'Test Case 20 Failed: Handles invalid path');

    console.log('All InvestigationPath tests passed!');
}

runApiUtilsTests();
testInvestigationPath();

console.log('\nAll tests in utils.test.js passed!');
