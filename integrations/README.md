# Gemini Cloud Assist MCP — Integrations

This directory contains CI/CD and platform integrations built on top of the
**Gemini Cloud Assist MCP** server (`https://geminicloudassist.googleapis.com/mcp`).

## Available Integrations

- **[GitHub Integration (`integrations/github/`)](github/README.md)**:
  - **IaC & Code Review Action (`integrations/github/actions/iac-review/`)**:
    GitHub Action that invokes the **Cloud Operator** agent on Pull Requests and
    `/cloud-operator review` comments to review Infrastructure-as-Code (IaC)
    changes and post inline review suggestions or Companion Pull Requests.
