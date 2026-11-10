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

// Application Default Credentials headers for the MCP servers. OpenCode and
// Pi send fixed headers, with nothing like Claude Code's headersHelper, so the
// plugin runs scripts/adc-headers itself, the same script Claude Code and
// Codex run, and hands the client new headers when the token changes.

import { execFile } from "node:child_process";
import { homedir } from "node:os";
import { delimiter, join } from "node:path";
import { PLUGIN_ROOT } from "./plugin-files.ts";

// gcloud mints a new access token on every call, valid for an hour. Applying
// one makes the client reconnect, so a token is kept until it is this old.
const REFRESH_AFTER_MS = 45 * 60 * 1000;
// How often to check the token's age, and to retry while there are no
// credentials yet (for example before gcloud auth application-default login).
const POLL_MS = 4 * 60 * 1000;
const SCRIPT_TIMEOUT_MS = 30 * 1000;
// The longest a running call can hold back new headers: the longest call
// timeout the plugin configures (autocloud's, in .mcp.json). A client can drop
// the end-of-call event (for example for a cancelled call), and without a limit
// the token would then never be renewed.
const MAX_DEFER_MS = 20 * 60 * 1000;

// Where the Google Cloud CLI is usually installed. A desktop app started from
// the Dock or Start menu may not inherit the shell's PATH, so these are added
// after it.
function gcloudDirs(): string[] {
  const home = homedir();
  if (process.platform === "win32") {
    const local = process.env.LOCALAPPDATA ?? join(home, "AppData", "Local");
    return [
      join(local, "Google", "Cloud SDK", "google-cloud-sdk", "bin"),
      join(process.env.ProgramFiles ?? "C:\\Program Files", "Google", "Cloud SDK", "google-cloud-sdk", "bin"),
      join(process.env["ProgramFiles(x86)"] ?? "C:\\Program Files (x86)", "Google", "Cloud SDK", "google-cloud-sdk", "bin"),
    ];
  }
  return [
    join(home, "google-cloud-sdk", "bin"),
    "/opt/homebrew/bin",
    "/opt/homebrew/share/google-cloud-sdk/bin",
    "/usr/local/bin",
    "/usr/local/share/google-cloud-sdk/bin",
    "/snap/bin",
    "/usr/bin",
  ];
}

function runAdcHeaders(): Promise<Record<string, string>> {
  const env = { ...process.env, PATH: [process.env.PATH, ...gcloudDirs()].filter(Boolean).join(delimiter) };
  const windows = process.platform === "win32";
  // cmd.exe /s strips the outer pair of quotes from what follows /c, so the
  // path gets two pairs and is passed verbatim, as Node's own shell option
  // does; otherwise a path with a space, such as C:\Users\First Last\...,
  // splits at the space.
  const [file, args] = windows
    ? ["cmd.exe", ["/d", "/s", "/c", `""${join(PLUGIN_ROOT, "scripts", "adc-headers.cmd")}""`]]
    : ["bash", [join(PLUGIN_ROOT, "scripts", "adc-headers")]];
  const options = { env, timeout: SCRIPT_TIMEOUT_MS, windowsHide: true, windowsVerbatimArguments: windows };
  return new Promise((resolve, reject) => {
    execFile(file, args, options, (error, stdout, stderr) => {
      if (error) {
        reject(new Error(stderr.trim() || error.message));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch {
        // stdout carries an access token, so describe it without quoting it:
        // this message is logged and shown to the user.
        const first = JSON.stringify(stdout.trimStart()[0] ?? "");
        reject(new Error(`scripts/adc-headers printed ${stdout.length} bytes that aren't JSON (starting with ${first}).`));
      }
    });
  });
}

export class GoogleAuth {
  headers: Record<string, string> = {};
  error: string | undefined;
  private fetchedAt = 0;
  private inFlight = 0;
  private refreshDue = false;
  private refreshDueSince = 0;
  private refreshing = false;
  private timer: ReturnType<typeof setInterval> | undefined;
  private readonly onChange: () => void | Promise<void>;

  // onChange is called after new headers are fetched, but never while a call
  // to one of the plugin's servers is running: the client may reconnect the
  // server to apply them, and an operator call can run for 20 minutes. A
  // running call keeps working on the token it started with.
  constructor(onChange: () => void | Promise<void>) {
    this.onChange = onChange;
  }

  // Fetches the first headers. Never throws: on failure, headers stays empty
  // and error says why, so the plugin can still load its skills.
  async start(): Promise<void> {
    await this.fetch();
  }

  // Starts renewing the headers. Calling it again while it runs does nothing.
  startRenewing(): void {
    if (this.timer) return;
    this.timer = setInterval(() => void this.poll(), POLL_MS);
    (this.timer as { unref?: () => void }).unref?.();
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = undefined;
  }

  callStarted(): void {
    this.inFlight++;
  }

  callEnded(): void {
    this.inFlight = Math.max(0, this.inFlight - 1);
    if (this.inFlight === 0 && this.refreshDue) void this.refresh();
  }

  private async poll(): Promise<void> {
    const stale = !this.headers.Authorization || Date.now() - this.fetchedAt >= REFRESH_AFTER_MS;
    if (!stale) return;
    if (this.inFlight > 0) {
      if (!this.refreshDue) {
        this.refreshDue = true;
        this.refreshDueSince = Date.now();
        return;
      }
      if (Date.now() - this.refreshDueSince < MAX_DEFER_MS) return;
      // No call runs longer than MAX_DEFER_MS, so the count is off by a
      // missed end-of-call event.
      this.inFlight = 0;
    }
    await this.refresh();
  }

  // The poll and callEnded can both start a refresh while the other's fetch
  // is still running; one is enough.
  private async refresh(): Promise<void> {
    if (this.refreshing) return;
    this.refreshing = true;
    try {
      this.refreshDue = false;
      this.refreshDueSince = 0;
      if (await this.fetch()) await this.notify();
    } finally {
      this.refreshing = false;
    }
  }

  private async fetch(): Promise<boolean> {
    try {
      this.headers = await runAdcHeaders();
      this.fetchedAt = Date.now();
      this.error = undefined;
      return true;
    } catch (error) {
      this.error = error instanceof Error ? error.message : String(error);
      return false;
    }
  }

  private async notify(): Promise<void> {
    try {
      await this.onChange();
    } catch (error) {
      console.warn("cloud-operator: couldn't apply new credentials:", error);
    }
  }
}
