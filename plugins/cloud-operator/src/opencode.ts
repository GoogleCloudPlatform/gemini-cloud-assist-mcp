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

// OpenCode 2 plugin: adds the plugin's skills, its always-on rules, and its
// MCP servers signed in with Application Default Credentials.

import type { Plugin } from "@opencode/plugin";
import { GoogleAuth } from "./google-auth.ts";
import { type McpServer, readAlwaysOnRules, readMcpServers, readSkills } from "./plugin-files.ts";

const ID = "cloud-operator";

// OpenCode names an MCP tool <server>_<tool>, with characters other than
// letters, digits, "_" and "-" replaced by "_".
function toolPrefix(server: string): string {
  return `${server.replace(/[^A-Za-z0-9_-]/g, "_")}_`;
}

const plugin: Plugin.Plugin = {
  id: ID,
  async setup(ctx) {
    const servers = readMcpServers();
    const prefixes = servers.map((server) => toolPrefix(server.name));
    const isOurTool = (tool: string) => prefixes.some((prefix) => tool.startsWith(prefix));

    const auth = new GoogleAuth(() => ctx.mcp.reload());
    await auth.start();
    auth.startRenewing();
    if (auth.error) {
      console.warn(`${ID}: Google Cloud MCP servers are unavailable until Application Default Credentials work: ${auth.error}`);
    }

    // A server needs either ADC headers or a static header, such as the
    // usage attribution header. Re-evaluated on every reload, so a server
    // appears once credentials start working.
    const usable = (server: McpServer) =>
      Boolean(auth.headers.Authorization) || Object.keys(server.headers).length > 0;

    await ctx.mcp.transform((editor) => {
      for (const server of servers) {
        // A server of the same name in the user's own config wins.
        if (editor.get(server.name) || !usable(server)) continue;
        editor.set(server.name, {
          type: "remote",
          url: server.url,
          headers: { ...server.headers, ...auth.headers },
          oauth: false,
          // The skills call these tools by name, so expose them directly
          // rather than through Code Mode.
          codemode: false,
          ...(server.timeoutMs ? { timeout: { execution: server.timeoutMs } } : {}),
        } as Parameters<typeof editor.set>[1]);
      }
    });

    await ctx.tool.hook("execute.before", (event) => {
      if (isOurTool(event.tool)) auth.callStarted();
    });
    await ctx.tool.hook("execute.after", (event) => {
      if (isOurTool(event.tool)) auth.callEnded();
    });

    const skills = readSkills();
    await ctx.skill.transform((editor) => {
      for (const skill of skills) {
        editor.add({
          id: skill.name,
          name: skill.name,
          description: skill.description,
          path: skill.path,
          content: skill.body,
        } as Parameters<typeof editor.add>[0]);
      }
    });

    const rules = readAlwaysOnRules();
    if (rules.length > 0) {
      await ctx.session.hook("context", (event) => {
        for (const rule of rules) event.system.push({ type: "text", text: rule.text });
      });
    }

    return () => auth.stop();
  },
};

export default plugin;
