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

import assert from 'assert';
import fs from 'fs';
import path from 'path';
import { InvestigationViewer, formatInvestigationList } from './formatting_utils.js';

// --- Mock Data ---

import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const realisticInvestigationPath = path.join(__dirname, 'test-data', 'test_investigation.json');
const mockInvestigationData = JSON.parse(fs.readFileSync(realisticInvestigationPath, 'utf-8'));

const mockInvestigationList = [
    { name: 'investigation-1', title: 'First Investigation', executionState: 'INVESTIGATION_EXECUTION_STATE_SUCCEEDED' },
    { name: 'investigation-2', title: 'Second Investigation', executionState: 'INVESTIGATION_EXECUTION_STATE_FAILED' }
];


// --- Test Cases ---

function testInvestigationViewer() {
    console.log('--- Running InvestigationViewer Tests ---');

    const viewer = new InvestigationViewer(mockInvestigationData);

    // Test formatIssueSection
    const issueSection = viewer.formatIssueSection();
    console.log('\n--- Testing formatIssueSection ---');
    console.log(issueSection);
    assert(issueSection.includes('## Gemini Cloud Assist Investigation'), 'Issue section should have a title');
    assert(issueSection.includes('**Name**: [Gemini CLI Test] Test Investigation for GKE'), 'Issue section should have the investigation name');
    assert(issueSection.includes('**Start Time**: N/A'), 'Issue section should have the start time');
    assert(issueSection.includes('**Issue Description**:\nThe \'default-pool\' nodepool in our GKE cluster \'gke-cluster-123\' is not scaling up as expected.'), 'Issue section should have the issue description');
    console.log('✅ formatIssueSection passed');

    // Test formatUserObservationsSection
    const userObsSection = viewer.formatUserObservationsSection();
    console.log('\n--- Testing formatUserObservationsSection ---');
    console.log(userObsSection);
    assert(userObsSection === '', 'User observations section should be empty');
    console.log('✅ formatUserObservationsSection passed');

    // Test formatObservationsSection
    const obsSection = viewer.formatObservationsSection();
    console.log('\n--- Testing formatObservationsSection ---');
    console.log(obsSection);
    assert(obsSection.includes('## Relevant Observations (8)'), 'Relevant observations section should have a title');
    assert(obsSection.includes('### Nodepool Scaling Issues: IP Exhaustion & Template Missing'), 'Relevant observations should contain IP Exhaustion Observation.');
    console.log('✅ formatObservationsSection passed');

    // Test formatHypothesesSection
    const hypoSection = viewer.formatHypothesesSection();
    console.log('\n--- Testing formatHypothesesSection ---');
    console.log(hypoSection);
    assert(hypoSection.includes('## Hypotheses (3)'), 'Hypotheses section should have a title');
    console.log('✅ formatHypothesesSection passed');

    // Test formatInvestigationLink
    const link = viewer.formatInvestigationLink();
    console.log('\n--- Testing formatInvestigationLink ---');
    console.log(link);
    assert(link.includes('https://console.cloud.google.com/troubleshooting/investigations/details/8b1f9405-15b6-4830-b57e-2ff6a1dd5119'), 'Investigation link should be correct');
    console.log('✅ formatInvestigationLink passed');

    // Test render
    const rendered = viewer.render();
    console.log('\n--- Testing render ---');
    console.log(rendered);
    assert(rendered.length > 0, 'Rendered output should not be empty');
    console.log('✅ render passed');

    // Test render with showObservationsAndHypotheses = false
    const renderedWithoutObs = viewer.render({ showObservationsAndHypotheses: false });
    console.log('\n--- Testing render with showObservationsAndHypotheses = false ---');
    console.log(renderedWithoutObs);
    assert(!renderedWithoutObs.includes('## Relevant Observations'), 'Rendered output should not contain observations');
    assert(!renderedWithoutObs.includes('## Hypotheses'), 'Rendered output should not contain hypotheses');
    console.log('✅ render with showObservationsAndHypotheses = false passed');

    console.log('--- InvestigationViewer Tests Passed ---');
}

function testFormatInvestigationList() {
    console.log('--- Running formatInvestigationList Tests ---');

    // Test with data
    const formattedList = formatInvestigationList(mockInvestigationList);
    console.log('\n--- Testing formatInvestigationList with data ---');
    console.log(formattedList);
    assert(formattedList.includes('Investigation ID: investigation-1'), 'Formatted list should include the first investigation');
    assert(formattedList.includes('Title: Second Investigation'), 'Formatted list should include the second investigation');
    console.log('✅ formatInvestigationList with data passed');

    // Test with nextPageToken
    const formattedListWithToken = formatInvestigationList(mockInvestigationList, 'test-token');
    console.log('\n--- Testing formatInvestigationList with nextPageToken ---');
    console.log(formattedListWithToken);
    assert(formattedListWithToken.includes('Next page token: test-token'), 'Formatted list should include the next page token');
    console.log('✅ formatInvestigationList with nextPageToken passed');

    // Test with no data
    const noData = formatInvestigationList([]);
    console.log('\n--- Testing formatInvestigationList with no data ---');
    console.log(noData);
    assert.strictEqual(noData, 'No investigations found.', 'Should return "No investigations found." for empty data');
    console.log('✅ formatInvestigationList with no data passed');

    console.log('--- formatInvestigationList Tests Passed ---');
}


// --- Run All Tests ---

try {
    testInvestigationViewer();
    console.log('');
    testFormatInvestigationList();
    console.log('\nAll tests passed!');
} catch (error) {
    console.error('\nTests failed:', error.message);
    process.exit(1);
}
