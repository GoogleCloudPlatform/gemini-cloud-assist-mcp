#!/usr/bin/env node

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

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerTools } from './tools.js';
import { readFileSync } from 'fs';

// Redirect console.log to stderr to not interfere with stdio transport
const info = console.error;

async function getServer() {
    const packageJson = JSON.parse(readFileSync(new URL('./package.json', import.meta.url)));
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

async function main() {
    try {
        const stdioTransport = new StdioServerTransport();
        const server = await getServer();
        await server.connect(stdioTransport);
        info('Gemini Cloud Assist MCP server connected via stdio.');
    } catch (error) {
        console.error('Failed to start MCP server:', error);
        process.exit(1);
    }
}

main();
