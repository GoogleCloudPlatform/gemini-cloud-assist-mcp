"""GitHub Action runner entrypoint for AutoCloud Operator PR reviews."""

from collections.abc import Mapping, Sequence
import json
import os
from typing import Any

from absl import app
from absl import flags
from absl import logging

from iac_design_review import auth
from iac_design_review import config
from iac_design_review import github_pr
from iac_design_review import mcp_client
from iac_design_review import parser

_WORKSPACE_DIR = flags.DEFINE_string(
    'workspace_dir',
    '',
    'Repository checkout directory. Defaults to $GITHUB_WORKSPACE or cwd.',
)
_CONFIG_PATH = flags.DEFINE_string(
    'config_path',
    '',
    'Path to .github/cloud-operator.yml relative to workspace or absolute.',
)
_EVENT_NAME = flags.DEFINE_string(
    'event_name',
    '',
    'GitHub webhook event name (defaults to $GITHUB_EVENT_NAME).',
)
_EVENT_PATH = flags.DEFINE_string(
    'event_path',
    '',
    'Path to GitHub webhook event JSON payload ($GITHUB_EVENT_PATH).',
)
_REPO_FULL_NAME = flags.DEFINE_string(
    'repo_full_name',
    '',
    'GitHub owner/repo identifier (defaults to $GITHUB_REPOSITORY).',
)
_MCP_URL = flags.DEFINE_string(
    'mcp_url',
    '',
    'HTTPS URL for Gemini Cloud Assist MCP endpoint.',
)
_USE_LOCAL_ADC = flags.DEFINE_bool(
    'use_local_adc',
    False,
    'Use local workstation ADC credentials (Cloudtop smoke testing only).',
)
_DRY_RUN_GITHUB = flags.DEFINE_bool(
    'dry_run_github',
    False,
    'Skip git push and GitHub REST API calls (local smoke testing mode).',
)
_CHANGED_FILES = flags.DEFINE_list(
    'changed_files',
    [],
    'Optional list of relative file paths for --dry_run_github testing.',
)

_MAX_FILE_BYTES = 128 * 1024
_MAX_COMMENT_CHARS = 16 * 1024


def _extract_issue_comment_body(payload: Mapping[str, Any]) -> str:
  """Extracts a bounded, stripped comment body from an issue_comment payload."""
  comment_obj = payload.get('comment')
  if not isinstance(comment_obj, Mapping):
    return ''
  raw_body = comment_obj.get('body')
  if not isinstance(raw_body, str):
    return ''
  return raw_body.strip()[:_MAX_COMMENT_CHARS]


def _load_event_payload(event_path: str) -> dict[str, Any]:
  """Reads and decodes the GitHub webhook event JSON payload."""
  if not event_path:
    return {}
  with open(event_path, encoding='utf-8') as event_file:
    data = json.load(event_file)
  if not isinstance(data, dict):
    raise ValueError('GitHub event payload root must be a JSON object.')
  return data


def _extract_pr_metadata(
    event_name: str, payload: Mapping[str, Any]
) -> tuple[int, str, str]:
  """Extracts `(pr_number, pr_title, pr_head_branch)` from the event payload."""
  if event_name == 'pull_request':
    pr_obj = payload.get('pull_request') or {}
    if isinstance(pr_obj, Mapping):
      pr_num = int(pr_obj.get('number', 0) or 0)
      title = str(pr_obj.get('title', '') or f'PR #{pr_num}')
      head_obj = pr_obj.get('head') or {}
      head_ref = (
          str(head_obj.get('ref', ''))
          if isinstance(head_obj, Mapping)
          else ''
      )
      return pr_num, title, head_ref

  if event_name == 'issue_comment':
    issue_obj = payload.get('issue') or {}
    if isinstance(issue_obj, Mapping):
      pr_num = int(issue_obj.get('number', 0) or 0)
      title = str(issue_obj.get('title', '') or f'PR #{pr_num}')
      return pr_num, title, ''

  return 0, 'Local Smoke Test PR', 'smoke-test-branch'


def _read_workspace_files(
    workspace_dir: str, relative_paths: Sequence[str]
) -> dict[str, str]:
  """Reads text files from `workspace_dir` up to `_MAX_FILE_BYTES` each."""
  workspace_real = os.path.realpath(workspace_dir)
  bundled: dict[str, str] = {}

  for raw_rel in relative_paths:
    safe_rel = parser.sanitize_relative_repo_path(raw_rel)
    abs_path = os.path.realpath(os.path.join(workspace_real, safe_rel))
    if not abs_path.startswith(workspace_real + os.sep):
      continue
    if not os.path.isfile(abs_path) or os.path.islink(abs_path):
      continue
    if os.path.getsize(abs_path) > _MAX_FILE_BYTES:
      logging.warning('Skipping large file (>128KB): %s', safe_rel)
      continue
    try:
      with open(abs_path, encoding='utf-8') as src_file:
        bundled[safe_rel] = src_file.read()
    except UnicodeDecodeError:
      logging.info('Skipping non-UTF-8 binary file: %s', safe_rel)
  return bundled


def run_action(
    *,
    workspace_dir: str,
    config_path: str,
    event_name: str,
    event_payload: Mapping[str, Any],
    repo_full_name: str,
    mcp_url: str,
    tokens: auth.TokenSource,
    github_client: github_pr.GitHubClient | None,
    dry_run_github: bool,
    override_changed_files: Sequence[str] = (),
) -> int:
  """Executes the Option 1 AutoCloud GitHub Action workflow.

  Args:
    workspace_dir: Repository checkout root directory.
    config_path: Path to `.github/autocloud.yml`.
    event_name: GitHub webhook event name.
    event_payload: Decoded GitHub webhook event JSON.
    repo_full_name: GitHub `owner/repo` string.
    mcp_url: HTTPS MCP endpoint URL.
    tokens: Human Google EUC token source.
    github_client: Authenticated `GitHubClient` (None when `dry_run_github`).
    dry_run_github: Whether to skip git push and GitHub REST API mutations.
    override_changed_files: Explicit relative paths for local smoke tests.

  Returns:
    Process exit code (0 on success).
  """
  repo_cfg = config.load_config(config_path)

  if not dry_run_github and not config.should_trigger_code_review(
      repo_cfg, event_name, event_payload
  ):
    logging.info(
        'Event %s does not match configured code_changes triggers; skipping.',
        event_name,
    )
    return 0

  pr_number, pr_title, pr_head_branch = _extract_pr_metadata(
      event_name, event_payload
  )
  if pr_number <= 0:
    pr_number = 1

  prior_context_id: str | None = None
  if override_changed_files:
    rel_paths = list(override_changed_files)
  elif github_client is not None:
    if event_name == 'issue_comment' and not pr_head_branch:
      api_title, pr_head_branch = github_client.get_pr_metadata(
          repo_full_name, pr_number
      )
      if api_title:
        pr_title = api_title
      if pr_head_branch.startswith(config.COMPANION_BRANCH_PREFIX):
        logging.info(
            'PR #%d is a Companion PR (%s); skipping.',
            pr_number,
            pr_head_branch,
        )
        return 0
      if (
          not dry_run_github
          and not repo_cfg.scenarios.code_changes.allow_fork_prs
          and github_client.is_pr_from_fork(repo_full_name, pr_number) is True
      ):
        logging.info(
            'PR #%d originates from a fork and allow_fork_prs is False; '
            'skipping.',
            pr_number,
        )
        return 0
      if not dry_run_github:
        github_pr.checkout_pr_head(workspace_dir, pr_number)
    rel_paths = github_client.list_pr_changed_files(repo_full_name, pr_number)
    prior_comments = github_client.list_issue_comments(
        repo_full_name, pr_number
    )
    prior_reviews = github_client.list_pr_review_bodies(
        repo_full_name, pr_number
    )
    prior_context_id = parser.extract_context_id_marker(
        [*prior_comments, *prior_reviews]
    )
  else:
    raise ValueError(
        'Either --changed_files or a live GitHubClient must be provided.'
    )

  changed_files = _read_workspace_files(workspace_dir, rel_paths)
  if not changed_files:
    logging.info(
        'No readable text files changed in PR #%d; exiting.', pr_number
    )
    return 0

  pr_mode = repo_cfg.scenarios.code_changes.pr_mode
  prompt = mcp_client.build_pr_review_prompt(
      project_id=repo_cfg.project_id,
      repo_full_name=repo_full_name or 'local/smoke-test',
      pr_number=pr_number,
      pr_title=pr_title,
      changed_files=changed_files,
      pr_mode=pr_mode,
  )
  if event_name == 'issue_comment':
    comment_body = _extract_issue_comment_body(event_payload)
    if comment_body:
      prompt = (
          f'{prompt}\n\n'
          '## PR Comment Trigger / Additional Instructions\n\n'
          f'{comment_body}'
      )

  answer = mcp_client.ask_cloud_operator(
      tokens=tokens,
      mcp_url=mcp_url,
      project_id=repo_cfg.project_id,
      agent_id=repo_cfg.agent_id,
      user_query=prompt,
      context_id=prior_context_id,
  )

  remediated = parser.extract_remediated_files(answer.content)
  explicit_inline = parser.extract_inline_comments(answer.content)
  covered_paths = {item.path for item in explicit_inline}
  unmatched_remediated = [
      rem for rem in remediated if rem.path not in covered_paths
  ]
  diff_inline = parser.build_inline_comments_from_remediated_files(
      changed_files, unmatched_remediated
  )
  all_inline = parser.clamp_inline_comments_to_files(
      [*explicit_inline, *diff_inline], changed_files
  )

  logging.info(
      'Received AutoCloud review (context_id=%s, pr_mode=%s, '
      'inline_comments=%d, remediated_files=%d).',
      answer.context_id,
      pr_mode,
      len(all_inline),
      len(remediated),
  )

  clean_summary = parser.strip_inline_comments_json_block(answer.content)

  if dry_run_github:
    if remediated:
      written = github_pr.write_remediated_files_safely(
          workspace_dir, remediated
      )
      logging.info('Dry-run wrote remediated files locally: %s', written)
    logging.info('Dry-run inline comments count: %d', len(all_inline))
    logging.info('Dry-run review summary:\n%s', clean_summary)
    return 0

  if github_client is None:
    raise RuntimeError('github_client is required when dry_run_github=False.')

  if pr_mode == 'inline_comments':
    review_body_with_ctx = parser.embed_context_id_marker(
        clean_summary, answer.context_id
    )
    github_client.post_pr_review(
        repo_full_name,
        pr_number,
        review_body_with_ctx,
        inline_comments=all_inline,
    )
    return 0

  companion_url = ''
  if pr_mode == 'companion_pr' and remediated and pr_head_branch:
    written = github_pr.write_remediated_files_safely(workspace_dir, remediated)
    companion_branch = github_pr.companion_branch_for_pr(pr_number)
    pushed = github_pr.commit_and_push_companion_branch(
        workspace_dir=workspace_dir,
        companion_branch=companion_branch,
        written_paths=written,
        pr_number=pr_number,
        push_remote=True,
    )
    if pushed:
      companion_url = github_client.create_or_update_companion_pr(
          repo_full_name=repo_full_name,
          source_pr_number=pr_number,
          pr_head_branch=pr_head_branch,
          companion_branch=companion_branch,
          summary_markdown=clean_summary,
      )

  comment_body = clean_summary
  if companion_url:
    comment_body = (
        f'### Cloud Operator Companion PR Opened: {companion_url}\n\n'
        f'{comment_body}'
    )
  comment_with_ctx = parser.embed_context_id_marker(
      comment_body, answer.context_id
  )
  github_client.post_issue_comment(
      repo_full_name, pr_number, comment_with_ctx
  )
  return 0


def main(argv: Sequence[str]) -> None:
  """CLI entrypoint for the Cloud Operator GitHub Action runner."""
  if len(argv) > 1:
    raise app.UsageError('Too many command-line arguments.')

  workspace_dir = (
      _WORKSPACE_DIR.value
      or os.environ.get('GITHUB_WORKSPACE', '')
      or os.getcwd()
  )
  config_path = _CONFIG_PATH.value or os.path.join(
      workspace_dir, '.github', 'cloud-operator.yml'
  )
  event_name = _EVENT_NAME.value or os.environ.get(
      'GITHUB_EVENT_NAME', 'pull_request'
  )
  event_path = _EVENT_PATH.value or os.environ.get('GITHUB_EVENT_PATH', '')
  repo_full_name = _REPO_FULL_NAME.value or os.environ.get(
      'GITHUB_REPOSITORY', ''
  )
  mcp_url = (
      _MCP_URL.value
      or os.environ.get('CLOUD_OPERATOR_MCP_URL', '')
      or mcp_client.DEFAULT_PROD_MCP_URL
  )

  tokens = auth.build_token_source(
      oauth_config_json=os.environ.get('CLOUD_OPERATOR_OAUTH_CONFIG', ''),
      use_local_adc=_USE_LOCAL_ADC.value,
  )

  gh_client: github_pr.GitHubClient | None = None
  if not _DRY_RUN_GITHUB.value:
    gh_token = os.environ.get('GITHUB_TOKEN', '')
    gh_client = github_pr.GitHubClient(github_token=gh_token)

  event_payload = _load_event_payload(event_path)
  exit_code = run_action(
      workspace_dir=workspace_dir,
      config_path=config_path,
      event_name=event_name,
      event_payload=event_payload,
      repo_full_name=repo_full_name,
      mcp_url=mcp_url,
      tokens=tokens,
      github_client=gh_client,
      dry_run_github=_DRY_RUN_GITHUB.value,
      override_changed_files=_CHANGED_FILES.value,
  )
  if exit_code != 0:
    raise SystemExit(exit_code)


def run() -> None:
  """Zero-argument console script entrypoint for `pyproject.toml`."""
  app.run(main)


if __name__ == '__main__':
  run()
