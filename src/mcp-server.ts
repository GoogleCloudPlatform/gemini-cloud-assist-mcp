#!/usr/bin/env node

/**
 * @license
 * Copyright 2025 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { registerTools } from './tools.js';
import { readFileSync } from 'fs';

// Redirect console.log to stderr to not interfere with stdio transport
// eslint-disable-next-line no-console
const info = console.error;

interface PackageJson {
  name: string;
  version: string;
  displayName: string;
  description: string;
}

async function getServer(): Promise<McpServer> {
  const packageJson: PackageJson = JSON.parse(
    readFileSync(new URL('../package.json', import.meta.url)).toString()
  );
  const server = new McpServer({
    name: packageJson.name,
    version: packageJson.version,
    displayName: packageJson.displayName,
    description: packageJson.description,
    protocols: ['mcp/v1'],
  });
  registerTools(server);
  return server;
}

async function main(): Promise<void> {
  try {
    const stdioTransport = new StdioServerTransport();
    const server = await getServer();
    await server.connect(stdioTransport);
    info('Gemini Cloud Assist MCP server connected via stdio.');
  } catch (error) {
    info('Failed to start MCP server:', error);
    process.exit(1);
  }
}

main();
