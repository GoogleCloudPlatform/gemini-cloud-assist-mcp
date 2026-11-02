"""HTTPS MCP client and prompt builder for `ask_cloud_operator`."""

from collections.abc import Mapping, Sequence
import json
import re
import urllib.parse
import uuid

from absl import logging
import requests

from iac_design_review import auth
from iac_design_review import parser

DEFAULT_PROD_MCP_URL = 'https://geminicloudassist.googleapis.com/mcp'
DEFAULT_STAGING_MCP_URL = (
    'https://staging-geminicloudassist.sandbox.googleapis.com/mcp'
)
DEFAULT_AUTOPUSH_MCP_URL = (
    'https://autopush-geminicloudassist.sandbox.googleapis.com/mcp'
)

_ALLOWED_MCP_HOST_RE = re.compile(
    r'^(?:geminicloudassist\.googleapis\.com|'
    r'[a-z0-9-]+-geminicloudassist\.sandbox\.googleapis\.com)$'
)
_BACKTICK_RUN_RE = re.compile(r'`+')

_CONNECT_TIMEOUT_SECONDS = 15
_READ_TIMEOUT_SECONDS = 1500
_MAX_HTTP_ERROR_DETAIL_CHARS = 300


class McpTransportError(RuntimeError):
  """Raised on HTTP or transport-level failures calling the MCP endpoint."""

  def __init__(self, message: str, status_code: int | None = None):
    """Initializes `McpTransportError`.

    Args:
      message: Human-readable transport error description.
      status_code: Optional HTTP status code if an HTTP response was received.
    """
    self.status_code = status_code
    super().__init__(message)


def _validate_mcp_url(mcp_url: str) -> None:
  """Validates that `mcp_url` uses HTTPS and targets an official GCA MCP host.

  Args:
    mcp_url: Candidate MCP endpoint URL.

  Raises:
    ValueError: If the URL scheme is not `https` or the hostname is not an
      allowed Gemini Cloud Assist endpoint.
  """
  parsed = urllib.parse.urlsplit(mcp_url.strip())
  if parsed.scheme != 'https' or not parsed.hostname:
    raise ValueError(f'mcp_url must start with https://, got {mcp_url!r}')
  host = parsed.hostname.lower()
  if not _ALLOWED_MCP_HOST_RE.match(host):
    raise ValueError(
        f'Untrusted mcp_url host {host!r}; expected '
        'geminicloudassist.googleapis.com or '
        '*-geminicloudassist.sandbox.googleapis.com.'
    )


def _extract_http_error_detail(response: requests.Response) -> str:
  """Extracts a concise diagnostic detail string from a non-200 HTTP response."""
  raw_text = (response.text or '').strip()
  if not raw_text:
    return ''
  try:
    parsed = json.loads(raw_text)
  except json.JSONDecodeError:
    parsed = None
  if isinstance(parsed, Mapping):
    err = parsed.get('error')
    if isinstance(err, Mapping):
      status = str(err.get('status') or '').strip()
      msg = str(err.get('message') or '').strip()
      if status and msg:
        return f'{status}: {msg}'[:_MAX_HTTP_ERROR_DETAIL_CHARS]
      if msg:
        return msg[:_MAX_HTTP_ERROR_DETAIL_CHARS]
  single_line = ' '.join(raw_text.split())
  return single_line[:_MAX_HTTP_ERROR_DETAIL_CHARS]


def build_pr_review_prompt(
    *,
    project_id: str,
    repo_full_name: str,
    pr_number: int,
    pr_title: str,
    changed_files: Mapping[str, str],
    pr_mode: str = 'inline_comments',
) -> str:
  """Constructs the Option 1 IaC & code review prompt for `ask_cloud_operator`.

  Bundles modified repository files inline and instructs the AutoCloud
  Operator agent to evaluate changes against Google Best Practices and emit
  inline review comments and/or complete remediated files.

  Args:
    project_id: Target GCP project ID (e.g., `my-gcp-project`).
    repo_full_name: GitHub `owner/repo` identifier.
    pr_number: Pull Request number.
    pr_title: Pull Request title.
    changed_files: Mapping of relative file paths to full file contents.
    pr_mode: Delivery mode (`inline_comments`, `companion_pr`, `comment_only`).

  Returns:
    Formatted prompt string for `ask_cloud_operator`.
  """
  file_sections: list[str] = []
  for rel_path, file_content in changed_files.items():
    lines = file_content.splitlines()
    if pr_mode == 'inline_comments':
      body_text = '\n'.join(
          f'{idx}: {line}' for idx, line in enumerate(lines, start=1)
      )
    else:
      body_text = '\n'.join(lines)
    max_backticks = max(
        (len(m.group(0)) for m in _BACKTICK_RUN_RE.finditer(file_content)),
        default=0,
    )
    fence = '`' * max(3, max_backticks + 1)
    file_sections.append(
        f'### Existing File: `{rel_path}` ({len(lines)} lines)\n'
        f'{fence}\n{body_text}\n{fence}'
    )
  bundled_files_str = '\n\n'.join(file_sections)

  inline_instr = ''
  if pr_mode == 'inline_comments':
    inline_instr = (
        '3. A fenced JSON block (` ```json '
        'title="cloud-operator-inline-comments"`) '
        'containing a JSON array of line-anchored inline comments for the PR '
        'diff using this schema:\n'
        '```json\n'
        '[\n'
        '  {\n'
        '    "finding_id": 1,\n'
        '    "change_index": 1,\n'
        '    "total_changes_for_finding": 2,\n'
        '    "path": "main.tf",\n'
        '    "start_line": 65,\n'
        '    "line": 65,\n'
        '    "title": "Restrict Cloud Run ingress to Internal Load Balancer",\n'
        '    "severity": "High",\n'
        '    "body": "Crisp 1-2 sentence explanation of the issue and fix '
        '(do NOT repeat the Rule ID in parentheses here).",\n'
        '    "guideline_label": "Cloud Run Ingress Settings",\n'
        '    "guideline_url": '
        '"https://cloud.google.com/run/docs/securing/ingress",\n'
        '    "rule_id": "run_ingress_settings (constraints/run.allowedIngress)",\n'
        '    "resource": "module.cloud_run",\n'
        '    "key_changes": [],\n'
        '    "disruptive_warning": "Explain if the change breaks traffic, '
        'rejects legacy ACLs, or recreates stateful resources (or empty '
        'string).",\n'
        '    "cost_important": "Explain if the change increases billing or '
        'storage costs (or empty string).",\n'
        '    "action_required_caution": "Explain if the suggestion contains a '
        'placeholder value like \\"example.com\\" that must be edited before '
        'applying (or empty string).",\n'
        '    "suggestion": "  ingress                = '
        '\\"INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER\\""\n'
        '  }\n'
        ']\n'
        '```\n'
        '   - Populate `key_changes` with a list of bullet strings only when '
        'multiple attributes are updated in the same hunk; otherwise use '
        '`[]`.\n'
        '   - Link multi-hunk or multi-file fixes to their parent summary '
        'table row using `finding_id`, `change_index`, and '
        '`total_changes_for_finding` (e.g., `1/2` and `2/2`).\n'
        '   - Each input file line below is prefixed with `<line_number>: ` '
        'for exact 1-based line referencing—do NOT include `<line_number>: ` '
        'prefixes inside your remediated file blocks or `suggestion` code.\n'
    )

  summary_template = (
      '### Autocloud identified <N> risks in your Terraform\n\n'
      '✅ **[Test passed]** The proposed fixes are validated against '
      '**Terraform <vX.Y.Z> Validate and Plan** in an isolated sandbox.\n\n'
      '| Severity | Category | Finding & Affected Locations | Guidelines |\n'
      '| :--- | :--- | :--- | :--- |\n'
      '| 🔴 **High** | 🔒 Security | **#1. <Short finding title>** '
      '`⚠️ Disruptive`<br/><sub>2 inline comments: `main.tf:L65`, '
      '`outputs.tf:L6–10`</sub> | **Org Policy · Google Policy**<br/>'
      '[<Rule or Doc Name>](<https://...>) |\n'
      '| 🟠 **Medium** | 🔒 Security | **#2. <Short finding title>** '
      '`⚠️ Disruptive` `🛠️ Action Required`<br/><sub>2 inline comments: '
      '`main.tf:L104–106`, `main.tf:L126–129`</sub> | **Google Policy**<br/>'
      '[<Rule or Doc Name>](<https://...>) |\n\n'
      '---\n'
      'ℹ️ **Run / Session ID:** `<session_or_trace_id>`\n'
      '👇 **Detailed inline comments and 1-click code suggestions are added '
      'on the affected files below.**'
  )

  return (
      f'Review Pull Request #{pr_number} ("{pr_title}") in GitHub repository '
      f'`{repo_full_name}` against Google Cloud project `{project_id}`.\n\n'
      'IaC Review: Review Terraform against Google Best Practices and generate '
      'improvements regarding IaC best practices, security posture, and '
      'organization policies.\n\n'
      'Provide your response using the following structure:\n'
      '1. A concise top-level Pull Request review summary following this '
      'exact Markdown template (do NOT include a `# Pull Request Review` '
      'title header, repository/project metadata block, duplicate `Executive '
      'Summary` or `Detailed Findings & Recommendations` prose lists, '
      'disconnected `### References` sections, or internal tool error codes '
      'such as `DEGRADED` or `POLICY_RETRIEVAL_FAILED`):\n\n'
      f'{summary_template}\n\n'
      '   - Sort rows by severity (`🔴 **High**`, `🟠 **Medium**`, '
      '`🟡 **Low**`).\n'
      '   - Add inline status pills `` `⚠️ Disruptive` `` (when a change '
      'can disrupt traffic, ACLs, or stateful resources) and/or '
      '`` `🛠️ Action Required` `` (when a placeholder value must be '
      'replaced before applying) next to the finding title.\n'
      '   - In `Guidelines`, always label the policy source (`**Org Policy**`, '
      '`**Google Policy**`, `**Org Policy · Google Policy**`, or '
      '`**Internal Policy**`) followed by `<br/>` and a clickable doc link '
      '`[<Rule or Doc Name>](<https://...>)` (or the constraint/policy label '
      'if no URL applies).\n'
      '   - If 0 issues or policy violations are found, output only:\n'
      '     `✅ **No issues found** — All changes validated against '
      '**Terraform <vX.Y.Z> Validate and Terraform Plan**. No policy '
      'violations detected.`\n'
      '2. The COMPLETE remediated content for each modified file that needs '
      'changes, formatted inside a fenced code block with `title="<path>"` '
      '(for example: ```hcl title="envs/prod/main.tf"). These blocks are '
      'automatically extracted and stripped from the top-level summary '
      'comment.\n'
      f'{inline_instr}\n'
      f'## Modified Files in PR #{pr_number}\n\n{bundled_files_str}'
  )


def build_issue_implementation_prompt(
    *,
    project_id: str,
    repo_full_name: str,
    issue_number: int,
    issue_title: str,
    issue_body: str,
    issue_labels: Sequence[str] = (),
    comment_body: str = '',
    repo_files: Mapping[str, str],
) -> str:
  """Constructs an unopinionated issue implementation prompt for the operator.

  Passes the user's GitHub issue context (whether a feature request or a bug
  report), optional follow-up comment, and existing repository files directly to
  `ask_cloud_operator` so the model can infer intent and emit complete created
  or modified files for Companion PR creation.

  Args:
    project_id: Target GCP project ID (e.g., `my-gcp-project`).
    repo_full_name: GitHub `owner/repo` identifier.
    issue_number: GitHub Issue number.
    issue_title: GitHub Issue title.
    issue_body: GitHub Issue markdown description.
    issue_labels: Optional sequence of label names attached to the issue.
    comment_body: Optional follow-up `/cloud-operator implement` comment text.
    repo_files: Mapping of relative file paths to existing file contents.

  Returns:
    Formatted prompt string for `ask_cloud_operator`.
  """
  cleaned_labels = [lbl.strip() for lbl in issue_labels if lbl.strip()]
  labels_str = ', '.join(cleaned_labels) if cleaned_labels else 'None'
  description_text = issue_body.strip() or '_(No description provided.)_'

  comment_section = ''
  if comment_body.strip():
    comment_section = (
        f'### Follow-Up Issue Comment\n{comment_body.strip()}\n\n'
    )

  if repo_files:
    file_sections: list[str] = []
    for rel_path, file_content in repo_files.items():
      lines = file_content.splitlines()
      body_text = '\n'.join(lines)
      max_backticks = max(
          (len(m.group(0)) for m in _BACKTICK_RUN_RE.finditer(file_content)),
          default=0,
      )
      fence = '`' * max(3, max_backticks + 1)
      file_sections.append(
          f'### Existing File: `{rel_path}` ({len(lines)} lines)\n'
          f'{fence}\n{body_text}\n{fence}'
      )
    bundled_files_str = '\n\n'.join(file_sections)
  else:
    bundled_files_str = (
        '_(No existing IaC files found in repository; generate new files as '
        'needed.)_'
    )

  return (
      f'GitHub Issue #{issue_number} in repository `{repo_full_name}` '
      f'(target Google Cloud project: `{project_id}`).\n\n'
      '### Issue Details\n'
      f'- **Title**: {issue_title}\n'
      f'- **Labels**: {labels_str}\n\n'
      f'### Issue Description\n{description_text}\n\n'
      f'{comment_section}'
      '### Output Format Instructions\n'
      'Fulfill the request described in the issue above.\n'
      '1. Provide a clear markdown explanation of your analysis and the '
      'changes made.\n'
      '2. If creating new files or modifying existing files in the repository, '
      'output the COMPLETE file content for each created or modified file '
      'inside a fenced code block with `title="<relative/path/to/file>"` '
      '(for example: ```hcl title="main.tf") so the GitHub Action can commit '
      'the changes and open a Pull Request.\n\n'
      f'## Existing Repository Files\n\n{bundled_files_str}'
  )


def _consume_mcp_response_text(response: requests.Response) -> str:
  """Reads SSE or JSON lines from `response`, logging progress notifications.

  Stops reading as soon as a terminal JSON-RPC response (`result` or `error`)
  arrives on an SSE stream so the client never hangs waiting for socket EOF.

  Args:
    response: Open HTTP 200 `requests.Response` from the MCP endpoint.

  Returns:
    Raw response body (or accumulated SSE lines) containing the final JSON-RPC
    response.

  Raises:
    McpTransportError: If an SSE stream closes after emitting progress frames
      without delivering a terminal `result` or `error` JSON-RPC frame.
  """
  collected_lines: list[str] = []
  saw_sse_data = False
  saw_terminal_rpc = False
  for raw_line in response.iter_lines(decode_unicode=False):
    if raw_line is None:
      continue
    line = (
        raw_line.decode('utf-8', errors='replace')
        if isinstance(raw_line, bytes)
        else str(raw_line)
    )
    collected_lines.append(line)
    stripped = line.strip()
    if not stripped.startswith('data:'):
      continue
    chunk = stripped[len('data:') :].strip()
    if not chunk or chunk == '[DONE]':
      continue
    saw_sse_data = True
    try:
      obj = json.loads(chunk)
    except json.JSONDecodeError:
      continue
    if not isinstance(obj, Mapping):
      continue
    if obj.get('method') == 'notifications/progress':
      params = obj.get('params')
      if isinstance(params, Mapping):
        msg = str(params.get('message', '')).strip()
        if msg:
          logging.info('[Cloud Operator Progress] %s', msg)
      continue
    if 'result' in obj or 'error' in obj:
      saw_terminal_rpc = True
      break

  if saw_sse_data and not saw_terminal_rpc:
    raise McpTransportError(
        'SSE stream ended before a terminal JSON-RPC response was received.'
    )

  if collected_lines:
    return '\n'.join(collected_lines)
  return response.text or ''


def ask_cloud_operator(
    *,
    tokens: auth.TokenSource,
    mcp_url: str,
    project_id: str,
    agent_id: str = '',
    user_query: str,
    context_id: str | None = None,
    correlation_id: str | None = None,
) -> parser.McpAnswer:
  """Invokes `ask_cloud_operator` via JSON-RPC over HTTPS/SSE.

  Args:
    tokens: Human Google EUC token source.
    mcp_url: Full HTTPS URL to the Gemini Cloud Assist MCP endpoint.
    project_id: Target GCP project ID (with or without `projects/` prefix).
    agent_id: Optional target AutoCloud Operator agent ID. When empty, defaults
      to the caller's personal agent.
    user_query: Prompt string sent to the operator agent.
    context_id: Optional conversation context ID for multi-turn continuity.
    correlation_id: Optional request ID for log correlation.

  Returns:
    Parsed `parser.McpAnswer` containing `content` and `context_id`.

  Raises:
    ValueError: If `mcp_url` does not use `https://` on an allowed Gemini Cloud
      Assist MCP host, or if `project_id` is empty.
    McpTransportError: On network, non-200 HTTP, incomplete SSE stream, or
      invalid JSON responses.
    parser.McpError: On tool-level or JSON-RPC errors inside HTTP 200.
  """
  _validate_mcp_url(mcp_url)

  clean_project = project_id.strip().removeprefix('projects/').strip()
  if not clean_project:
    raise ValueError('project_id must be non-empty.')

  req_id = correlation_id or str(uuid.uuid4())
  arguments: dict[str, str] = {
      'project': f'projects/{clean_project}',
      'userQuery': user_query,
  }
  if agent_id:
    arguments['agentId'] = agent_id
  if context_id:
    arguments['contextId'] = context_id

  rpc_body = {
      'jsonrpc': '2.0',
      'id': req_id,
      'method': 'tools/call',
      'params': {
          'name': 'ask_cloud_operator',
          'arguments': arguments,
          '_meta': {
              'progressToken': req_id,
          },
      },
  }

  headers = {
      'Authorization': f'Bearer {tokens.token()}',
      'Content-Type': 'application/json',
      'Accept': 'application/json, text/event-stream',
      'X-Goog-User-Project': clean_project,
  }

  logging.info(
      'Calling ask_cloud_operator (project=%s, agent_id=%s, id=%s, chars=%d)',
      clean_project,
      agent_id or '<personal>',
      req_id,
      len(user_query),
  )

  try:
    response = requests.post(
        mcp_url,
        json=rpc_body,
        headers=headers,
        stream=True,
        allow_redirects=False,
        timeout=(_CONNECT_TIMEOUT_SECONDS, _READ_TIMEOUT_SECONDS),
    )
  except requests.RequestException as err:
    raise McpTransportError(
        'Could not reach the AutoCloud MCP endpoint.'
    ) from err

  try:
    if response.status_code != 200:
      detail = _extract_http_error_detail(response)
      suffix = f': {detail}' if detail else '.'
      raise McpTransportError(
          f'AutoCloud MCP endpoint returned HTTP {response.status_code}{suffix}',
          status_code=response.status_code,
      )

    raw_body = _consume_mcp_response_text(response)
  except requests.RequestException as err:
    raise McpTransportError(
        'Connection to AutoCloud MCP endpoint timed out or reset mid-stream.'
    ) from err
  finally:
    response.close()

  json_text = parser.parse_sse(raw_body)
  try:
    payload = json.loads(json_text)
  except json.JSONDecodeError as err:
    raise McpTransportError(
        'AutoCloud MCP endpoint returned non-JSON payload.'
    ) from err

  if not isinstance(payload, Mapping):
    raise McpTransportError('AutoCloud MCP payload root is not a JSON object.')

  return parser.extract_answer(payload)
