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

// Reads what the OpenCode plugin and the Pi extension need from the files the
// other clients already use, so nothing is declared twice: the MCP servers
// from .mcp.json, the always-on rules from rules/ (this plugin has none), and
// the skills from skills/.

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const PLUGIN_ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

export interface McpServer {
  name: string;
  url: string;
  // Static headers, such as the usage attribution header, with
  // environment variables expanded and empty values dropped.
  headers: Record<string, string>;
  // Per-call timeout in milliseconds; undefined keeps the client's default.
  timeoutMs?: number;
}

export interface SkillFile {
  name: string;
  description: string;
  path: string;
  body: string;
}

function readJson(relativePath: string): Record<string, any> {
  const path = join(PLUGIN_ROOT, relativePath);
  return existsSync(path) ? JSON.parse(readFileSync(path, "utf8")) : {};
}

// Expands ${NAME} and ${NAME:-default}, the forms .mcp.json headers can use.
function expandEnv(value: string): string {
  return value.replace(
    /\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}/g,
    (_, name: string, fallback?: string) => process.env[name] || fallback || "",
  );
}

// The servers come from .mcp.json, which Claude Code also reads. mcp.json, the
// Agent Plugins file, lists the same servers but can't carry what is needed
// here: headers, such as the usage attribution header, and a timeout.
// headersHelper is not used, since the plugin runs scripts/adc-headers itself
// (google-auth.ts).
export function readMcpServers(): McpServer[] {
  const servers = readJson(".mcp.json").mcpServers ?? {};
  return Object.entries(servers).map(([name, server]: [string, any]) => {
    const headers: Record<string, string> = {};
    for (const [key, raw] of Object.entries(server.headers ?? {})) {
      const value = expandEnv(String(raw));
      if (value) headers[key] = value;
    }
    return { name, url: server.url, headers, timeoutMs: server.timeout };
  });
}

// Splits a Markdown file into its YAML frontmatter fields and its body.
// Handles the frontmatter these files use: plain or quoted scalars and the
// folded (>, >-) and literal (|, |-) block styles. Nested maps such as
// metadata are skipped.
function parseFrontmatter(text: string): { fields: Record<string, string>; body: string } {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(text);
  if (!match) return { fields: {}, body: text };
  const fields: Record<string, string> = {};
  const lines = match[1].split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const field = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(lines[i]);
    if (!field) continue;
    const [, key, rest] = field;
    if (/^[>|][+-]?$/.test(rest)) {
      const block: string[] = [];
      while (i + 1 < lines.length && (/^\s/.test(lines[i + 1]) || lines[i + 1] === "")) {
        block.push(lines[++i].trim());
      }
      fields[key] = rest.startsWith(">") ? block.join(" ").trim() : block.join("\n").trim();
    } else if (rest) {
      fields[key] = rest.replace(/^(["'])(.*)\1$/, "$2");
    }
  }
  return { fields, body: match[2] };
}

export function readSkills(): SkillFile[] {
  const root = join(PLUGIN_ROOT, "skills");
  if (!existsSync(root)) return [];
  const skills: SkillFile[] = [];
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const path = join(root, entry.name, "SKILL.md");
    if (!entry.isDirectory() || !existsSync(path)) continue;
    const { fields, body } = parseFrontmatter(readFileSync(path, "utf8"));
    if (!fields.name || !fields.description) continue;
    skills.push({ name: fields.name, description: fields.description, path, body: body.trimStart() });
  }
  return skills.sort((a, b) => a.name.localeCompare(b.name));
}

// Rules marked trigger: always_on, which Antigravity loads into every
// conversation, as Markdown without their frontmatter.
export function readAlwaysOnRules(): { name: string; text: string }[] {
  const root = join(PLUGIN_ROOT, "rules");
  if (!existsSync(root)) return [];
  return readdirSync(root)
    .filter((file) => file.endsWith(".md"))
    .sort()
    .map((file) => ({ name: file.replace(/\.md$/, ""), ...parseFrontmatter(readFileSync(join(root, file), "utf8")) }))
    .filter((rule) => rule.fields.trigger === "always_on")
    .map((rule) => ({ name: rule.name, text: rule.body.trim() }));
}
