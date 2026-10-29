"""Onboarding CLI wizard (`cloud-operator-github-init`) for Option A setup.

Supports both:
  1. Zero-clone remote GitHub onboarding (`--github_repo=owner/repo` or
     interactive terminal wizard): verifies/obtains Google OAuth refresh
     credentials, enables GitHub Actions PR creation permissions via API,
     uploads `CLOUD_OPERATOR_OAUTH_CONFIG` to GitHub Secrets, and commits
     `.github/cloud-operator.yml` + `.github/workflows/cloud-operator.yml`
     directly to the remote repository.
  2. Local checkout file generation (`--repo_dir=/path/to/repo`).
"""

import base64
from collections.abc import Callable, Sequence
import json
import os
import re
import subprocess
import sys

from absl import app
from absl import flags
from absl import logging

from iac_design_review import auth
from iac_design_review import config

DEFAULT_ACTION_REF = (
    'GoogleCloudPlatform/gemini-cloud-assist-mcp/'
    'integrations/github/actions/iac-review@main'
)

_GITHUB_REPO = flags.DEFINE_string(
    'github_repo',
    '',
    'Remote GitHub repository in owner/repo format for zero-clone onboarding.',
)
_REPO_DIR = flags.DEFINE_string(
    'repo_dir',
    '',
    'Local GitHub repository root directory (used when --github_repo is unset).',
)
_PROJECT_ID = flags.DEFINE_string(
    'project_id',
    '',
    'Target Google Cloud project ID (e.g. my-gcp-project).',
)
_AGENT_ID = flags.DEFINE_string(
    'agent_id',
    '',
    'Optional custom Cloud Operator agent ID (defaults to personal agent).',
)
_ACTION_REF = flags.DEFINE_string(
    'action_ref',
    DEFAULT_ACTION_REF,
    'GitHub Action reference used in .github/workflows/cloud-operator.yml.',
)
_ADC_PATH = flags.DEFINE_string(
    'adc_path',
    os.path.expanduser(
        '~/.config/gcloud/application_default_credentials.json'
    ),
    'Path to local Google ADC JSON file containing a human refresh_token.',
)
_SET_GITHUB_SECRET = flags.DEFINE_bool(
    'set_github_secret',
    False,
    'If True, uploads CLOUD_OPERATOR_OAUTH_CONFIG to GitHub via `gh secret set`.',
)
_INTERACTIVE = flags.DEFINE_bool(
    'interactive',
    False,
    'Force interactive wizard prompts for missing flags.',
)
_AUTO_GCLOUD_LOGIN = flags.DEFINE_bool(
    'auto_gcloud_login',
    True,
    'Automatically run `gcloud auth application-default login` if ADC missing.',
)
_PR_MODE = flags.DEFINE_string(
    'pr_mode',
    'inline_comments',
    'PR review delivery mode: inline_comments (default), companion_pr, or '
    'comment_only.',
)

_REPO_FULL_NAME_RE = re.compile(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$')


def _validate_github_repo(github_repo: str) -> str:
  """Validates a GitHub `owner/repo` string."""
  cleaned = github_repo.strip()
  if not _REPO_FULL_NAME_RE.match(cleaned):
    raise ValueError(
        f'Invalid GitHub repository {github_repo!r}; expected "owner/repo".'
    )
  return cleaned


def render_autocloud_config_yaml(
    *,
    project_id: str,
    agent_id: str = '',
    enable_code_changes: bool = True,
    pr_mode: str = 'inline_comments',
) -> str:
  """Renders and validates `.github/autocloud.yml` content.

  Args:
    project_id: Target GCP project ID.
    agent_id: Optional custom AutoCloud Operator agent ID. When empty, the
      caller's personal operator agent is used.
    enable_code_changes: Whether Scenario 1 (PR Code & IaC Review) is enabled.
    pr_mode: PR review mode (`inline_comments`, `companion_pr`, `comment_only`).

  Returns:
    Validated YAML configuration string.
  """
  normalized_agent = config.normalize_agent_id(agent_id)
  if normalized_agent:
    agent_line = f'agent_id: "{normalized_agent}"\n\n'
  else:
    agent_line = (
        '# Optional: custom agent ID (defaults to caller\'s personal agent)\n'
        '# agent_id: ""\n\n'
    )

  code_enabled_str = 'true' if enable_code_changes else 'false'
  yaml_str = (
      'version: 1\n'
      f'project_id: "{project_id}"\n'
      f'{agent_line}'
      'scenarios:\n'
      '  # Scenario 1: PR Code & IaC Review\n'
      '  code_changes:\n'
      f'    enabled: {code_enabled_str}\n'
      '    triggers:\n'
      '      - pull_request.opened\n'
      '      - pull_request.synchronize\n'
      '      - issue_comment.created\n'
      '    trigger_command: "/cloud-operator review"\n'
      '    # Options: "inline_comments" (default), "companion_pr", '
      '"comment_only"\n'
      f'    pr_mode: "{pr_mode}"\n'
      '    allowed_author_associations:\n'
      '      - OWNER\n'
      '      - MEMBER\n'
      '      - COLLABORATOR\n'
      '    allow_fork_prs: false\n\n'
      '  # Scenario 2: Issue & Bug Implementation '
      '(WORK IN PROGRESS - Not available yet)\n'
      '  issue_implementation:\n'
      '    enabled: false\n'
      '    triggers:\n'
      '      - issues.labeled\n'
      '      - issue_comment.created\n'
      '    trigger_labels:\n'
      '      - "cloud-operator-implement"\n'
      '    trigger_command: "/cloud-operator implement"\n'
      '    base_branch: "main"\n'
  )
  config.parse_config_yaml(yaml_str)
  return yaml_str


def render_github_workflow_yaml(
    *, action_ref: str = DEFAULT_ACTION_REF
) -> str:
  """Renders `.github/workflows/cloud-operator.yml` content."""
  return (
      'name: Cloud Operator\n\n'
      'on:\n'
      '  pull_request:\n'
      '    types: [opened, synchronize, reopened]\n'
      '  issue_comment:\n'
      '    types: [created]\n\n'
      'concurrency:\n'
      '  group: >-\n'
      '    cloud-operator-${{ github.event.pull_request.number ||\n'
      '    github.event.issue.number || github.ref }}\n'
      '  cancel-in-progress: true\n\n'
      'permissions:\n'
      '  contents: write\n'
      '  pull-requests: write\n'
      '  issues: write\n\n'
      'jobs:\n'
      '  cloud-operator:\n'
      '    runs-on: ubuntu-latest\n'
      '    if: >-\n'
      "      github.event_name == 'pull_request' ||\n"
      "      (github.event_name == 'issue_comment' &&\n"
      "      contains(github.event.comment.body, '/cloud-operator'))\n"
      '    steps:\n'
      '      - name: Checkout Repository\n'
      '        uses: actions/checkout@v4\n'
      '        with:\n'
      '          fetch-depth: 0\n\n'
      '      - name: Run Cloud Operator\n'
      f'        uses: {action_ref}\n'
      '        env:\n'
      '          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n'
      '          CLOUD_OPERATOR_OAUTH_CONFIG: '
      '${{ secrets.CLOUD_OPERATOR_OAUTH_CONFIG }}\n'
  )


def initialize_repository(
    *,
    repo_dir: str,
    project_id: str,
    agent_id: str = '',
    action_ref: str = DEFAULT_ACTION_REF,
    enable_code_changes: bool = True,
    pr_mode: str = 'inline_comments',
) -> tuple[str, str]:
  """Writes `.github/cloud-operator.yml` and `.github/workflows/cloud-operator.yml`.

  Args:
    repo_dir: Target GitHub repository root directory.
    project_id: Target GCP project ID.
    agent_id: Optional target Cloud Operator agent ID.
    action_ref: GitHub Action reference string.
    enable_code_changes: Whether Scenario 1 (PR Code & IaC Review) is enabled.
    pr_mode: PR review mode (`inline_comments`, `companion_pr`, `comment_only`).

  Returns:
    Tuple of `(config_file_path, workflow_file_path)`.
  """
  repo_real = os.path.realpath(repo_dir)
  if not os.path.isdir(repo_real):
    raise ValueError(f'Repository directory does not exist: {repo_dir!r}')

  config_yaml = render_autocloud_config_yaml(
      project_id=project_id,
      agent_id=agent_id,
      enable_code_changes=enable_code_changes,
      pr_mode=pr_mode,
  )
  workflow_yaml = render_github_workflow_yaml(action_ref=action_ref)

  github_dir = os.path.join(repo_real, '.github')
  workflows_dir = os.path.join(github_dir, 'workflows')
  os.makedirs(workflows_dir, exist_ok=True)

  config_path = os.path.join(github_dir, 'cloud-operator.yml')
  workflow_path = os.path.join(workflows_dir, 'cloud-operator.yml')

  with open(config_path, 'w', encoding='utf-8') as cfg_file:
    cfg_file.write(config_yaml)
  with open(workflow_path, 'w', encoding='utf-8') as wf_file:
    wf_file.write(workflow_yaml)

  return config_path, workflow_path


def ensure_adc_credentials(
    *, adc_path: str, auto_gcloud_login: bool = True
) -> str:
  """Verifies local ADC OAuth refresh credentials or triggers `gcloud` login.

  Args:
    adc_path: Path to local `application_default_credentials.json`.
    auto_gcloud_login: If True, runs `gcloud auth application-default login`
      when `adc_path` is missing or invalid.

  Returns:
    Compact JSON string containing `client_id`, `client_secret`, and
    `refresh_token` suitable for `AUTOCLOUD_OAUTH_CONFIG`.

  Raises:
    auth.TokenSourceError: If valid human OAuth credentials cannot be obtained.
  """
  try:
    source = auth.OAuthRefreshTokenSource.from_adc_file(adc_path)
    source.token()
  except auth.TokenSourceError:
    if not auto_gcloud_login:
      raise
    logging.info(
        'Valid ADC not found at %s; launching `gcloud auth '
        'application-default login`...',
        adc_path,
    )
    try:
      subprocess.run(
          ['gcloud', 'auth', 'application-default', 'login'],
          shell=False,
          check=True,
      )
    except subprocess.CalledProcessError as err:
      raise auth.TokenSourceError(
          'gcloud auth application-default login failed '
          f'(exit {err.returncode}).'
      ) from err
    source = auth.OAuthRefreshTokenSource.from_adc_file(adc_path)
    source.token()

  with open(adc_path, encoding='utf-8') as adc_file:
    raw_adc = json.load(adc_file)
  return json.dumps({
      'client_id': str(raw_adc['client_id']).strip(),
      'client_secret': str(raw_adc['client_secret']).strip(),
      'refresh_token': str(raw_adc['refresh_token']).strip(),
  })


def upload_oauth_secret_via_gh(
    *,
    adc_path: str,
    repo_dir: str = '',
    github_repo: str = '',
    auto_gcloud_login: bool = True,
) -> None:
  """Validates local ADC user credentials and sets `CLOUD_OPERATOR_OAUTH_CONFIG`.

  Args:
    adc_path: Path to local `application_default_credentials.json`.
    repo_dir: Optional local repository directory where `gh` should execute.
    github_repo: Optional remote `owner/repo` target (`--repo owner/repo`).
    auto_gcloud_login: Whether to run `gcloud` login if ADC is missing.

  Raises:
    auth.TokenSourceError: If ADC file lacks valid human OAuth credentials.
    RuntimeError: If `gh secret set` fails.
  """
  secret_payload = ensure_adc_credentials(
      adc_path=adc_path, auto_gcloud_login=auto_gcloud_login
  )
  cmd = ['gh', 'secret', 'set', 'CLOUD_OPERATOR_OAUTH_CONFIG']
  if github_repo:
    safe_repo = _validate_github_repo(github_repo)
    cmd.extend(['--repo', safe_repo])

  run_cwd = os.path.realpath(repo_dir) if repo_dir else None
  try:
    subprocess.run(
        cmd,
        cwd=run_cwd,
        input=secret_payload,
        text=True,
        shell=False,
        check=True,
        capture_output=True,
    )
  except subprocess.CalledProcessError as err:
    raise RuntimeError(
        'gh secret set CLOUD_OPERATOR_OAUTH_CONFIG failed '
        f'(exit {err.returncode}).'
    ) from err


def enable_github_workflow_pr_permissions(*, github_repo: str) -> None:
  """Enables write and PR-creation workflow permissions on `github_repo`.

  Calls `PUT /repos/{owner}/{repo}/actions/permissions/workflow` via `gh api`
  so the Action can push companion branches and open Companion PRs without
  manual Settings clicks.

  Args:
    github_repo: Target GitHub repository in `owner/repo` format.

  Raises:
    RuntimeError: If the `gh api` call fails.
  """
  safe_repo = _validate_github_repo(github_repo)
  cmd = [
      'gh',
      'api',
      '--method',
      'PUT',
      f'repos/{safe_repo}/actions/permissions/workflow',
      '-f',
      'default_workflow_permissions=write',
      '-F',
      'can_approve_pull_request_reviews=true',
  ]
  try:
    subprocess.run(
        cmd,
        shell=False,
        check=True,
        capture_output=True,
        text=True,
    )
  except subprocess.CalledProcessError as err:
    stderr_msg = (err.stderr or '').strip()
    raise RuntimeError(
        f'Failed to enable workflow PR permissions on {safe_repo}: {stderr_msg}'
    ) from err


def upsert_remote_github_file(
    *,
    github_repo: str,
    file_path: str,
    content: str,
    commit_message: str,
) -> None:
  """Creates or updates `file_path` in `github_repo` via GitHub Contents API.

  Args:
    github_repo: Target GitHub repository in `owner/repo` format.
    file_path: Repository-relative POSIX path (e.g. `.github/autocloud.yml`).
    content: UTF-8 file content to commit.
    commit_message: Git commit message.

  Raises:
    RuntimeError: If the `gh api` Contents PUT call fails.
  """
  safe_repo = _validate_github_repo(github_repo)
  clean_path = file_path.lstrip('/')
  endpoint = f'repos/{safe_repo}/contents/{clean_path}'

  existing_sha = ''
  probe = subprocess.run(
      ['gh', 'api', endpoint],
      shell=False,
      check=False,
      capture_output=True,
      text=True,
  )
  if probe.returncode == 0 and probe.stdout:
    try:
      probe_data = json.loads(probe.stdout)
      if isinstance(probe_data, dict) and probe_data.get('sha'):
        existing_sha = str(probe_data['sha'])
    except json.JSONDecodeError:
      existing_sha = ''

  b64_content = base64.b64encode(content.encode('utf-8')).decode('ascii')
  put_cmd = [
      'gh',
      'api',
      '--method',
      'PUT',
      endpoint,
      '-f',
      f'message={commit_message}',
      '-f',
      f'content={b64_content}',
  ]
  if existing_sha:
    put_cmd.extend(['-f', f'sha={existing_sha}'])

  try:
    subprocess.run(
        put_cmd,
        shell=False,
        check=True,
        capture_output=True,
        text=True,
    )
  except subprocess.CalledProcessError as err:
    stderr_msg = (err.stderr or '').strip()
    raise RuntimeError(
        f'Failed to commit {clean_path} to {safe_repo}: {stderr_msg}'
    ) from err


def onboard_remote_repository(
    *,
    github_repo: str,
    project_id: str,
    agent_id: str = '',
    action_ref: str = DEFAULT_ACTION_REF,
    adc_path: str = _ADC_PATH.default,
    enable_code_changes: bool = True,
    pr_mode: str = 'inline_comments',
    auto_gcloud_login: bool = True,
) -> None:
  """Executes full Option A zero-clone remote onboarding for `github_repo`.

  1. Validates/acquires Google OAuth refresh token and uploads
     `AUTOCLOUD_OAUTH_CONFIG` to GitHub Secrets.
  2. Enables GitHub Actions workflow write & PR-creation permissions.
  3. Commits `.github/autocloud.yml` and `.github/workflows/autocloud.yml`
     directly to `github_repo` via the GitHub Contents API.

  Args:
    github_repo: Target GitHub repository in `owner/repo` format.
    project_id: Target GCP project ID.
    agent_id: Optional custom AutoCloud Operator agent ID.
    action_ref: GitHub Action reference string.
    adc_path: Path to local Google ADC JSON file.
    enable_code_changes: Whether Scenario 1 (PR Code & IaC Review) is enabled.
    pr_mode: PR review mode (`inline_comments`, `companion_pr`, `comment_only`).
    auto_gcloud_login: Whether to run `gcloud` login if ADC is missing.
  """
  safe_repo = _validate_github_repo(github_repo)
  config_yaml = render_autocloud_config_yaml(
      project_id=project_id,
      agent_id=agent_id,
      enable_code_changes=enable_code_changes,
      pr_mode=pr_mode,
  )
  workflow_yaml = render_github_workflow_yaml(action_ref=action_ref)

  logging.info(
      '1/4 Uploading CLOUD_OPERATOR_OAUTH_CONFIG secret to %s...', safe_repo
  )
  upload_oauth_secret_via_gh(
      adc_path=adc_path,
      github_repo=safe_repo,
      auto_gcloud_login=auto_gcloud_login,
  )

  logging.info(
      '2/4 Enabling GitHub Actions PR creation permissions on %s...', safe_repo
  )
  enable_github_workflow_pr_permissions(github_repo=safe_repo)

  logging.info('3/4 Committing .github/cloud-operator.yml to %s...', safe_repo)
  upsert_remote_github_file(
      github_repo=safe_repo,
      file_path='.github/cloud-operator.yml',
      content=config_yaml,
      commit_message='ci(cloud-operator): configure .github/cloud-operator.yml',
  )

  logging.info(
      '4/4 Committing .github/workflows/cloud-operator.yml to %s...', safe_repo
  )
  upsert_remote_github_file(
      github_repo=safe_repo,
      file_path='.github/workflows/cloud-operator.yml',
      content=workflow_yaml,
      commit_message='ci(cloud-operator): add Cloud Operator workflow',
  )


def run_interactive_wizard(
    *,
    input_fn: Callable[[str], str] = input,
    default_github_repo: str = '',
    default_project_id: str = '',
    default_agent_id: str = '',
    default_action_ref: str = DEFAULT_ACTION_REF,
) -> tuple[str, str, str, str, bool]:
  """Prompts the user interactively for onboarding parameters.

  Args:
    input_fn: Callable used to read lines from stdin (injectable for tests).
    default_github_repo: Default `owner/repo` value.
    default_project_id: Default GCP project ID.
    default_agent_id: Default custom agent ID.
    default_action_ref: Default GitHub Action reference.

  Returns:
    Tuple of `(github_repo, project_id, agent_id, action_ref,
    enable_code_changes)`.
  """
  print('\n=== Cloud Operator — GitHub Onboarding Wizard ===\n')
  repo_prompt = (
      f'1. GitHub Repository (owner/repo) [{default_github_repo}]: '
      if default_github_repo
      else '1. GitHub Repository (owner/repo, or blank for local directory): '
  )
  github_repo = input_fn(repo_prompt).strip() or default_github_repo

  proj_prompt = (
      f'2. Google Cloud Project ID [{default_project_id}]: '
      if default_project_id
      else '2. Google Cloud Project ID (e.g. my-gcp-project): '
  )
  project_id = input_fn(proj_prompt).strip() or default_project_id

  agent_prompt = (
      f'3. Cloud Operator Agent ID (optional) [{default_agent_id}]: '
      if default_agent_id
      else '3. Cloud Operator Agent ID (optional, Enter for personal agent): '
  )
  agent_id = input_fn(agent_prompt).strip() or default_agent_id

  action_prompt = f'4. GitHub Action Reference [{default_action_ref}]: '
  action_ref = input_fn(action_prompt).strip() or default_action_ref

  print('\n5. Scenarios:')
  print('   [1] PR Code & IaC Review (Default: Enabled, Mode: Inline Comments)')
  print(
      '   [2] Issue & Bug Implementation '
      '[Work in Progress — Not available yet]'
  )
  enable_ans = (
      input_fn('   Enable PR Code & IaC Review? [Y/n]: ').strip().lower()
  )
  enable_code_changes = enable_ans not in ('n', 'no', 'false', '0')

  return github_repo, project_id, agent_id, action_ref, enable_code_changes


def main(argv: Sequence[str]) -> None:
  """CLI entrypoint for `autocloud-github-init`."""
  if len(argv) > 1:
    raise app.UsageError('Too many command-line arguments.')

  github_repo = _GITHUB_REPO.value.strip()
  project_id = _PROJECT_ID.value.strip()
  agent_id = _AGENT_ID.value.strip()
  action_ref = _ACTION_REF.value.strip()
  pr_mode = _PR_MODE.value.strip()
  enable_code_changes = True

  if _INTERACTIVE.value or (not project_id and sys.stdin.isatty()):
    (
        github_repo,
        project_id,
        agent_id,
        action_ref,
        enable_code_changes,
    ) = run_interactive_wizard(
        default_github_repo=github_repo,
        default_project_id=project_id,
        default_agent_id=agent_id,
        default_action_ref=action_ref,
    )

  if not project_id:
    raise app.UsageError('--project_id is required.')

  if github_repo:
    onboard_remote_repository(
        github_repo=github_repo,
        project_id=project_id,
        agent_id=agent_id,
        action_ref=action_ref,
        adc_path=_ADC_PATH.value,
        enable_code_changes=enable_code_changes,
        pr_mode=pr_mode,
        auto_gcloud_login=_AUTO_GCLOUD_LOGIN.value,
    )
    logging.info(
        'Successfully onboarded https://github.com/%s with Cloud Operator!',
        github_repo,
    )
    return

  repo_dir = _REPO_DIR.value or os.getcwd()
  config_path, workflow_path = initialize_repository(
      repo_dir=repo_dir,
      project_id=project_id,
      agent_id=agent_id,
      action_ref=action_ref,
      enable_code_changes=enable_code_changes,
      pr_mode=pr_mode,
  )
  logging.info('Generated Cloud Operator config: %s', config_path)
  logging.info('Generated GitHub workflow: %s', workflow_path)

  if _SET_GITHUB_SECRET.value:
    upload_oauth_secret_via_gh(
        adc_path=_ADC_PATH.value,
        repo_dir=repo_dir,
        auto_gcloud_login=_AUTO_GCLOUD_LOGIN.value,
    )
    logging.info(
        'Uploaded CLOUD_OPERATOR_OAUTH_CONFIG secret via `gh secret set`.'
    )


def run() -> None:
  """Zero-argument console script entrypoint for `pyproject.toml`."""
  app.run(main)


if __name__ == '__main__':
  run()
