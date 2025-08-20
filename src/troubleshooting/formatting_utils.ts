/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { PRIMARY_USER_OBSERVATION_ID } from './api/constants.js';
import { InvestigationPath } from './api/utils.js';
import { Observation, Investigation, KnowledgeUrl } from './api/types.js';

const GEMINI_CLOUD_INVESTIGATIONS_BASE_URL =
  'https://console.cloud.google.com/troubleshooting/investigations/details/';

/**
 * Utility functions for formatting investigation data into human-readable text.
 */

function formatResources(resources: string[]): string[] {
  if (!resources || resources.length === 0) {
    return [];
  }
  const lines = [`**Relevant Resources (${resources.length})**`];
  lines.push(...resources.map((res) => `- ${res}`));
  return lines;
}

function formatKnowledgeUrls(links: KnowledgeUrl): string[] {
  if (!links) {
    return [];
  }
  const lines = ['**Relevant Links**:', ''];
  lines.push(
    ...Object.entries(links).map(([title, url]) => `- [${title}](${url})`)
  );
  return lines;
}

function isJson(str: string): boolean {
  try {
    JSON.parse(str);
  } catch {
    return false;
  }
  return true;
}

function cleanText(text: string | undefined | null): string {
  if (!text) {
    return '';
  }
  if (isJson(text)) {
    return '```json\n' + JSON.stringify(JSON.parse(text), null, 2) + '\n```';
  }
  return text;
}

export function getInvestigationLink(
  projectId: string,
  investigationId: string
): string {
  if (!projectId || !investigationId) {
    return '';
  }
  const params = new URLSearchParams({
    project: projectId,
  });
  return `${GEMINI_CLOUD_INVESTIGATIONS_BASE_URL}${investigationId}?${params.toString()}`;
}

// --- InvestigationViewer Class ---

export class InvestigationViewer {
  data: Investigation;
  path: InvestigationPath | null;
  observations: { [key: string]: Observation };
  userTextObservations: { [key: string]: Observation };

  /**
   * A tool to create a well-formatted, human-readable text representation
   * of an investigation JSON object.
   * @param {object} data - The investigation data loaded from JSON.
   */
  constructor(data: Investigation) {
    if (typeof data !== 'object' || data === null) {
      throw new TypeError('Input data must be an object.');
    }
    this.data = data.snapshot || data;
    this.path = InvestigationPath.fromInvestigationName(this.data.name || '');

    this.observations = {};
    if (this.data.observations) {
      for (const obs of Object.values(this.data.observations)) {
        if (obs.id) {
          this.observations[obs.id] = obs;
        }
      }
    }

    this.userTextObservations = {};
    for (const [obsId, obs] of Object.entries(this.observations)) {
      if (
        obs.observerType === 'OBSERVER_TYPE_USER' &&
        obs.observationType === 'OBSERVATION_TYPE_TEXT_DESCRIPTION'
      ) {
        this.userTextObservations[obsId] = obs;
      }
    }
  }

  formatIssueSection(): string {
    const userInput = this.observations[PRIMARY_USER_OBSERVATION_ID] || {};
    const startTime =
      userInput.timeIntervals &&
      userInput.timeIntervals[0] &&
      userInput.timeIntervals[0].startTime
        ? userInput.timeIntervals[0].startTime
        : 'N/A';
    const projectIdentifier = this.path ? this.path.getProjectId() : 'N/A';

    const details = {
      Name: this.data.title || 'N/A',
      'Start Time': startTime,
      'End Time': this.data.updateTime || 'N/A',
      Project: projectIdentifier,
      'Investigation Path': this.data.name || 'N/A',
      'Revision Path': this.data.revision || 'N/A',
    };

    const contentLines = ['## Gemini Cloud Assist Investigation', ''];
    contentLines.push(
      ...Object.entries(details).map(([key, value]) => `**${key}**: ${value}`)
    );
    contentLines.push('**Issue Description**:');
    contentLines.push(cleanText(userInput.text || 'No description provided.'));
    contentLines.push('');
    contentLines.push(...formatResources(userInput.relevantResources || []));
    contentLines.push('');

    return contentLines.join('\n');
  }

  formatUserObservationsSection(): string {
    const userObs = Object.values(this.userTextObservations).filter(
      (obs) => obs.id !== PRIMARY_USER_OBSERVATION_ID
    );

    if (userObs.length === 0) {
      return '';
    }

    const contentLines = [`## User Observations (${userObs.length})`, ''];
    for (const obs of userObs) {
      contentLines.push(`- ${cleanText(obs.text || 'No text content.')}`);
      contentLines.push('');
    }

    return contentLines.join('\n');
  }

  isRelevantObservation(obs: Observation): boolean {
    if (!obs.title) return false;
    if ((obs.systemRelevanceScore || -1) < 0) return false;

    const observerType = obs.observerType;
    const obsType = obs.observationType;

    if (observerType === 'OBSERVER_TYPE_USER') return false;
    if (obsType === 'OBSERVATION_TYPE_RELATED_RESOURCES') return false;

    return ['OBSERVER_TYPE_DIAGNOSTICS', 'OBSERVER_TYPE_SIGNALS'].includes(
      observerType || ''
    );
  }

  formatObservationsSection(): string {
    const relevantObs = Object.values(this.observations)
      .filter((obs) => this.isRelevantObservation(obs))
      .sort((a, b) => (a.title || '').localeCompare(b.title || ''));

    if (relevantObs.length === 0) {
      return '## Relevant Observations (0)\n\nNo relevant observations found matching the criteria.';
    }

    const sectionTitle = `## Relevant Observations (${relevantObs.length})`;
    const itemDetailBlocks = relevantObs.map((obs) => {
      const blockLines = [`### ${obs.title || 'N/A'}`];
      const obsIdType = (obs.id || 'N/A').split('.')[0];
      blockLines.push(
        `**Type**: ${obsIdType.charAt(0).toUpperCase() + obsIdType.slice(1).toLowerCase()}`
      );
      blockLines.push('');
      blockLines.push(cleanText(obs.text || 'No text content.'));
      blockLines.push(...formatResources(obs.relevantResources || []));
      return blockLines.join('\n');
    });

    const observationsDetailsStr = itemDetailBlocks.join('\n\n---\n\n');
    return `${sectionTitle}\n\n${observationsDetailsStr}`;
  }

  formatHypothesesSection(): string {
    const hypotheses = Object.values(this.observations)
      .filter((obs) => obs.observationType === 'OBSERVATION_TYPE_HYPOTHESIS')
      .sort((a, b) => (a.title || '').localeCompare(b.title || ''));

    if (hypotheses.length === 0) {
      return '## Hypotheses (0)\n\nNo hypotheses found.';
    }

    const sectionTitle = `## Hypotheses (${hypotheses.length})`;
    const itemDetailBlocks = hypotheses.map((hypo, i) => {
      const blockLines = [`### Hypothesis ${i + 1}: ${hypo.title || 'N/A'}`];
      const textContent = cleanText(hypo.text);
      textContent.split('\n').forEach((line) => {
        blockLines.push(
          line.trim().startsWith('*') || line.trim().startsWith('```')
            ? `  ${line}`
            : line
        );
      });
      blockLines.push('');
      blockLines.push(...formatKnowledgeUrls(hypo.knowledgeUrls || {}));
      return blockLines.join('\n');
    });

    const hypothesesDetailsStr = itemDetailBlocks.join('\n\n---\n\n');
    return `${sectionTitle}\n\n${hypothesesDetailsStr}`;
  }

  formatInvestigationLink(): string {
    if (!this.path) {
      return '';
    }
    const projectId = this.path.getProjectId();
    const investigationId = this.path.getInvestigationId();
    if (!projectId || !investigationId) {
      return '';
    }
    const link = getInvestigationLink(projectId, investigationId);
    if (!link) {
      return '';
    }
    return `------------------\n\nYou can view this investigation in the Google Cloud Console\n<${link}>\n\n------------------`;
  }

  render(options: { showObservationsAndHypotheses?: boolean } = {}): string {
    const { showObservationsAndHypotheses = true } = options;

    const sections = [
      this.formatIssueSection(),
      this.formatUserObservationsSection(),
    ];

    if (showObservationsAndHypotheses) {
      sections.push(this.formatObservationsSection());
      sections.push(this.formatHypothesesSection());
    }

    const mainContent = sections.filter(Boolean).join('\n\n');
    const investigationLink = this.formatInvestigationLink();

    return `${mainContent}\n\n${investigationLink}`.trim();
  }
}

// --- Investigation List Formatting ---
export function formatInvestigationList(
  investigationsData: Investigation[],
  nextPageToken?: string
): string {
  if (!investigationsData || investigationsData.length === 0) {
    return 'No investigations found.';
  }

  const formattedInvestigations = investigationsData.map((inv) => {
    const name = inv.name || 'N/A';
    const title = inv.title || 'N/A';
    let executionState = inv.executionState || 'N/A';
    if (executionState.startsWith('INVESTIGATION_EXECUTION_STATE_')) {
      executionState = executionState.replace(
        'INVESTIGATION_EXECUTION_STATE_',
        ''
      );
    }
    return `Investigation ID: ${name}\nTitle: ${title}\nState: ${executionState}`;
  });

  const separator = '\n' + '-'.repeat(80) + '\n';
  let outputText = formattedInvestigations.join(separator);
  if (nextPageToken) {
    outputText += `\n\nNext page token: ${nextPageToken}`;
  }
  return outputText;
}
