// Copyright 2026 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Pi extension: adds the plugin's always-on rules and its MCP servers signed
// in with Application Default Credentials. Pi loads the skills itself, from
// "pi.skills" in package.json.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { GoogleAuth } from "./google-auth.ts";
import { type McpServer, readAlwaysOnRules, readMcpServers } from "./plugin-files.ts";

const ID = "cloud-operator";

// Pi names an MCP tool mcp__<server>__<tool>, with characters other than
// letters, digits and "_" replaced by "_".
function toolPrefix(server: string): string {
  return `mcp__${server.replace(/[^A-Za-z0-9_]/g, "_")}__`;
}

export default async function googleCloudDeveloper(pi: ExtensionAPI): Promise<void> {
  const rules = readAlwaysOnRules();
  pi.on("before_agent_start", (event) => {
    for (const rule of rules) event.systemPromptOptions.sections[rule.name] = rule.text;
  });

  // Pi releases before built-in MCP still get the skills and the rules. An
  // extension that throws while loading stops Pi from starting.
  if (typeof pi.registerMcpServer !== "function") {
    pi.on("session_start", (_event, ctx) =>
      ctx.ui.notify(`${ID}: the Google Cloud MCP servers need a newer Pi; run pi update.`, "warning"),
    );
    return;
  }

  const servers = readMcpServers();
  const prefixes = servers.map((server) => toolPrefix(server.name));
  const isOurTool = (tool: string) => prefixes.some((prefix) => tool.startsWith(prefix));

  const register = () => {
    for (const server of servers) {
      // A server needs either ADC headers or a static header, such as the
      // usage attribution header.
      if (!auth.headers.Authorization && Object.keys(server.headers).length === 0) continue;
      pi.registerMcpServer(server.name, serverConfig(server, auth.headers));
    }
  };
  // Registering a name again replaces the earlier registration, so this also
  // applies new headers. A server of the same name in the user's mcp.json wins.
  const auth = new GoogleAuth(register);
  await auth.start();
  register();

  pi.on("tool_execution_start", (event) => {
    if (isOurTool(event.toolName)) auth.callStarted();
  });
  pi.on("tool_execution_end", (event) => {
    if (isOurTool(event.toolName)) auth.callEnded();
  });
  // Pi loads extensions afresh for each session (a new session, /resume or
  // /fork runs this function again after session_shutdown), and some commands
  // load them without starting a session, so renewal runs only while a
  // session does, as Pi's extension docs ask for timers.
  pi.on("session_start", (_event, ctx) => {
    auth.startRenewing();
    if (auth.error) {
      ctx.ui.notify(
        `${ID}: Google Cloud MCP servers are unavailable until Application Default Credentials work: ${auth.error}`,
        "warning",
      );
    }
  });
  pi.on("session_shutdown", () => auth.stop());
}

function serverConfig(server: McpServer, adcHeaders: Record<string, string>) {
  return {
    type: "http" as const,
    url: server.url,
    headers: { ...server.headers, ...adcHeaders },
    // The skills call these tools by name, so declare them to the model
    // directly.
    exposure: "direct" as const,
    // Pi's timeout is in seconds.
    ...(server.timeoutMs ? { timeout: Math.ceil(server.timeoutMs / 1000) } : {}),
  };
}
