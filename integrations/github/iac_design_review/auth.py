"""Human Google EUC token sources for Cloud Operator MCP calls.

The Cloud Operator agent requires human Google end-user credentials (EUC)
and rejects service accounts or federated workload tokens. In GitHub Actions,
an offline OAuth 2.0 refresh token (`CLOUD_OPERATOR_OAUTH_CONFIG`) minted during
onboarding (`cloud-operator-github-init`) is exchanged in-memory against
Google's OAuth 2.0 token endpoint (`https://oauth2.googleapis.com/token`) to
obtain short-lived (~1h) human access tokens.

Security invariants:
  * Secrets and tokens are never logged, persisted to disk, or echoed in errors.
  * Missing or invalid credentials fail closed (`TokenSourceError`).
"""

import json
import os
import threading
import time
from typing import Protocol

from absl import logging
import requests

_GOOGLE_TOKEN_URI = 'https://oauth2.googleapis.com/token'
_REFRESH_MARGIN_SECONDS = 120
_TOKEN_TIMEOUT_SECONDS = 15
_DEFAULT_ADC_PATH = os.path.expanduser(
    '~/.config/gcloud/application_default_credentials.json'
)


class TokenSourceError(RuntimeError):
  """Raised when no usable human EUC access token can be obtained."""


class TokenSource(Protocol):
  """Supplies an OAuth 2.0 Bearer access token for a human Google identity."""

  def token(self) -> str:
    """Returns a valid Bearer token or raises `TokenSourceError`."""


class StaticTokenSource:
  """Returns a fixed bearer token. Intended strictly for unit tests."""

  def __init__(self, token_value: str):
    """Initializes the static token source.

    Args:
      token_value: Non-empty static token string for test assertions.
    """
    self._token_value = token_value

  def token(self) -> str:
    """Returns the static token or raises `TokenSourceError` if empty."""
    if not self._token_value:
      raise TokenSourceError('Static token is empty.')
    return self._token_value


class OAuthRefreshTokenSource:
  """Exchanges a stored OAuth 2.0 refresh token for short-lived human EUC."""

  def __init__(self, client_id: str, client_secret: str, refresh_token: str):
    """Initializes the refresh token source.

    Args:
      client_id: OAuth 2.0 client ID.
      client_secret: OAuth 2.0 client secret.
      refresh_token: Offline OAuth 2.0 refresh token for the human owner.

    Raises:
      TokenSourceError: If any credential field is empty.
    """
    if not (client_id and client_secret and refresh_token):
      raise TokenSourceError(
          'OAuth configuration must include client_id, client_secret, and '
          'refresh_token.'
      )
    self._client_id = client_id
    self._client_secret = client_secret
    self._refresh_token = refresh_token
    self._lock = threading.Lock()
    self._cached_token: str = ''
    self._expiry_epoch: float = 0.0

  @classmethod
  def from_json_string(cls, raw_json: str) -> 'OAuthRefreshTokenSource':
    """Constructs an `OAuthRefreshTokenSource` from a JSON secret string.

    Args:
      raw_json: JSON string containing `client_id`, `client_secret`, and
        `refresh_token` (e.g., from `CLOUD_OPERATOR_OAUTH_CONFIG`).

    Returns:
      Configured `OAuthRefreshTokenSource` instance.

    Raises:
      TokenSourceError: If JSON is empty, malformed, or missing keys.
    """
    if not raw_json or not raw_json.strip():
      raise TokenSourceError('OAuth configuration JSON is empty.')
    try:
      parsed = json.loads(raw_json)
    except json.JSONDecodeError as err:
      raise TokenSourceError(
          'OAuth configuration is not valid JSON.'
      ) from err
    if not isinstance(parsed, dict):
      raise TokenSourceError('OAuth configuration JSON must be an object.')
    raw_client_id = parsed.get('client_id')
    raw_client_secret = parsed.get('client_secret')
    raw_refresh_token = parsed.get('refresh_token')
    if not (
        isinstance(raw_client_id, str)
        and isinstance(raw_client_secret, str)
        and isinstance(raw_refresh_token, str)
    ):
      raise TokenSourceError(
          'OAuth configuration client_id, client_secret, and refresh_token '
          'must be strings.'
      )
    return cls(
        client_id=raw_client_id.strip(),
        client_secret=raw_client_secret.strip(),
        refresh_token=raw_refresh_token.strip(),
    )

  @classmethod
  def from_adc_file(
      cls, adc_path: str = _DEFAULT_ADC_PATH
  ) -> 'OAuthRefreshTokenSource':
    """Constructs an `OAuthRefreshTokenSource` from a local ADC JSON file.

    Args:
      adc_path: Path to `application_default_credentials.json`.

    Returns:
      Configured `OAuthRefreshTokenSource` instance.

    Raises:
      TokenSourceError: If the ADC file cannot be read or lacks user tokens.
    """
    try:
      with open(adc_path, encoding='utf-8') as adc_file:
        raw_json = adc_file.read()
    except OSError as err:
      raise TokenSourceError(
          f'Could not read local ADC file at {adc_path!r}. '
          'Run `gcloud auth application-default login` first.'
      ) from err
    return cls.from_json_string(raw_json)

  def token(self) -> str:
    """Returns a cached or freshly minted human OAuth 2.0 access token.

    Returns:
      Short-lived Bearer access token string.

    Raises:
      TokenSourceError: If token exchange with Google OAuth fails.
    """
    with self._lock:
      now = time.time()
      if (
          self._cached_token
          and now + _REFRESH_MARGIN_SECONDS < self._expiry_epoch
      ):
        return self._cached_token

      payload = {
          'client_id': self._client_id,
          'client_secret': self._client_secret,
          'refresh_token': self._refresh_token,
          'grant_type': 'refresh_token',
      }
      try:
        response = requests.post(
            _GOOGLE_TOKEN_URI,
            data=payload,
            timeout=_TOKEN_TIMEOUT_SECONDS,
        )
      except requests.RequestException as err:
        raise TokenSourceError(
            'Network error communicating with Google OAuth token endpoint.'
        ) from err

      if response.status_code != 200:
        raise TokenSourceError(
            f'Google OAuth token endpoint returned HTTP {response.status_code}.'
        )

      try:
        token_data = response.json()
      except ValueError as err:
        raise TokenSourceError(
            'Google OAuth token endpoint returned non-JSON body.'
        ) from err

      if not isinstance(token_data, dict):
        raise TokenSourceError(
            'Google OAuth token endpoint returned non-object JSON.'
        )

      raw_access_token = token_data.get('access_token')
      if not isinstance(raw_access_token, str) or not raw_access_token.strip():
        raise TokenSourceError(
            'Google OAuth token refresh returned an empty access_token.'
        )
      access_token = raw_access_token.strip()

      raw_expires = token_data.get('expires_in', 3600)
      if isinstance(raw_expires, bool):
        raise TokenSourceError(
            'Google OAuth token refresh returned invalid expires_in.'
        )
      try:
        expires_in = int(raw_expires if raw_expires is not None else 3600)
      except (TypeError, ValueError) as err:
        raise TokenSourceError(
            'Google OAuth token refresh returned non-numeric expires_in.'
        ) from err
      self._cached_token = access_token
      self._expiry_epoch = now + expires_in
      logging.info(
          'Refreshed Google human EUC token (expires_in=%ds).', expires_in
      )
      return self._cached_token


def build_token_source(
    *,
    oauth_config_json: str = '',
    use_local_adc: bool = False,
    adc_path: str = _DEFAULT_ADC_PATH,
) -> TokenSource:
  """Builds the appropriate `TokenSource` for the execution environment.

  Args:
    oauth_config_json: Raw JSON string from `CLOUD_OPERATOR_OAUTH_CONFIG`
      secret.
    use_local_adc: Whether to read local workstation ADC credentials instead.
    adc_path: Path to local ADC file when `use_local_adc` is True.

  Returns:
    Configured `TokenSource` instance.

  Raises:
    TokenSourceError: If neither valid OAuth JSON nor local ADC is available.
  """
  if use_local_adc:
    logging.warning(
        'Using local workstation ADC credentials (--use_local_adc). '
        'Intended for Cloudtop smoke testing only.'
    )
    return OAuthRefreshTokenSource.from_adc_file(adc_path)

  if oauth_config_json:
    return OAuthRefreshTokenSource.from_json_string(oauth_config_json)

  raise TokenSourceError(
      'Missing CLOUD_OPERATOR_OAUTH_CONFIG secret and --use_local_adc is False.'
  )
