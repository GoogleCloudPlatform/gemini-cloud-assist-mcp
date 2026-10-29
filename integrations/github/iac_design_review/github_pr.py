"""Git workspace remediation writer and GitHub REST API client."""

from collections.abc import Sequence
import os
import re
import subprocess
from typing import Any

from absl import logging
import requests

from iac_design_review import config
from iac_design_review import parser

DEFAULT_GITHUB_API_URL = 'https://api.github.com'
_GITHUB_TIMEOUT_SECONDS = 30
_BRANCH_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,199}$')
_REPO_FULL_NAME_RE = re.compile(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$')
_HUNK_HEADER_RE = re.compile(
    r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', re.MULTILINE
)
_IGNORED_WORKSPACE_DIRS = frozenset({
    '.git',
    '.github',
    '.terraform',
    'node_modules',
    '__pycache__',
    '.venv',
    'venv',
    '.tox',
    '.mypy_cache',
    '.pytest_cache',
    'dist',
    'build',
})
_IGNORED_WORKSPACE_FILENAMES = frozenset({
    '.terraform.lock.hcl',
    'package-lock.json',
    'yarn.lock',
    'pnpm-lock.yaml',
    'poetry.lock',
})
_PRIMARY_IAC_EXTENSIONS = frozenset({
    '.tf',
    '.tfvars',
    '.hcl',
    '.tftpl',
    '.yaml',
    '.yml',
    '.json',
})
_SECONDARY_TEXT_EXTENSIONS = frozenset({
    '.sh',
    '.py',
    '.go',
    '.md',
    '.toml',
    '.cfg',
    '.ini',
    '.tpl',
})
_SECONDARY_EXACT_FILENAMES = frozenset({'Dockerfile', 'Makefile'})
_DEFAULT_MAX_COLLECTED_FILES = 50
_DEFAULT_MAX_FILE_BYTES = 128 * 1024
_DEFAULT_MAX_TOTAL_BYTES = 512 * 1024


def parse_patch_right_hunks(patch_text: str) -> list[tuple[int, int]]:
  """Extracts 1-based inclusive `(start_line, end_line)` right-side diff hunks.

  Args:
    patch_text: Unified diff `patch` string returned by GitHub's PR files API.

  Returns:
    List of `(start_line, end_line)` ranges valid on `side: "RIGHT"`.
  """
  hunks: list[tuple[int, int]] = []
  for match in _HUNK_HEADER_RE.finditer(patch_text or ''):
    start_line = int(match.group(1))
    count = int(match.group(2)) if match.group(2) is not None else 1
    if count <= 0:
      continue
    hunks.append((start_line, start_line + count - 1))
  return hunks


def _align_comment_to_hunks(
    entry: dict[str, Any],
    hunks: Sequence[tuple[int, int]],
    *,
    is_added_file: bool = False,
) -> dict[str, Any] | None:
  """Aligns and clamps a serialized inline comment dict to valid PR diff hunks.

  GitHub's Pull Request Review API (`POST /repos/{owner}/{repo}/pulls/{n}/reviews`)
  rejects the entire review request with HTTP 422 if any comment's `line` or
  `start_line` falls outside a diff hunk or spans across two separate hunks.

  Args:
    entry: Serialized GitHub review comment dictionary.
    hunks: Valid right-side `(start_line, end_line)` hunks for `entry['path']`.
    is_added_file: True if `entry['path']` was newly added in the PR (`status ==
      "added"`), meaning `(1, max_hunk_line)` covers the entire file.

  Returns:
    Aligned comment dictionary ready for GitHub's API, or None if the comment
    targets lines outside the PR diff hunks.
  """
  if not hunks:
    return None

  line = int(entry['line'])
  raw_start = entry.get('start_line')
  start_line = int(raw_start) if raw_start is not None else None
  has_suggestion = '```suggestion' in str(entry.get('body', ''))
  max_hunk_line = max(h_end for _, h_end in hunks)

  if line > max_hunk_line:
    if is_added_file and hunks == [(1, max_hunk_line)]:
      overshoot = line - max_hunk_line
      if (
          has_suggestion
          and start_line is not None
          and start_line - overshoot < 1
      ):
        return None
      line = max_hunk_line
      if start_line is not None:
        start_line = max(1, start_line - overshoot)
    elif not has_suggestion and start_line is not None:
      for h_start, h_end in hunks:
        if h_start <= start_line <= h_end:
          line = h_end
          break

  if has_suggestion:
    eff_start = start_line if start_line is not None else line
    for h_start, h_end in hunks:
      if h_start <= eff_start <= line <= h_end:
        aligned = dict(entry)
        aligned['line'] = line
        if start_line is not None and 1 <= start_line < line:
          aligned['start_line'] = start_line
          aligned['start_side'] = 'RIGHT'
        else:
          aligned.pop('start_line', None)
          aligned.pop('start_side', None)
        return aligned
    return None

  for h_start, h_end in hunks:
    if h_start <= line <= h_end:
      aligned = dict(entry)
      aligned['line'] = line
      if start_line is not None:
        clamped_start = max(h_start, min(start_line, line))
        if 1 <= clamped_start < line:
          aligned['start_line'] = clamped_start
          aligned['start_side'] = 'RIGHT'
        else:
          aligned.pop('start_line', None)
          aligned.pop('start_side', None)
      return aligned

  if start_line is not None:
    for h_start, h_end in hunks:
      if h_start <= start_line <= h_end and line > h_end:
        aligned = dict(entry)
        aligned['line'] = h_end
        if 1 <= start_line < h_end:
          aligned['start_line'] = start_line
          aligned['start_side'] = 'RIGHT'
        else:
          aligned.pop('start_line', None)
          aligned.pop('start_side', None)
        return aligned

  return None


class GitHubIntegrationError(RuntimeError):
  """Raised when git operations or GitHub REST API requests fail."""


def validate_branch_name(branch_name: str) -> str:
  """Validates a git branch name against option/command injection.

  Args:
    branch_name: Candidate git branch ref name.

  Returns:
    Validated branch name string.

  Raises:
    ValueError: If `branch_name` contains unsafe characters or `..`.
  """
  cleaned = branch_name.strip()
  if not _BRANCH_NAME_RE.match(cleaned) or '..' in cleaned:
    raise ValueError(f'Unsafe git branch name rejected: {branch_name!r}')
  return cleaned


def validate_repo_full_name(repo_full_name: str) -> str:
  """Validates a GitHub `owner/repo` string.

  Args:
    repo_full_name: Repository identifier in `owner/repo` format.

  Returns:
    Validated `owner/repo` string.

  Raises:
    ValueError: If `repo_full_name` is malformed.
  """
  cleaned = repo_full_name.strip()
  if not _REPO_FULL_NAME_RE.match(cleaned):
    raise ValueError(f'Invalid GitHub repository name: {repo_full_name!r}')
  return cleaned


def companion_branch_for_pr(pr_number: int) -> str:
  """Returns the deterministic Companion PR branch name for `pr_number`."""
  if pr_number <= 0:
    raise ValueError(f'pr_number must be positive, got {pr_number}')
  return f'{config.COMPANION_BRANCH_PREFIX}{pr_number}'


def companion_branch_for_issue(issue_number: int) -> str:
  """Returns the deterministic Companion PR branch name for `issue_number`."""
  if issue_number <= 0:
    raise ValueError(f'issue_number must be positive, got {issue_number}')
  return f'{config.ISSUE_COMPANION_BRANCH_PREFIX}{issue_number}'


def collect_workspace_files(
    workspace_dir: str,
    *,
    max_files: int = _DEFAULT_MAX_COLLECTED_FILES,
    max_file_bytes: int = _DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = _DEFAULT_MAX_TOTAL_BYTES,
) -> dict[str, str]:
  """Collects existing IaC and configuration text files from `workspace_dir`.

  Prioritizes Terraform/HCL/YAML/JSON infrastructure files before auxiliary
  scripts and docs, while skipping `.git`, `.github`, `.terraform`, lockfiles,
  symlinks, binary files, and oversized files.

  Args:
    workspace_dir: Local git checkout root directory.
    max_files: Maximum number of files to collect.
    max_file_bytes: Maximum size in bytes for any single file.
    max_total_bytes: Maximum cumulative size in bytes across collected files.

  Returns:
    Ordered mapping of repository-relative file paths to UTF-8 file contents.

  Raises:
    ValueError: If `workspace_dir` does not exist.
  """
  workspace_real = os.path.realpath(workspace_dir)
  if not os.path.isdir(workspace_real):
    raise ValueError(f'Workspace directory does not exist: {workspace_dir!r}')

  candidates: list[tuple[int, str, str, int]] = []
  for dirpath, dirnames, filenames in os.walk(
      workspace_real, followlinks=False
  ):
    dirnames[:] = sorted(
        d
        for d in dirnames
        if d not in _IGNORED_WORKSPACE_DIRS
        and not os.path.islink(os.path.join(dirpath, d))
    )
    for filename in sorted(filenames):
      if filename in _IGNORED_WORKSPACE_FILENAMES:
        continue
      _, ext = os.path.splitext(filename)
      ext_lower = ext.lower()
      if ext_lower in _PRIMARY_IAC_EXTENSIONS:
        tier = 0
      elif (
          ext_lower in _SECONDARY_TEXT_EXTENSIONS
          or filename in _SECONDARY_EXACT_FILENAMES
      ):
        tier = 1
      else:
        continue

      candidate_abs = os.path.join(dirpath, filename)
      if os.path.islink(candidate_abs) or not os.path.isfile(candidate_abs):
        continue
      real_abs = os.path.realpath(candidate_abs)
      if not real_abs.startswith(workspace_real + os.sep):
        continue

      rel_raw = os.path.relpath(real_abs, workspace_real).replace(os.sep, '/')
      try:
        safe_rel = parser.sanitize_relative_repo_path(rel_raw)
      except ValueError:
        continue

      try:
        file_size = os.path.getsize(real_abs)
      except OSError:
        continue
      if file_size > max_file_bytes:
        logging.warning('Skipping large workspace file (>%dB): %s', max_file_bytes, safe_rel)
        continue

      candidates.append((tier, safe_rel, real_abs, file_size))

  candidates.sort(key=lambda item: (item[0], item[1]))
  collected: dict[str, str] = {}
  total_bytes = 0
  for _, safe_rel, real_abs, file_size in candidates:
    if len(collected) >= max_files:
      break
    if total_bytes + file_size > max_total_bytes:
      continue
    try:
      with open(real_abs, 'rb') as raw_file:
        raw_bytes = raw_file.read()
    except OSError:
      continue
    if b'\x00' in raw_bytes:
      continue
    try:
      text_content = raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
      continue
    collected[safe_rel] = text_content
    total_bytes += file_size

  return collected


def write_remediated_files_safely(
    workspace_dir: str,
    remediated_files: Sequence[parser.RemediatedFile],
) -> list[str]:
  """Writes remediated files inside `workspace_dir` with path traversal guards.

  Resolves both `workspace_dir` and every target path with `os.path.realpath`
  to guarantee symlinks or relative segments cannot escape the repository root.

  Args:
    workspace_dir: Local git checkout root directory.
    remediated_files: Validated `RemediatedFile` items extracted from MCP.

  Returns:
    List of normalized relative paths written to disk.

  Raises:
    ValueError: If any path escapes `workspace_dir` or targets `.git`/`.github`.
    OSError: If file creation fails.
  """
  workspace_real = os.path.realpath(workspace_dir)
  if not os.path.isdir(workspace_real):
    raise ValueError(f'Workspace directory does not exist: {workspace_dir!r}')

  written_paths: list[str] = []
  for item in remediated_files:
    rel_path = parser.sanitize_relative_repo_path(item.path)
    candidate_abs = os.path.join(workspace_real, rel_path)
    parent_real = os.path.realpath(os.path.dirname(candidate_abs))

    if parent_real != workspace_real and not parent_real.startswith(
        workspace_real + os.sep
    ):
      raise ValueError(
          f'Resolved parent directory escapes workspace: {item.path!r}'
      )

    os.makedirs(parent_real, exist_ok=True)
    target_real = os.path.realpath(candidate_abs)
    if not target_real.startswith(workspace_real + os.sep):
      raise ValueError(f'Resolved file path escapes workspace: {item.path!r}')

    if os.path.islink(candidate_abs):
      raise ValueError(f'Refusing to overwrite symlink path: {item.path!r}')

    content = item.content
    if not content.endswith('\n'):
      content = f'{content}\n'

    with open(target_real, 'w', encoding='utf-8') as out_file:
      out_file.write(content)
    written_paths.append(rel_path)

  return written_paths


def _run_git(workspace_dir: str, args: Sequence[str]) -> str:
  """Executes a `git` subcommand safely without a shell."""
  cmd = ['git', *args]
  try:
    completed = subprocess.run(
        cmd,
        cwd=workspace_dir,
        check=True,
        shell=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
  except subprocess.CalledProcessError as err:
    stderr_summary = (err.stderr or '').strip()
    raise GitHubIntegrationError(
        f'git {args[0]} failed (exit {err.returncode}): {stderr_summary}'
    ) from err


def commit_and_push_companion_branch(
    *,
    workspace_dir: str,
    companion_branch: str,
    written_paths: Sequence[str],
    pr_number: int | None = None,
    issue_number: int | None = None,
    push_remote: bool = True,
) -> bool:
  """Creates/updates the companion branch, commits changes, and pushes.

  Args:
    workspace_dir: Local git repository root.
    companion_branch: Companion branch name (`cloud-operator/remediate-pr-<N>`
      or `cloud-operator/issue-<N>`).
    written_paths: Relative file paths written by `write_remediated_files_safely`.
    pr_number: Optional Pull Request number being remediated.
    issue_number: Optional Issue number being implemented.
    push_remote: Whether to push the branch to `origin` (False in dry runs).

  Returns:
    True if at least one file changed and was committed; False if no diff.

  Raises:
    ValueError: If `companion_branch`, `written_paths`, or target numbers fail
      validation.
    GitHubIntegrationError: If any `git` command fails.
  """
  if not written_paths:
    return False
  if pr_number is None and issue_number is None:
    raise ValueError('Either pr_number or issue_number must be provided.')

  safe_branch = validate_branch_name(companion_branch)
  safe_paths = [parser.sanitize_relative_repo_path(p) for p in written_paths]

  _run_git(workspace_dir, ['checkout', '-B', safe_branch])
  _run_git(
      workspace_dir, ['config', 'user.name', 'github-actions[bot]']
  )
  _run_git(
      workspace_dir,
      [
          'config',
          'user.email',
          '41898282+github-actions[bot]@users.noreply.github.com',
      ],
  )
  _run_git(workspace_dir, ['add', '--', *safe_paths])

  status_output = _run_git(
      workspace_dir, ['status', '--porcelain', '--', *safe_paths]
  )
  if not status_output:
    logging.info('Remediated files match HEAD; skipping companion commit.')
    return False

  if issue_number is not None:
    commit_msg = (
        f'feat(cloud-operator): implement changes for Issue #{issue_number}'
    )
  else:
    commit_msg = (
        f'fix(cloud-operator): apply IaC review remediations for PR #{pr_number}'
    )
  _run_git(workspace_dir, ['commit', '-m', commit_msg])

  if push_remote:
    subprocess.run(
        [
            'git',
            'fetch',
            'origin',
            f'refs/heads/{safe_branch}:refs/remotes/origin/{safe_branch}',
        ],
        cwd=workspace_dir,
        check=False,
        shell=False,
        capture_output=True,
        text=True,
    )
    refspec = f'HEAD:refs/heads/{safe_branch}'
    _run_git(
        workspace_dir,
        ['push', '--force-with-lease', 'origin', refspec],
    )
  return True


def checkout_branch(workspace_dir: str, branch_name: str) -> None:
  """Fetches `origin/<branch_name>` and checks out `FETCH_HEAD` detached.

  Args:
    workspace_dir: Local git repository root.
    branch_name: Remote branch name on `origin` (e.g., `main` or
      `cloud-operator/issue-7`).

  Raises:
    ValueError: If `branch_name` fails branch safety validation.
    GitHubIntegrationError: If `git fetch` or `git checkout` fails.
  """
  safe_branch = validate_branch_name(branch_name)
  _run_git(
      workspace_dir,
      [
          'fetch',
          'origin',
          f'refs/heads/{safe_branch}:refs/remotes/origin/{safe_branch}',
      ],
  )
  _run_git(workspace_dir, ['checkout', '--detach', 'FETCH_HEAD'])


def checkout_pr_head(workspace_dir: str, pr_number: int) -> None:
  """Fetches and checks out `refs/pull/<pr_number>/head` in `workspace_dir`.

  On `issue_comment` webhook events (e.g. `/autocloud review`), GitHub Actions
  checks out the repository's default branch (`main`) rather than the PR's head
  commit. Fetching `pull/<pr_number>/head` ensures files added or modified in
  the PR exist on disk before reading workspace files.

  Args:
    workspace_dir: Local git repository root.
    pr_number: Pull Request number.

  Raises:
    ValueError: If `pr_number` is not positive.
    GitHubIntegrationError: If `git fetch` or `git checkout` fails.
  """
  if pr_number <= 0:
    raise ValueError(f'pr_number must be positive, got {pr_number}')
  _run_git(workspace_dir, ['fetch', 'origin', f'pull/{pr_number}/head'])
  _run_git(workspace_dir, ['checkout', '--detach', 'FETCH_HEAD'])


class GitHubClient:
  """Minimal GitHub REST API v3 client using `GITHUB_TOKEN`."""

  def __init__(
      self,
      github_token: str,
      api_base_url: str = DEFAULT_GITHUB_API_URL,
  ):
    """Initializes `GitHubClient`.

    Args:
      github_token: GitHub Actions `GITHUB_TOKEN` or fine-grained token.
      api_base_url: HTTPS base URL for GitHub REST API.

    Raises:
      ValueError: If `github_token` is empty or `api_base_url` is not HTTPS.
    """
    if not github_token or not github_token.strip():
      raise ValueError('github_token must be non-empty.')
    if not api_base_url.startswith('https://'):
      raise ValueError(
          f'api_base_url must start with https://, got {api_base_url!r}'
      )
    self._token = github_token.strip()
    self._api_base_url = api_base_url.rstrip('/')
    self._pr_diff_hunks: dict[
        tuple[str, int], dict[str, list[tuple[int, int]]]
    ] = {}
    self._pr_added_files: dict[tuple[str, int], set[str]] = {}
    self._pr_is_fork: dict[tuple[str, int], bool] = {}

  def _headers(self) -> dict[str, str]:
    """Returns standard GitHub REST API request headers."""
    return {
        'Authorization': f'Bearer {self._token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }

  def _request_json(
      self,
      method: str,
      path: str,
      *,
      params: dict[str, Any] | None = None,
      json_body: dict[str, Any] | None = None,
  ) -> Any:
    """Performs an authenticated HTTPS request to GitHub's REST API."""
    url = f'{self._api_base_url}/{path.lstrip("/")}'
    try:
      response = requests.request(
          method=method,
          url=url,
          headers=self._headers(),
          params=params,
          json=json_body,
          timeout=_GITHUB_TIMEOUT_SECONDS,
      )
    except requests.RequestException as err:
      raise GitHubIntegrationError(
          f'GitHub API network error ({method} {path}).'
      ) from err

    if response.status_code >= 400:
      raise GitHubIntegrationError(
          f'GitHub API {method} {path} returned HTTP {response.status_code}.'
      )

    if not response.text:
      return None
    try:
      return response.json()
    except ValueError as err:
      raise GitHubIntegrationError(
          f'GitHub API {method} {path} returned invalid JSON.'
      ) from err

  def get_pr_metadata(
      self, repo_full_name: str, pr_number: int
  ) -> tuple[str, str]:
    """Fetches `(title, head_ref)` for a Pull Request via GitHub's REST API."""
    safe_repo = validate_repo_full_name(repo_full_name)
    resp = self._request_json(
        'GET',
        f'/repos/{safe_repo}/pulls/{pr_number}',
    )
    if not isinstance(resp, dict):
      return f'PR #{pr_number}', ''
    self._pr_is_fork[(safe_repo, pr_number)] = config.is_fork_pull_request(resp)
    title = str(resp.get('title', '') or f'PR #{pr_number}')
    head_obj = resp.get('head')
    head_ref = (
        str(head_obj.get('ref', ''))
        if isinstance(head_obj, dict)
        else ''
    )
    return title, head_ref

  def is_pr_from_fork(self, repo_full_name: str, pr_number: int) -> bool:
    """Returns True if the Pull Request originates from a forked repository."""
    safe_repo = validate_repo_full_name(repo_full_name)
    cached = self._pr_is_fork.get((safe_repo, pr_number))
    if cached is not None:
      return cached
    resp = self._request_json(
        'GET',
        f'/repos/{safe_repo}/pulls/{pr_number}',
    )
    if not isinstance(resp, dict):
      return False
    is_fork = config.is_fork_pull_request(resp)
    self._pr_is_fork[(safe_repo, pr_number)] = is_fork
    return is_fork

  def list_pr_changed_files(
      self, repo_full_name: str, pr_number: int
  ) -> list[str]:
    """Lists non-deleted repository-relative files changed in a Pull Request."""
    safe_repo = validate_repo_full_name(repo_full_name)
    items = self._request_json(
        'GET',
        f'/repos/{safe_repo}/pulls/{pr_number}/files',
        params={'per_page': 100},
    )
    if not isinstance(items, list):
      return []

    paths: list[str] = []
    hunks_by_path: dict[str, list[tuple[int, int]]] = {}
    added_files: set[str] = set()
    for entry in items:
      if not isinstance(entry, dict):
        continue
      status = str(entry.get('status', '') or '')
      if status == 'removed':
        continue
      filename = str(entry.get('filename', ''))
      try:
        safe_path = parser.sanitize_relative_repo_path(filename)
      except ValueError:
        continue
      paths.append(safe_path)
      if status == 'added':
        added_files.add(safe_path)
      patch_str = str(entry.get('patch', '') or '')
      if patch_str:
        hunks_by_path[safe_path] = parse_patch_right_hunks(patch_str)

    self._pr_diff_hunks[(safe_repo, pr_number)] = hunks_by_path
    self._pr_added_files[(safe_repo, pr_number)] = added_files
    return paths

  def list_issue_comments(
      self, repo_full_name: str, issue_number: int
  ) -> list[str]:
    """Lists chronological comment body strings on an issue or PR."""
    safe_repo = validate_repo_full_name(repo_full_name)
    items = self._request_json(
        'GET',
        f'/repos/{safe_repo}/issues/{issue_number}/comments',
        params={'per_page': 100},
    )
    if not isinstance(items, list):
      return []
    return [
        str(item.get('body', ''))
        for item in items
        if isinstance(item, dict) and item.get('body')
    ]

  def list_pr_review_bodies(
      self, repo_full_name: str, pr_number: int
  ) -> list[str]:
    """Lists chronological Pull Request review body strings on a PR."""
    safe_repo = validate_repo_full_name(repo_full_name)
    items = self._request_json(
        'GET',
        f'/repos/{safe_repo}/pulls/{pr_number}/reviews',
        params={'per_page': 100},
    )
    if not isinstance(items, list):
      return []
    return [
        str(item.get('body', ''))
        for item in items
        if isinstance(item, dict) and item.get('body')
    ]

  def post_issue_comment(
      self, repo_full_name: str, issue_number: int, body: str
  ) -> str:
    """Posts a comment on a GitHub Pull Request or Issue."""
    safe_repo = validate_repo_full_name(repo_full_name)
    resp = self._request_json(
        'POST',
        f'/repos/{safe_repo}/issues/{issue_number}/comments',
        json_body={'body': body},
    )
    if isinstance(resp, dict):
      return str(resp.get('html_url', ''))
    return ''

  def post_pr_review(
      self,
      repo_full_name: str,
      pr_number: int,
      body: str,
      inline_comments: Sequence[parser.InlineReviewComment] = (),
  ) -> str:
    """Posts a Pull Request Review with optional line-anchored inline comments.

    Uses `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews` (`event:
    "COMMENT"`). If GitHub rejects the inline comments array (e.g. HTTP 422 when
    a line number falls outside the PR diff hunk), falls back to posting the
    review summary and inline suggestions in a top-level PR comment so findings
    are never lost.

    Args:
      repo_full_name: GitHub `owner/repo` string.
      pr_number: Pull Request number.
      body: Top-level review summary body (including `context_id` marker).
      inline_comments: Line-anchored `InlineReviewComment` items.

    Returns:
      HTML URL of the created Pull Request review or fallback comment.
    """
    safe_repo = validate_repo_full_name(repo_full_name)
    serialized_comments: list[dict[str, Any]] = []
    for item in inline_comments:
      try:
        safe_path = parser.sanitize_relative_repo_path(item.path)
      except ValueError:
        continue
      if item.line < 1 or not item.body.strip():
        continue
      entry: dict[str, Any] = {
          'path': safe_path,
          'line': item.line,
          'side': 'RIGHT',
          'body': item.body,
      }
      if item.start_line is not None and 1 <= item.start_line < item.line:
        entry['start_line'] = item.start_line
        entry['start_side'] = 'RIGHT'
      serialized_comments.append(entry)

    hunks_by_path = self._pr_diff_hunks.get((safe_repo, pr_number))
    added_files = self._pr_added_files.get((safe_repo, pr_number), set())
    in_diff_comments: list[dict[str, Any]] = []
    out_of_diff_comments: list[dict[str, Any]] = []
    if hunks_by_path is not None:
      for entry in serialized_comments:
        file_hunks = hunks_by_path.get(entry['path'], [])
        aligned = _align_comment_to_hunks(
            entry,
            file_hunks,
            is_added_file=(entry['path'] in added_files),
        )
        if aligned is not None:
          in_diff_comments.append(aligned)
        else:
          out_of_diff_comments.append(entry)
    else:
      in_diff_comments = serialized_comments

    review_body = body
    if out_of_diff_comments:
      context_id = parser.extract_context_id_marker([review_body])
      if context_id:
        review_body = re.sub(
            r'\s*<!--\s*cloud-operator-context-id:\s*[a-zA-Z0-9_./:-]+\s*-->\s*$',
            '',
            review_body,
        ).rstrip()
      extra_sections = [
          review_body,
          '---\n\n### Additional Findings (Outside PR Diff Hunks)',
      ]
      for cmt in out_of_diff_comments:
        loc = (
            f"{cmt['path']}:L{cmt['start_line']}-L{cmt['line']}"
            if 'start_line' in cmt
            else f"{cmt['path']}:L{cmt['line']}"
        )
        extra_sections.append(f"#### `{loc}`\n{cmt['body']}")
      review_body = '\n\n'.join(s for s in extra_sections if s)
      if context_id:
        review_body = parser.embed_context_id_marker(review_body, context_id)

    review_payload: dict[str, Any] = {
        'event': 'COMMENT',
        'body': review_body,
    }
    if in_diff_comments:
      review_payload['comments'] = in_diff_comments

    try:
      resp = self._request_json(
          'POST',
          f'/repos/{safe_repo}/pulls/{pr_number}/reviews',
          json_body=review_payload,
      )
      if isinstance(resp, dict):
        return str(resp.get('html_url', ''))
      return ''
    except GitHubIntegrationError as err:
      if not in_diff_comments:
        raise
      logging.warning(
          'Inline PR review returned %s; falling back to PR comment.', err
      )
      fallback_sections = [review_body]
      for cmt in in_diff_comments:
        loc = (
            f"{cmt['path']}:L{cmt['start_line']}-L{cmt['line']}"
            if 'start_line' in cmt
            else f"{cmt['path']}:L{cmt['line']}"
        )
        fallback_sections.append(f"#### `{loc}`\n{cmt['body']}")
      return self.post_issue_comment(
          safe_repo, pr_number, '\n\n'.join(fallback_sections)
      )

  def has_open_companion_pr(
      self,
      *,
      repo_full_name: str,
      base_branch: str,
      companion_branch: str,
  ) -> bool:
    """Returns True if an open PR already exists from `companion_branch`."""
    safe_repo = validate_repo_full_name(repo_full_name)
    owner = safe_repo.split('/', 1)[0]
    safe_base = validate_branch_name(base_branch)
    safe_head = validate_branch_name(companion_branch)
    existing_prs = self._request_json(
        'GET',
        f'/repos/{safe_repo}/pulls',
        params={
            'head': f'{owner}:{safe_head}',
            'base': safe_base,
            'state': 'open',
        },
    )
    return bool(isinstance(existing_prs, list) and existing_prs)

  def create_or_update_companion_pr(
      self,
      *,
      repo_full_name: str,
      pr_head_branch: str,
      companion_branch: str,
      summary_markdown: str,
      source_pr_number: int | None = None,
      source_issue_number: int | None = None,
      issue_title: str = '',
  ) -> str:
    """Creates or updates a Companion PR for PR remediation or Issue resolution.

    Args:
      repo_full_name: GitHub `owner/repo` string.
      pr_head_branch: Target `base` branch for the PR (contributor's PR branch
        for reviews, or `base_branch` such as `main` for issue implementation).
      companion_branch: Head branch (`cloud-operator/remediate-pr-<N>` or
        `cloud-operator/issue-<N>`).
      summary_markdown: Markdown summary of findings or implemented changes.
      source_pr_number: Original PR number being remediated (Scenario 1).
      source_issue_number: Original Issue number being implemented (Scenario 2).
      issue_title: Optional GitHub Issue title for Scenario 2 PR titles.

    Returns:
      HTML URL of the created or updated Companion PR.

    Raises:
      ValueError: If neither `source_pr_number` nor `source_issue_number` is
        provided, or if repository/branch names fail validation.
    """
    if source_pr_number is None and source_issue_number is None:
      raise ValueError(
          'Either source_pr_number or source_issue_number must be provided.'
      )
    safe_repo = validate_repo_full_name(repo_full_name)
    owner = safe_repo.split('/', 1)[0]
    safe_base = validate_branch_name(pr_head_branch)
    safe_head = validate_branch_name(companion_branch)

    if source_issue_number is not None:
      clean_issue_title = ' '.join(issue_title.split())
      if clean_issue_title:
        title = (
            f'[Cloud Operator] Resolve Issue #{source_issue_number}: '
            f'{clean_issue_title}'
        )[:240]
      else:
        title = f'[Cloud Operator] Resolve Issue #{source_issue_number}'
      body = (
          'Automated Pull Request generated by **Cloud Operator**.\n\n'
          f'Closes #{source_issue_number}\n\n'
          f'{summary_markdown}'
      )
    else:
      title = (
          f'[Cloud Operator] IaC & Code Remediations for PR #{source_pr_number}'
      )
      body = (
          f'Automated Companion PR for #{source_pr_number} generated by '
          '**Cloud Operator**.\n\n'
          f'{summary_markdown}'
      )

    existing_prs = self._request_json(
        'GET',
        f'/repos/{safe_repo}/pulls',
        params={
            'head': f'{owner}:{safe_head}',
            'base': safe_base,
            'state': 'open',
        },
    )
    if isinstance(existing_prs, list) and existing_prs:
      first = existing_prs[0]
      if isinstance(first, dict) and first.get('number'):
        companion_num = int(first['number'])
        updated = self._request_json(
            'PATCH',
            f'/repos/{safe_repo}/pulls/{companion_num}',
            json_body={'title': title, 'body': body},
        )
        if isinstance(updated, dict):
          return str(updated.get('html_url', ''))

    created = self._request_json(
        'POST',
        f'/repos/{safe_repo}/pulls',
        json_body={
            'title': title,
            'head': safe_head,
            'base': safe_base,
            'body': body,
        },
    )
    if isinstance(created, dict):
      return str(created.get('html_url', ''))
    return ''
