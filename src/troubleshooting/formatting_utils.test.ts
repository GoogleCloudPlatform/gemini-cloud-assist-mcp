/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';
import {
  InvestigationViewer,
  formatInvestigationList,
} from './formatting_utils.js';
import { fileURLToPath } from 'url';
import { Investigation } from './api/types.js';

// --- Mock Data ---

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const realisticInvestigationPath = path.join(
  __dirname,
  'test-data',
  'test_investigation.json'
);
const mockInvestigationData: Investigation = JSON.parse(
  fs.readFileSync(realisticInvestigationPath, 'utf-8')
);

const mockInvestigationList = [
  {
    name: 'investigation-1',
    title: 'First Investigation',
    executionState: 'INVESTIGATION_EXECUTION_STATE_SUCCEEDED',
  },
  {
    name: 'investigation-2',
    title: 'Second Investigation',
    executionState: 'INVESTIGATION_EXECUTION_STATE_FAILED',
  },
];

// --- Test Cases ---

describe('InvestigationViewer', () => {
  const viewer = new InvestigationViewer(mockInvestigationData);

  it('should format the issue section', () => {
    const issueSection = viewer.formatIssueSection();
    expect(issueSection).toContain('## Gemini Cloud Assist Investigation');
    expect(issueSection).toContain(
      '**Name**: [Gemini CLI Test] Test Investigation for GKE'
    );
    expect(issueSection).toContain('**Start Time**: N/A');
    expect(issueSection).toContain(
      "**Issue Description**:\nThe 'default-pool' nodepool in our GKE cluster 'gke-cluster-123' is not scaling up as expected."
    );
  });

  it('should format the user observations section', () => {
    const userObsSection = viewer.formatUserObservationsSection();
    expect(userObsSection).toBe('');
  });

  it('should format the observations section', () => {
    const obsSection = viewer.formatObservationsSection();
    expect(obsSection).toContain('## Relevant Observations (8)');
    expect(obsSection).toContain(
      '### Nodepool Scaling Issues: IP Exhaustion & Template Missing'
    );
  });

  it('should format the hypotheses section', () => {
    const hypoSection = viewer.formatHypothesesSection();
    expect(hypoSection).toContain('## Hypotheses (3)');
  });

  it('should format the investigation link', () => {
    const link = viewer.formatInvestigationLink();
    expect(link).toContain(
      'https://console.cloud.google.com/troubleshooting/investigations/details/8b1f9405-15b6-4830-b57e-2ff6a1dd5119'
    );
  });

  it('should render the full investigation', () => {
    const rendered = viewer.render();
    expect(rendered.length).toBeGreaterThan(0);
  });

  it('should render without observations and hypotheses', () => {
    const renderedWithoutObs = viewer.render({
      showObservationsAndHypotheses: false,
    });
    expect(renderedWithoutObs).not.toContain('## Relevant Observations');
    expect(renderedWithoutObs).not.toContain('## Hypotheses');
  });
});

describe('formatInvestigationList', () => {
  it('should format a list of investigations', () => {
    const formattedList = formatInvestigationList(mockInvestigationList);
    expect(formattedList).toContain('Investigation ID: investigation-1');
    expect(formattedList).toContain('Title: Second Investigation');
  });

  it('should format a list of investigations with a next page token', () => {
    const formattedListWithToken = formatInvestigationList(
      mockInvestigationList,
      'test-token'
    );
    expect(formattedListWithToken).toContain('Next page token: test-token');
  });

  it('should return a message for an empty list of investigations', () => {
    const noData = formatInvestigationList([]);
    expect(noData).toBe('No investigations found.');
  });
});
