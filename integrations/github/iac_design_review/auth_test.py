"""Unit tests for auth.py."""

import json
from unittest import mock

from absl.testing import absltest
import requests

from iac_design_review import auth


class AuthTest(absltest.TestCase):
  """Tests OAuth refresh token exchange and token source construction."""

  @mock.patch.object(requests, 'post', autospec=True)
  def test_oauth_refresh_token_source_caches_token(self, mock_post):
    mock_resp = mock.MagicMock(status_code=200)
    mock_resp.json.return_value = {
        'access_token': 'fake-human-euc-token',
        'expires_in': 3600,
    }
    mock_post.return_value = mock_resp

    raw_secret = json.dumps({
        'client_id': 'fake-client-id',
        'client_secret': 'fake-client-secret',
        'refresh_token': 'fake-refresh-token',
    })
    source = auth.OAuthRefreshTokenSource.from_json_string(raw_secret)
    self.assertEqual(source.token(), 'fake-human-euc-token')
    self.assertEqual(source.token(), 'fake-human-euc-token')
    self.assertEqual(mock_post.call_count, 1)

  def test_static_token_source_rejects_empty_token(self):
    source = auth.StaticTokenSource('')
    with self.assertRaises(auth.TokenSourceError):
      source.token()

  def test_build_token_source_fails_closed_when_missing_credentials(self):
    with self.assertRaises(auth.TokenSourceError):
      auth.build_token_source(oauth_config_json='', use_local_adc=False)

  def test_from_json_string_rejects_null_fields(self):
    raw_secret = json.dumps({
        'client_id': 'fake-client-id',
        'client_secret': 'fake-client-secret',
        'refresh_token': None,
    })
    with self.assertRaises(auth.TokenSourceError):
      auth.OAuthRefreshTokenSource.from_json_string(raw_secret)

  @mock.patch.object(requests, 'post', autospec=True)
  def test_token_rejects_non_dict_or_null_access_token_or_bad_expires_in(
      self, mock_post
  ):
    raw_secret = json.dumps({
        'client_id': 'fake-client-id',
        'client_secret': 'fake-client-secret',
        'refresh_token': 'fake-refresh-token',
    })
    for bad_payload in (
        ['not-a-dict'],
        {'access_token': None, 'expires_in': 3600},
        {'access_token': 'fake-human-euc-token', 'expires_in': 'not-an-int'},
        {'access_token': 'fake-human-euc-token', 'expires_in': True},
    ):
      mock_resp = mock.MagicMock(status_code=200)
      mock_resp.json.return_value = bad_payload
      mock_post.return_value = mock_resp
      source = auth.OAuthRefreshTokenSource.from_json_string(raw_secret)
      with self.assertRaises(auth.TokenSourceError):
        source.token()


if __name__ == '__main__':
  absltest.main()
