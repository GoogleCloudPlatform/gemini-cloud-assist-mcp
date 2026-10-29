"""Configuration parser and event router for Cloud Operator GitHub integration."""

from collections.abc import Mapping
import dataclasses
import re
from typing import Any

import yaml

_PROJECT_ID_RE = re.compile(r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$')
_AGENT_ID_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{1,62}$')
_FENCED_COMMENT_BLOCK_RE = re.compile(
    r'(?:```.*?```|~~~.*?~~~)', re.DOTALL
)

ALLOWED_CODE_TRIGGERS = frozenset({
    'pull_request.opened',
    'pull_request.synchronize',
    'pull_request.reopened',
    'issue_comment.created',
})

ALLOWED_ISSUE_TRIGGERS = frozenset({
    'issues.opened',
    'issues.labeled',
    'issue_comment.created',
})

ALLOWED_PR_MODES = frozenset({
    'inline_comments',
    'companion_pr',
    'comment_only',
})

ALLOWED_AUTHOR_ASSOCIATIONS = frozenset({
    'OWNER',
    'MEMBER',
    'COLLABORATOR',
    'CONTRIBUTOR',
    'FIRST_TIME_CONTRIBUTOR',
    'FIRST_TIMER',
    'MANNEQUIN',
    'NONE',
})

DEFAULT_ALLOWED_AUTHOR_ASSOCIATIONS: tuple[str, ...] = (
    'OWNER',
    'MEMBER',
    'COLLABORATOR',
)

COMPANION_BRANCH_PREFIX = 'cloud-operator/remediate-pr-'
ISSUE_COMPANION_BRANCH_PREFIX = 'cloud-operator/issue-'


class ConfigValidationError(ValueError):
  """Raised when `.github/cloud-operator.yml` fails schema validation."""


@dataclasses.dataclass(frozen=True)
class CodeChangesConfig:
  """Configuration for Scenario 1: PR Code & IaC Review."""

  enabled: bool = True
  triggers: tuple[str, ...] = (
      'pull_request.opened',
      'pull_request.synchronize',
      'issue_comment.created',
  )
  trigger_command: str = '/cloud-operator review'
  pr_mode: str = 'inline_comments'
  allowed_author_associations: tuple[str, ...] = (
      DEFAULT_ALLOWED_AUTHOR_ASSOCIATIONS
  )
  allow_fork_prs: bool = False


@dataclasses.dataclass(frozen=True)
class IssueImplementationConfig:
  """Configuration for Scenario 2: Issue & Bug Implementation."""

  enabled: bool = False
  triggers: tuple[str, ...] = (
      'issues.opened',
      'issues.labeled',
      'issue_comment.created',
  )
  trigger_labels: tuple[str, ...] = ()
  trigger_command: str = '/cloud-operator implement'
  base_branch: str = 'main'
  allowed_author_associations: tuple[str, ...] = (
      DEFAULT_ALLOWED_AUTHOR_ASSOCIATIONS
  )


@dataclasses.dataclass(frozen=True)
class ScenariosConfig:
  """Container for configured Cloud Operator GitHub scenarios."""

  code_changes: CodeChangesConfig = dataclasses.field(
      default_factory=CodeChangesConfig
  )
  issue_implementation: IssueImplementationConfig = dataclasses.field(
      default_factory=IssueImplementationConfig
  )


@dataclasses.dataclass(frozen=True)
class AutoCloudRepoConfig:
  """Top-level configuration parsed from `.github/cloud-operator.yml`."""

  version: int
  project_id: str
  agent_id: str = ''
  scenarios: ScenariosConfig = dataclasses.field(
      default_factory=ScenariosConfig
  )


def _require_bool(
    raw_map: Mapping[str, Any], key: str, default: bool, section: str
) -> bool:
  """Returns a validated boolean value from `raw_map`."""
  val = raw_map.get(key, default)
  if not isinstance(val, bool):
    raise ConfigValidationError(f'{section}.{key} must be a boolean.')
  return val


def _require_str(
    raw_map: Mapping[str, Any], key: str, default: str, section: str
) -> str:
  """Returns a validated stripped string value from `raw_map`."""
  val = raw_map.get(key, default)
  if not isinstance(val, str):
    raise ConfigValidationError(f'{section}.{key} must be a string.')
  return val.strip()


def _parse_author_associations(
    raw_map: Mapping[str, Any], section: str
) -> tuple[str, ...]:
  """Parses and validates `allowed_author_associations` for a scenario."""
  raw_associations = raw_map.get(
      'allowed_author_associations',
      list(DEFAULT_ALLOWED_AUTHOR_ASSOCIATIONS),
  )
  if not isinstance(raw_associations, list) or not raw_associations:
    raise ConfigValidationError(
        f'{section}.allowed_author_associations must be a non-empty list.'
    )
  associations: list[str] = []
  for item in raw_associations:
    cleaned_assoc = str(item).strip().upper() if isinstance(item, str) else ''
    if not cleaned_assoc or cleaned_assoc not in ALLOWED_AUTHOR_ASSOCIATIONS:
      raise ConfigValidationError(
          f'Unsupported author_association: {item!r}. '
          f'Allowed: {sorted(ALLOWED_AUTHOR_ASSOCIATIONS)}'
      )
    associations.append(cleaned_assoc)
  return tuple(associations)


def _parse_code_changes(raw_map: Mapping[str, Any]) -> CodeChangesConfig:
  """Parses and validates the `scenarios.code_changes` block."""
  section = 'scenarios.code_changes'
  enabled = _require_bool(raw_map, 'enabled', True, section)
  raw_triggers = raw_map.get(
      'triggers',
      [
          'pull_request.opened',
          'pull_request.synchronize',
          'issue_comment.created',
      ],
  )
  if not isinstance(raw_triggers, list) or not raw_triggers:
    raise ConfigValidationError(
        'scenarios.code_changes.triggers must be a non-empty list.'
    )
  triggers: list[str] = []
  for item in raw_triggers:
    if not isinstance(item, str) or item not in ALLOWED_CODE_TRIGGERS:
      raise ConfigValidationError(
          f'Unsupported code_changes trigger: {item!r}. '
          f'Allowed: {sorted(ALLOWED_CODE_TRIGGERS)}'
      )
    triggers.append(item)

  trigger_command = _require_str(
      raw_map, 'trigger_command', '/cloud-operator review', section
  )
  if not trigger_command:
    raise ConfigValidationError(
        'scenarios.code_changes.trigger_command must be a non-empty string.'
    )

  pr_mode = _require_str(raw_map, 'pr_mode', 'inline_comments', section)
  if pr_mode not in ALLOWED_PR_MODES:
    raise ConfigValidationError(
        f'Unsupported pr_mode: {pr_mode!r}. '
        f'Allowed: {sorted(ALLOWED_PR_MODES)}'
    )

  associations = _parse_author_associations(raw_map, section)
  raw_allow_fork_prs = _require_bool(
      raw_map, 'allow_fork_prs', False, section
  )

  return CodeChangesConfig(
      enabled=enabled,
      triggers=tuple(triggers),
      trigger_command=trigger_command,
      pr_mode=pr_mode,
      allowed_author_associations=associations,
      allow_fork_prs=raw_allow_fork_prs,
  )


def _parse_issue_impl(raw_map: Mapping[str, Any]) -> IssueImplementationConfig:
  """Parses and validates the `scenarios.issue_implementation` block."""
  section = 'scenarios.issue_implementation'
  enabled = _require_bool(raw_map, 'enabled', False, section)
  raw_triggers = raw_map.get(
      'triggers',
      ['issues.opened', 'issues.labeled', 'issue_comment.created'],
  )
  if not isinstance(raw_triggers, list) or not raw_triggers:
    raise ConfigValidationError(
        'scenarios.issue_implementation.triggers must be a non-empty list.'
    )
  triggers: list[str] = []
  for item in raw_triggers:
    if not isinstance(item, str) or item not in ALLOWED_ISSUE_TRIGGERS:
      raise ConfigValidationError(
          f'Unsupported issue_implementation trigger: {item!r}. '
          f'Allowed: {sorted(ALLOWED_ISSUE_TRIGGERS)}'
      )
    triggers.append(item)

  raw_labels = raw_map.get('trigger_labels', [])
  if not isinstance(raw_labels, list):
    raise ConfigValidationError(
        'scenarios.issue_implementation.trigger_labels must be a list.'
    )
  labels: list[str] = []
  for label in raw_labels:
    if not isinstance(label, str) or not label.strip():
      raise ConfigValidationError(
          'scenarios.issue_implementation.trigger_labels items must be '
          'non-empty strings.'
      )
    labels.append(label.strip())

  trigger_command = _require_str(
      raw_map, 'trigger_command', '/cloud-operator implement', section
  )
  if not trigger_command:
    raise ConfigValidationError(
        'scenarios.issue_implementation.trigger_command must be a non-empty '
        'string.'
    )

  base_branch = _require_str(raw_map, 'base_branch', 'main', section)
  if not base_branch:
    raise ConfigValidationError(
        'scenarios.issue_implementation.base_branch must be a non-empty string.'
    )

  associations = _parse_author_associations(raw_map, section)

  return IssueImplementationConfig(
      enabled=enabled,
      triggers=tuple(triggers),
      trigger_labels=tuple(labels),
      trigger_command=trigger_command,
      base_branch=base_branch,
      allowed_author_associations=associations,
  )


def normalize_agent_id(raw_agent_id: str) -> str:
  """Normalizes an optional Cloud Operator `agent_id`.

  The Gemini Cloud Assist frontend prepends the reserved `autocloud-` prefix
  automatically when routing to backing agents, so any leading `autocloud-`
  prefix is stripped here. An empty string selects the caller's personal agent.

  Args:
    raw_agent_id: Raw `agent_id` value from `.github/cloud-operator.yml` or CLI.

  Returns:
    Normalized unprefixed `agent_id`, or `''` for the caller's personal agent.

  Raises:
    ConfigValidationError: If `raw_agent_id` is malformed or bare `autocloud-`.
  """
  cleaned = raw_agent_id.strip()
  if not cleaned:
    return ''

  if cleaned.startswith('autocloud-'):
    cleaned = cleaned.removeprefix('autocloud-')
    if not cleaned:
      raise ConfigValidationError(
          'agent_id must not be the bare reserved prefix "autocloud-".'
      )

  if not _AGENT_ID_RE.match(cleaned):
    raise ConfigValidationError(f'Invalid agent_id: {raw_agent_id!r}.')
  return cleaned


def parse_config_yaml(yaml_content: str) -> AutoCloudRepoConfig:
  """Parses and validates `.github/cloud-operator.yml` YAML string content.

  Args:
    yaml_content: Raw YAML string from `.github/cloud-operator.yml`.

  Returns:
    Validated `AutoCloudRepoConfig` instance.

  Raises:
    ConfigValidationError: If required fields are missing or invalid.
  """
  try:
    parsed = yaml.safe_load(yaml_content)
  except yaml.YAMLError as err:
    raise ConfigValidationError(f'Invalid YAML syntax: {err}') from err

  if not isinstance(parsed, Mapping):
    raise ConfigValidationError('Configuration root must be a YAML mapping.')

  version = parsed.get('version', 1)
  if isinstance(version, bool) or version != 1:
    raise ConfigValidationError(
        f'Unsupported config version: {version!r}. Expected 1.'
    )

  raw_project_id = parsed.get('project_id', '')
  if not isinstance(raw_project_id, str):
    raise ConfigValidationError('project_id must be a string.')
  project_id = raw_project_id.strip()
  if not _PROJECT_ID_RE.match(project_id):
    raise ConfigValidationError(
        f'Invalid or missing project_id: {project_id!r}.'
    )

  raw_agent_id = parsed.get('agent_id', '')
  if raw_agent_id is None:
    raw_agent_id = ''
  if not isinstance(raw_agent_id, str):
    raise ConfigValidationError('agent_id must be a string.')
  agent_id = normalize_agent_id(raw_agent_id)

  raw_scenarios = (
      parsed['scenarios']
      if 'scenarios' in parsed and parsed['scenarios'] is not None
      else {}
  )
  if not isinstance(raw_scenarios, Mapping):
    raise ConfigValidationError('`scenarios` must be a mapping.')

  raw_code = (
      raw_scenarios['code_changes']
      if 'code_changes' in raw_scenarios
      and raw_scenarios['code_changes'] is not None
      else {}
  )
  if not isinstance(raw_code, Mapping):
    raise ConfigValidationError('`scenarios.code_changes` must be a mapping.')

  raw_issue = (
      raw_scenarios['issue_implementation']
      if 'issue_implementation' in raw_scenarios
      and raw_scenarios['issue_implementation'] is not None
      else {}
  )
  if not isinstance(raw_issue, Mapping):
    raise ConfigValidationError(
        '`scenarios.issue_implementation` must be a mapping.'
    )

  return AutoCloudRepoConfig(
      version=version,
      project_id=project_id,
      agent_id=agent_id,
      scenarios=ScenariosConfig(
          code_changes=_parse_code_changes(raw_code),
          issue_implementation=_parse_issue_impl(raw_issue),
      ),
  )


def load_config(config_path: str) -> AutoCloudRepoConfig:
  """Reads and validates `.github/cloud-operator.yml` from disk.

  Args:
    config_path: File path to `.github/cloud-operator.yml`.

  Returns:
    Validated `AutoCloudRepoConfig` instance.

  Raises:
    ConfigValidationError: If the file cannot be read or fails validation.
  """
  try:
    with open(config_path, encoding='utf-8') as config_file:
      content = config_file.read()
  except OSError as err:
    raise ConfigValidationError(
        f'Could not read config file {config_path!r}: {err}'
    ) from err
  return parse_config_yaml(content)


def is_fork_pull_request(pull_request: Mapping[str, Any]) -> bool:
  """Returns True if `pull_request` originates from a forked repository."""
  head_info = pull_request.get('head')
  if not isinstance(head_info, Mapping):
    return False
  head_repo = head_info.get('repo')
  if isinstance(head_repo, Mapping) and bool(head_repo.get('fork', False)):
    return True
  base_info = pull_request.get('base')
  base_repo = (
      base_info.get('repo') if isinstance(base_info, Mapping) else None
  )
  if isinstance(head_repo, Mapping) and isinstance(base_repo, Mapping):
    head_full = str(head_repo.get('full_name', '')).strip()
    base_full = str(base_repo.get('full_name', '')).strip()
    if head_full and base_full and head_full != base_full:
      return True
  return False


def _matches_trigger_command(comment_body: str, trigger_command: str) -> bool:
  """Returns True if `trigger_command` starts a line outside fenced blocks."""
  body_without_fences = _FENCED_COMMENT_BLOCK_RE.sub('', comment_body)
  pattern = rf'(?m)^[^\S\r\n]*{re.escape(trigger_command)}(?:\s|$)'
  return bool(re.search(pattern, body_without_fences))


def _extract_issue_label_names(issue: Mapping[str, Any]) -> set[str]:
  """Extracts lowercase label names attached to a GitHub `issue` object."""
  raw_labels = issue.get('labels')
  if not isinstance(raw_labels, list):
    return set()
  names: set[str] = set()
  for entry in raw_labels:
    if isinstance(entry, Mapping):
      name = entry.get('name')
      if isinstance(name, str) and name.strip():
        names.add(name.strip().lower())
    elif isinstance(entry, str) and entry.strip():
      names.add(entry.strip().lower())
  return names


def should_trigger_code_review(
    repo_config: AutoCloudRepoConfig,
    event_name: str,
    event_payload: Mapping[str, Any],
) -> bool:
  """Determines whether a GitHub event should trigger a PR code review.

  Skips draft PRs, Cloud Operator branches (`cloud-operator/remediate-pr-*` and
  `cloud-operator/issue-*`), untrusted author associations, and fork PRs
  (unless `allow_fork_prs` is True).

  Args:
    repo_config: Validated repository configuration.
    event_name: GitHub Actions `GITHUB_EVENT_NAME` (e.g., `pull_request`).
    event_payload: Decoded JSON from `GITHUB_EVENT_PATH`.

  Returns:
    True if the PR code review workflow should execute, False otherwise.
  """
  code_cfg = repo_config.scenarios.code_changes
  if not code_cfg.enabled:
    return False

  action = str(event_payload.get('action', '')).strip()
  qualified_event = f'{event_name}.{action}' if action else event_name
  if qualified_event not in code_cfg.triggers:
    return False

  if event_name == 'pull_request':
    pull_request = event_payload.get('pull_request') or {}
    if not isinstance(pull_request, Mapping):
      return False
    if pull_request.get('draft', False):
      return False
    pr_assoc = str(pull_request.get('author_association') or '').strip().upper()
    if pr_assoc not in code_cfg.allowed_author_associations:
      return False
    if not code_cfg.allow_fork_prs and is_fork_pull_request(pull_request):
      return False
    head_info = pull_request.get('head') or {}
    head_ref = str(head_info.get('ref', ''))
    if head_ref.startswith(COMPANION_BRANCH_PREFIX) or head_ref.startswith(
        ISSUE_COMPANION_BRANCH_PREFIX
    ):
      return False
    return True

  if event_name == 'issue_comment':
    issue = event_payload.get('issue') or {}
    if not isinstance(issue, Mapping) or 'pull_request' not in issue:
      return False
    comment = event_payload.get('comment') or {}
    if not isinstance(comment, Mapping):
      return False
    author_assoc = str(comment.get('author_association') or '').strip().upper()
    if author_assoc not in code_cfg.allowed_author_associations:
      return False
    raw_body = comment.get('body')
    comment_body = str(raw_body) if isinstance(raw_body, str) else ''
    return _matches_trigger_command(comment_body, code_cfg.trigger_command)

  return False


def should_trigger_issue_implementation(
    repo_config: AutoCloudRepoConfig,
    event_name: str,
    event_payload: Mapping[str, Any],
) -> bool:
  """Determines whether a GitHub event should trigger Issue Implementation.

  Strictly ignores Pull Request events and Pull Request comments (`'pull_request'
  in issue`), enforces `allowed_author_associations`, applies optional
  `trigger_labels` filtering to `issues.opened` / `issues.labeled`, and matches
  `trigger_command` on `issue_comment.created`.

  Args:
    repo_config: Validated repository configuration.
    event_name: GitHub Actions `GITHUB_EVENT_NAME` (`issues` or `issue_comment`).
    event_payload: Decoded JSON from `GITHUB_EVENT_PATH`.

  Returns:
    True if the Issue Implementation workflow should execute, False otherwise.
  """
  issue_cfg = repo_config.scenarios.issue_implementation
  if not issue_cfg.enabled:
    return False

  action = str(event_payload.get('action', '')).strip()
  qualified_event = f'{event_name}.{action}' if action else event_name
  if qualified_event not in issue_cfg.triggers:
    return False

  issue = event_payload.get('issue') or {}
  if not isinstance(issue, Mapping) or 'pull_request' in issue:
    return False

  if event_name == 'issues':
    issue_assoc = str(issue.get('author_association') or '').strip().upper()
    if issue_assoc not in issue_cfg.allowed_author_associations:
      return False

    if action == 'labeled':
      if not issue_cfg.trigger_labels:
        return False
      allowed_labels = {lbl.lower() for lbl in issue_cfg.trigger_labels}
      label_obj = event_payload.get('label')
      added_name = (
          str(label_obj.get('name', '')).strip().lower()
          if isinstance(label_obj, Mapping)
          else ''
      )
      return bool(added_name and added_name in allowed_labels)

    if issue_cfg.trigger_labels:
      allowed_labels = {lbl.lower() for lbl in issue_cfg.trigger_labels}
      issue_labels = _extract_issue_label_names(issue)
      return bool(issue_labels & allowed_labels)

    return True

  if event_name == 'issue_comment':
    comment = event_payload.get('comment') or {}
    if not isinstance(comment, Mapping):
      return False
    author_assoc = str(comment.get('author_association') or '').strip().upper()
    if author_assoc not in issue_cfg.allowed_author_associations:
      return False
    raw_body = comment.get('body')
    comment_body = str(raw_body) if isinstance(raw_body, str) else ''
    return _matches_trigger_command(comment_body, issue_cfg.trigger_command)

  return False
