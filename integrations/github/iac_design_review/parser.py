"""Response parser and remediated-file extractor for Cloud Operator Action.

Handles two critical protocol details of `ask_cloud_operator`:
  1. Tool-level failures arrive as HTTP 200 with `result.isError: true`.
  2. Long-running invocations may answer as an SSE stream (`data: ...`) or a
     single JSON-RPC payload.

Also extracts remediated file blocks emitted by the agent and enforces path
sanitization against directory traversal (`..`) and protected `.git/` or
`.github/` paths.
"""

from collections.abc import Mapping, Sequence
import dataclasses
import difflib
import json
import posixpath
import re
from typing import Any

_CONTEXT_ID_MARKER_RE = re.compile(
    r'<!--\s*cloud-operator-context-id:\s*([a-zA-Z0-9_./:-]+)\s*-->'
)

# Matches any fenced code block (3+ backticks) along with an optional preceding
# `File:` heading/label on the line immediately before the opening fence.
# Groups:
#   1: Optional preceding `File:` path (e.g. `### File: main.tf`, `**File:** `a.tf``)
#   2: Opening backtick fence (` ``` ` or longer)
#   3: Fence info string (language tag and optional `title=...` / `:path`)
#   4: Code block body
_CODE_BLOCK_SCAN_RE = re.compile(
    r'(?:(?:^|\n)[ \t]*(?:#{1,6}[ \t]+)?(?:\*\*)?File:\s*(?:\*\*)?[ \t]*'
    r'\[?`?([^`\]\(\)\r\n*]+?)`?\]?(?:\([^\)]*\))?[ \t]*(?:\*\*)?:?[ \t]*\r?\n+)?'
    r'(`{3,})([^\n`]*)\r?\n(.*?\r?\n)[ \t]*\2[ \t]*(?=\r?\n|$)',
    re.DOTALL,
)

# Extracts an inline file path attribute from a fence info string:
#   `hcl title="envs/prod/main.tf"`
#   `terraform:envs/prod/main.tf`
#   `yaml file=k8s/deployment.yaml`
_FENCE_INFO_PATH_RE = re.compile(
    r'^[a-zA-Z0-9_-]*'
    r'(?:\s+(?:title|file|path)=["\']?([^"\'\n`]+)["\']?|:([^\s\n`]+))'
)

# Matches and strips a file header comment on the first line inside a code block:
#   `# File: envs/prod/main.tf`
#   `// File: main.tf`
#   `File: `main.tf``
_LEADING_FILE_HEADER_RE = re.compile(
    r'^(?:[#/*\->\s]*\s*)?File:\s*(?:\*\*)?\s*'
    r'\[?`?([^`\]\(\)\r\n*]+?)`?\]?(?:\([^\)]*\))?\s*(?:\*\*)?:?[ \t]*\r?\n+',
    re.IGNORECASE,
)

# Checks whether a code block contains top-level Terraform declarations.
_TERRAFORM_KEYWORDS_RE = re.compile(
    r'(?m)^\s*(?:resource|module|variable|provider|terraform|locals|output|data)[\s{]'
)

_TERRAFORM_TAGS = frozenset({'hcl', 'terraform', 'tf'})
_NON_TERRAFORM_TAGS = frozenset({
    'mermaid',
    'bash',
    'sh',
    'shell',
    'zsh',
    'python',
    'py',
    'sql',
    'json',
    'yaml',
    'yml',
    'ascii',
    'dot',
    'graphviz',
    'markdown',
    'md',
    'text',
    'txt',
})

# Matches a fenced JSON block containing structured inline PR review comments:
#   ```json title="cloud-operator-inline-comments"
_INLINE_COMMENTS_BLOCK_RE = re.compile(
    r'(?:^|\n)(?:#{1,4}\s*Line-Anchored[^\n]*\n+\s*)?'
    r'(`{3,})(?:json)?\s+(?:title|file|path)=["\']?cloud-operator-inline-comments["\']?'
    r'\s*\n(.*?)\r?\n[ \t]*\1[ \t]*(?=\r?\n|$)',
    re.DOTALL | re.IGNORECASE,
)

_OUTER_CODE_FENCE_RE = re.compile(
    r'^\s*(`{3,})[a-zA-Z0-9_-]*[ \t]*\r?\n(.*?)\r?\n\s*\1\s*$',
    re.DOTALL,
)

_LINE_NUMBER_PREFIX_RE = re.compile(r'^\s*\d+:\s?(.*)$')

_FAILED_TASK_STATES = frozenset({'FAILED', 'CANCELLED', 'REJECTED'})


class McpError(Exception):
  """Raised when `ask_cloud_operator` reports a JSON-RPC or tool error."""

  def __init__(self, code: int, status: str, message: str):
    """Initializes `McpError`.

    Args:
      code: Numeric error code (0 if unspecified).
      status: Canonical status string (e.g., `PERMISSION_DENIED`).
      message: Error message reported by the backend.
    """
    self.code = code
    self.status = status
    self.message = message
    super().__init__(f'{status or code}: {message}')


@dataclasses.dataclass(frozen=True)
class McpAnswer:
  """Parsed response from `ask_cloud_operator`."""

  content: str
  context_id: str | None = None


@dataclasses.dataclass(frozen=True)
class RemediatedFile:
  """A remediated repository file extracted from the agent's review output."""

  path: str
  content: str


@dataclasses.dataclass(frozen=True)
class InlineReviewComment:
  """A line-anchored GitHub Pull Request inline review comment."""

  path: str
  line: int
  body: str
  start_line: int | None = None


def _safe_int(val: Any, default: int = 0) -> int:
  """Safely converts `val` to `int`, returning `default` on non-int or bool."""
  if val is None or isinstance(val, bool):
    return default
  try:
    return int(val)
  except (TypeError, ValueError):
    return default


def parse_sse(raw_body: str) -> str:
  """Extracts the final JSON payload from an SSE response stream.

  Args:
    raw_body: Raw HTTP response body (either plain JSON or `data:` SSE lines).

  Returns:
    JSON string representing the final JSON-RPC response message.

  Raises:
    McpError: If an SSE stream contains only intermediate notifications and no
      terminal `result` or `error` frame.
  """
  if 'data:' not in raw_body:
    return raw_body

  # If the body is already a single JSON object (e.g. a JSON-RPC response whose
  # markdown content contains `data:` inside a Kubernetes ConfigMap snippet),
  # return it directly without splitting on `data:` lines.
  if raw_body.lstrip().startswith('{'):
    parsed_whole = _maybe_json(raw_body)
    if isinstance(parsed_whole, Mapping):
      return raw_body

  chunks: list[str] = []
  for line in raw_body.splitlines():
    stripped = line.strip()
    if stripped.startswith('data:'):
      chunk = stripped[len('data:') :].strip()
      if chunk and chunk != '[DONE]':
        chunks.append(chunk)

  if not chunks:
    return raw_body

  saw_json_object = False
  for chunk in reversed(chunks):
    try:
      parsed = json.loads(chunk)
    except json.JSONDecodeError:
      continue
    if isinstance(parsed, Mapping):
      saw_json_object = True
      if 'result' in parsed or 'error' in parsed:
        return chunk

  if saw_json_object:
    raise McpError(
        0,
        'UNAVAILABLE',
        'Incomplete SSE stream: no terminal JSON-RPC result or error frame.',
    )

  return chunks[-1]


def _maybe_json(text: str) -> Any:
  """Parses `text` as JSON or returns None if it is not valid JSON."""
  try:
    return json.loads(text)
  except (json.JSONDecodeError, TypeError):
    return None


def _extract_text_parts(result_map: Mapping[str, Any]) -> list[str]:
  """Collects text strings from `result.content` items."""
  parts: list[str] = []
  content_list = result_map.get('content')
  if not isinstance(content_list, Sequence):
    return parts
  for item in content_list:
    if isinstance(item, Mapping) and item.get('type') == 'text':
      text = item.get('text')
      if isinstance(text, str) and text:
        parts.append(text)
  return parts


def _raise_for_failed_task_state(
    mapping: Mapping[str, Any], fallback_message: str = ''
) -> None:
  """Raises `McpError` if `task_state` or `taskState` is in a failure state."""
  raw_state = mapping.get('task_state') or mapping.get('taskState')
  if not isinstance(raw_state, str):
    return
  state = raw_state.strip().upper()
  if state in _FAILED_TASK_STATES:
    msg = (
        str(mapping.get('content') or fallback_message or '').strip()
        or f'Cloud Operator task ended in state {state}.'
    )
    raise McpError(0, f'TASK_{state}', msg)


def _deduplicate_content_chunks(chunks: Sequence[str]) -> list[str]:
  """Deduplicates identical or cumulative text chunks in `result.content`."""
  cleaned = [c.strip() for c in chunks if c and c.strip()]
  if not cleaned:
    return []
  deduped: list[str] = []
  for chunk in cleaned:
    if not deduped or deduped[-1] != chunk:
      deduped.append(chunk)
  if len(deduped) > 1:
    last = deduped[-1]
    if all(prev in last for prev in deduped[:-1]):
      return [last]
  return deduped


def raise_for_tool_error(result_map: Mapping[str, Any]) -> None:
  """Raises `McpError` if `result.isError` is truthy.

  Args:
    result_map: The `result` dictionary from a JSON-RPC `tools/call` response.

  Raises:
    McpError: When `result_map.get('isError')` is True.
  """
  if not result_map.get('isError'):
    return

  code = 0
  status = ''
  message = ''
  for text in _extract_text_parts(result_map):
    parsed = _maybe_json(text)
    if isinstance(parsed, Mapping) and isinstance(parsed.get('error'), Mapping):
      err = parsed['error']
      code = _safe_int(err.get('code'), 0)
      status = str(err.get('status', '') or '')
      message = str(err.get('message', '') or '')
      details = err.get('details')
      if isinstance(details, Sequence):
        for detail in details:
          if isinstance(detail, Mapping) and detail.get('detail'):
            message = f"{message} {detail['detail']}".strip()
      break
    if not message:
      message = text

  raise McpError(code, status, message.strip() or 'Unknown MCP tool error.')


def extract_answer(payload: Mapping[str, Any]) -> McpAnswer:
  """Extracts the text content and `context_id` from a JSON-RPC response.

  Args:
    payload: Decoded JSON-RPC response dictionary.

  Returns:
    `McpAnswer` with `content` and optional `context_id`.

  Raises:
    McpError: If the payload contains a JSON-RPC or tool-level error, if
      `task_state` indicates a failed/cancelled/rejected task, or if the
      response content is empty.
  """
  if 'error' in payload and isinstance(payload['error'], Mapping):
    err = payload['error']
    raise McpError(
        _safe_int(err.get('code'), 0),
        str(err.get('status', '') or ''),
        str(err.get('message', 'JSON-RPC error')),
    )

  result_map = payload.get('result')
  if not isinstance(result_map, Mapping):
    raise McpError(0, '', 'Malformed MCP response: missing `result` object.')

  raise_for_tool_error(result_map)
  _raise_for_failed_task_state(result_map)

  structured = result_map.get('structuredContent')
  if isinstance(structured, Mapping):
    _raise_for_failed_task_state(structured)
    if structured.get('content'):
      context_id = (
          structured.get('context_id') or structured.get('contextId') or None
      )
      return McpAnswer(
          content=str(structured['content']).strip(),
          context_id=str(context_id) if context_id else None,
      )

  content_chunks: list[str] = []
  context_id_val: str | None = None
  for text in _extract_text_parts(result_map):
    parsed = _maybe_json(text)
    if isinstance(parsed, Mapping):
      _raise_for_failed_task_state(parsed)
      inner = (
          parsed['structuredContent']
          if isinstance(parsed.get('structuredContent'), Mapping)
          else parsed
      )
      _raise_for_failed_task_state(inner)
      if 'content' in inner or 'context_id' in inner or 'contextId' in inner:
        if inner.get('content'):
          content_chunks.append(str(inner['content']))
        cand = inner.get('context_id') or inner.get('contextId')
        if cand and not context_id_val:
          context_id_val = str(cand)
      else:
        content_chunks.append(text)
    else:
      content_chunks.append(text)

  if not context_id_val:
    top_cand = result_map.get('context_id') or result_map.get('contextId')
    if top_cand:
      context_id_val = str(top_cand)

  combined = '\n\n'.join(_deduplicate_content_chunks(content_chunks))
  if not combined:
    raise McpError(0, '', 'AutoCloud returned an empty response.')
  return McpAnswer(content=combined, context_id=context_id_val)


def sanitize_relative_repo_path(raw_path: str) -> str:
  """Validates and normalizes a repository-relative file path.

  Rejects absolute paths, parent-directory traversals (`..`), backslashes, and
  protected `.git` or `.github` path segments anywhere in the path.

  Args:
    raw_path: Candidate file path extracted from LLM markdown output.

  Returns:
    Normalized POSIX relative path within the repository.

  Raises:
    ValueError: If the path is unsafe or targets protected directories.
  """
  cleaned = raw_path.strip().replace('\\', '/')
  if not cleaned or cleaned.startswith('/'):
    raise ValueError(f'Path must be non-empty and relative: {raw_path!r}')

  normalized = posixpath.normpath(cleaned)
  if (
      normalized == '.'
      or normalized == '..'
      or normalized.startswith('../')
      or '/..' in normalized
  ):
    raise ValueError(f'Path traversal rejected: {raw_path!r}')

  if any(seg in ('.git', '.github') for seg in normalized.split('/')):
    raise ValueError(
        f'Protected repository metadata path rejected: {raw_path!r}'
    )
  return normalized


def _strip_line_number_prefixes(code_text: str) -> str:
  """Strips accidental `1: ` line-number prefixes from LLM code blocks."""
  lines = code_text.splitlines()
  non_empty = [line for line in lines if line.strip()]
  if not non_empty:
    return code_text
  prefixed_count = sum(
      1 for line in non_empty if _LINE_NUMBER_PREFIX_RE.match(line)
  )
  if prefixed_count * 2 <= len(non_empty):
    return code_text
  stripped_lines: list[str] = []
  for line in lines:
    match = _LINE_NUMBER_PREFIX_RE.match(line)
    stripped_lines.append(match.group(1) if match else line)
  trailing_nl = '\n' if code_text.endswith('\n') else ''
  return '\n'.join(stripped_lines) + trailing_nl


def _join_grouped_blocks(
    grouped: Mapping[str, list[str]], order: Sequence[str]
) -> list[RemediatedFile]:
  """Joins one or more code blocks per file path in order of appearance."""
  results: list[RemediatedFile] = []
  for path in order:
    blocks = grouped.get(path, [])
    if not blocks:
      continue
    if len(blocks) == 1:
      content = blocks[0]
    else:
      content = '\n\n'.join(b.strip('\n') for b in blocks) + '\n'
    results.append(RemediatedFile(path=path, content=content))
  return results


def extract_remediated_files(markdown_text: str) -> list[RemediatedFile]:
  """Extracts remediated file blocks from the AutoCloud Operator's response.

  Scans all fenced code blocks in document order using a 3-tier strategy
  aligned with `adcscorer.go`:
    1. Explicitly named file blocks via inline fence attributes (`title="..."`,
       `file=...`, `path=...`, `:path`), preceding `File:` headings/labels
       (`### File: main.tf`, `**File:** `main.tf``), or a first-line `# File:`
       comment inside the code block.
    2. Fenced `hcl`/`terraform`/`tf` blocks containing Terraform syntax
       (defaulting to `main.tf` when no file name is specified).
    3. Generic/untagged fenced blocks containing Terraform syntax keywords
       (defaulting to `main.tf`).

  Unsafe paths are skipped. When multiple blocks target the same file path,
  their contents are joined in order of appearance.

  Args:
    markdown_text: Full markdown response from `ask_cloud_operator`.

  Returns:
    Ordered list of validated `RemediatedFile` objects.
  """
  explicit_grouped: dict[str, list[str]] = {}
  explicit_order: list[str] = []

  tf_tagged_grouped: dict[str, list[str]] = {}
  tf_tagged_order: list[str] = []

  candidate_grouped: dict[str, list[str]] = {}
  candidate_order: list[str] = []

  for match in _CODE_BLOCK_SCAN_RE.finditer(markdown_text):
    preceding_file = (match.group(1) or '').strip()
    info_str = (match.group(3) or '').strip()
    raw_body = match.group(4) or ''

    info_path = ''
    info_match = _FENCE_INFO_PATH_RE.match(info_str)
    if info_match:
      info_path = (info_match.group(1) or info_match.group(2) or '').strip()

    lang_token = info_str.split()[0].split(':')[0].lower() if info_str else ''

    leading_path = ''
    leading_match = _LEADING_FILE_HEADER_RE.match(raw_body)
    if leading_match:
      leading_path = (leading_match.group(1) or '').strip()
      raw_body = raw_body[leading_match.end() :]

    raw_path = info_path or preceding_file or leading_path
    if raw_path == 'cloud-operator-inline-comments':
      continue

    code_body = _strip_line_number_prefixes(raw_body)
    if not code_body.strip():
      continue

    if raw_path:
      try:
        safe_path = sanitize_relative_repo_path(raw_path)
      except ValueError:
        continue
      if safe_path not in explicit_grouped:
        explicit_order.append(safe_path)
        explicit_grouped[safe_path] = []
      explicit_grouped[safe_path].append(code_body)
    elif lang_token in _TERRAFORM_TAGS:
      if _TERRAFORM_KEYWORDS_RE.search(code_body):
        if 'main.tf' not in tf_tagged_grouped:
          tf_tagged_order.append('main.tf')
          tf_tagged_grouped['main.tf'] = []
        tf_tagged_grouped['main.tf'].append(code_body)
    elif lang_token not in _NON_TERRAFORM_TAGS:
      if _TERRAFORM_KEYWORDS_RE.search(code_body):
        if 'main.tf' not in candidate_grouped:
          candidate_order.append('main.tf')
          candidate_grouped['main.tf'] = []
        candidate_grouped['main.tf'].append(code_body)

  if explicit_order:
    return _join_grouped_blocks(explicit_grouped, explicit_order)
  if tf_tagged_order:
    return _join_grouped_blocks(tf_tagged_grouped, tf_tagged_order)
  if candidate_order:
    return _join_grouped_blocks(candidate_grouped, candidate_order)
  return []


def extract_inline_comments(markdown_text: str) -> list[InlineReviewComment]:
  """Extracts structured inline PR review comments from the agent's response.

  Parses `title="cloud-operator-inline-comments"` JSON code blocks containing a
  list of comment objects (`path`, `line`, optional `start_line`, `body`, and
  optional `suggestion`).

  Args:
    markdown_text: Full markdown response from `ask_cloud_operator`.

  Returns:
    List of validated `InlineReviewComment` objects.
  """
  comments: list[InlineReviewComment] = []
  for match in _INLINE_COMMENTS_BLOCK_RE.finditer(markdown_text):
    raw_json = match.group(2).strip()
    parsed = _maybe_json(raw_json)
    if isinstance(parsed, Mapping) and isinstance(
        parsed.get('comments'), Sequence
    ):
      items = parsed['comments']
    elif isinstance(parsed, Sequence):
      items = parsed
    else:
      continue

    for item in items:
      if not isinstance(item, Mapping):
        continue
      raw_path = str(item.get('path') or item.get('file') or '').strip()
      try:
        safe_path = sanitize_relative_repo_path(raw_path)
      except ValueError:
        continue
      raw_line = item.get('line')
      if isinstance(raw_line, bool):
        continue
      line = _safe_int(raw_line, 0)
      if line < 1:
        continue

      start_line_val: int | None = None
      raw_start = item.get('start_line')
      if raw_start is not None and not isinstance(raw_start, bool):
        cand_start = _safe_int(raw_start, 0)
        if 1 <= cand_start < line:
          start_line_val = cand_start
        elif cand_start > line >= 1:
          start_line_val = line
          line = cand_start

      body = str(item.get('body') or item.get('comment') or '').strip()
      suggestion = item.get('suggestion')
      if isinstance(suggestion, str) and '```suggestion' not in body:
        outer_match = _OUTER_CODE_FENCE_RE.match(suggestion)
        unwrapped_sugg = outer_match.group(2) if outer_match else suggestion
        clean_sugg = _strip_line_number_prefixes(unwrapped_sugg).rstrip('\n')
        body = (
            f'{body}\n\n```suggestion\n{clean_sugg}\n```'
            if body
            else f'```suggestion\n{clean_sugg}\n```'
        )
      if not body:
        continue

      comments.append(
          InlineReviewComment(
              path=safe_path,
              line=line,
              body=body,
              start_line=start_line_val,
          )
      )
  return comments


def clamp_inline_comments_to_files(
    inline_comments: Sequence[InlineReviewComment],
    changed_files: Mapping[str, str],
) -> list[InlineReviewComment]:
  """Clamps inline comment line numbers to the actual line count of each file.

  If an LLM slightly miscounts lines near the end of a file (e.g. emitting
  `start_line=21, line=25` for a 23-line file), this shifts and clamps the
  line range into `[1, max_line]` so GitHub's Pull Request Review API does not
  reject the entire review batch with HTTP 422.

  Args:
    inline_comments: Candidate `InlineReviewComment` items.
    changed_files: Mapping of relative file paths to file content strings.

  Returns:
    List of `InlineReviewComment` items with line numbers clamped to file bounds.
  """
  clamped: list[InlineReviewComment] = []
  for item in inline_comments:
    file_text = changed_files.get(item.path)
    if file_text is None:
      clamped.append(item)
      continue
    max_line = len(file_text.splitlines())
    if max_line < 1:
      continue
    if item.line > max_line:
      overshoot = item.line - max_line
      new_line = max_line
      new_start_line: int | None = None
      if item.start_line is not None:
        shifted_start = max(1, item.start_line - overshoot)
        if shifted_start < new_line:
          new_start_line = shifted_start
      clamped.append(
          InlineReviewComment(
              path=item.path,
              line=new_line,
              body=item.body,
              start_line=new_start_line,
          )
      )
    else:
      clamped.append(item)
  return clamped


def build_inline_comments_from_remediated_files(
    original_files: Mapping[str, str],
    remediated_files: Sequence[RemediatedFile],
) -> list[InlineReviewComment]:
  """Computes line-anchored GitHub `suggestion` comments by diffing files.

  When the agent emits complete remediated file blocks (`title="<path>"`), this
  function diffs each remediated file against its original PR content and builds
  inline review comments with native GitHub ````suggestion` blocks anchored to
  the exact 1-based line ranges in the existing PR.

  Args:
    original_files: Mapping of relative file paths to original PR file contents.
    remediated_files: Sequence of `RemediatedFile` objects from the agent.

  Returns:
    List of `InlineReviewComment` objects with GitHub ````suggestion` blocks.
  """
  inline_comments: list[InlineReviewComment] = []
  for rem in remediated_files:
    orig_text = original_files.get(rem.path)
    if orig_text is None:
      continue
    orig_lines = orig_text.splitlines()
    rem_lines = rem.content.splitlines()
    if orig_lines == rem_lines or not orig_lines:
      continue

    matcher = difflib.SequenceMatcher(a=orig_lines, b=rem_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
      if tag == 'equal':
        continue
      replacement = '\n'.join(rem_lines[j1:j2])
      if tag in ('replace', 'delete'):
        start_1 = i1 + 1
        end_1 = max(start_1, i2)
        start_line = start_1 if start_1 < end_1 else None
        line = end_1
        sugg_body = (
            '**Cloud Operator Suggested Remediation:**\n'
            f'```suggestion\n{replacement}\n```'
        )
      else:
        # Pure insertion (`tag == 'insert'`): anchor to the line at i1 (or 1)
        # and include that anchor line in the suggestion block so GitHub
        # replaces 1 line with (anchor line + inserted lines).
        anchor_idx = min(max(i1 - 1, 0), len(orig_lines) - 1)
        line = anchor_idx + 1
        start_line = None
        if i1 == 0:
          combined = (
              f'{replacement}\n{orig_lines[0]}'
              if replacement
              else orig_lines[0]
          )
        else:
          combined = (
              f'{orig_lines[anchor_idx]}\n{replacement}'
              if replacement
              else orig_lines[anchor_idx]
          )
        sugg_body = (
            '**Cloud Operator Suggested Addition:**\n'
            f'```suggestion\n{combined}\n```'
        )

      inline_comments.append(
          InlineReviewComment(
              path=rem.path,
              line=line,
              body=sugg_body,
              start_line=start_line,
          )
      )
  return inline_comments


def strip_inline_comments_json_block(markdown_text: str) -> str:
  """Removes the machine-readable `cloud-operator-inline-comments` block."""
  cleaned = _INLINE_COMMENTS_BLOCK_RE.sub('', markdown_text).strip()
  return cleaned or markdown_text.strip()


def embed_context_id_marker(
    comment_body: str, context_id: str | None
) -> str:
  """Appends a hidden HTML comment marker with the Cloud Operator `context_id`.

  Args:
    comment_body: Markdown text to post on the GitHub PR.
    context_id: Optional Cloud Operator conversation ID returned by MCP. When
      None, `comment_body` is returned unchanged.

  Returns:
    Markdown comment string with embedded `<!-- cloud-operator-context-id: ... -->`.
  """
  if not context_id:
    return comment_body
  return f'{comment_body.rstrip()}\n\n<!-- cloud-operator-context-id: {context_id} -->'


def extract_context_id_marker(comments: Sequence[str]) -> str | None:
  """Finds the most recent AutoCloud `context_id` from GitHub PR comments.

  Args:
    comments: Sequence of PR comment body strings in chronological order.

  Returns:
    The latest `context_id` string if present, or None if not found.
  """
  for body in reversed(comments):
    match = _CONTEXT_ID_MARKER_RE.search(body)
    if match:
      return match.group(1)
  return None
