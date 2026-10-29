"""Unit tests for runner_main.py."""

import json
import os
import tempfile
from unittest import mock

from absl.testing import absltest
import requests

from iac_design_review import auth
from iac_design_review import github_pr
from iac_design_review import mcp_client
from iac_design_review import parser
from iac_design_review import runner_main


def _write_test_config(repo_dir: str) -> str:
  """Writes a minimal `.github/cloud-operator.yml` for runner unit tests."""
  github_dir = os.path.join(repo_dir, '.github')
  os.makedirs(github_dir, exist_ok=True)
  cfg_path = os.path.join(github_dir, 'cloud-operator.yml')
  with open(cfg_path, 'w', encoding='utf-8') as f:
    f.write('version: 1\nproject_id: "my-gcp-project"\n')
  return cfg_path


class RunnerMainTest(absltest.TestCase):
  """Tests end-to-end GitHub Action runner execution and dry-run modes."""

  @mock.patch.object(requests, 'post', autospec=True)
  def test_runner_dry_run_remediates_workspace_file(self, mock_post):
    remediated_md = (
        '### Findings\nAdded uniform_bucket_level_access.\n\n'
        '```hcl title="main.tf"\n'
        'resource "google_storage_bucket" "demo" {\n'
        '  uniform_bucket_level_access = true\n'
        '}\n'
        '```\n'
    )
    rpc_response = {
        'jsonrpc': '2.0',
        'id': '1',
        'result': {
            'structuredContent': {
                'content': remediated_md,
                'context_id': 'ctx-dry-run',
            }
        },
    }
    mock_post.return_value = mock.MagicMock(
        status_code=200, text=json.dumps(rpc_response)
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
      cfg_path = _write_test_config(tmp_dir)
      tf_path = os.path.join(tmp_dir, 'main.tf')
      with open(tf_path, 'w', encoding='utf-8') as tf_file:
        tf_file.write('resource "google_storage_bucket" "demo" {}\n')

      exit_code = runner_main.run_action(
          workspace_dir=tmp_dir,
          config_path=cfg_path,
          event_name='pull_request',
          event_payload={},
          repo_full_name='org/demo',
          mcp_url=mcp_client.DEFAULT_PROD_MCP_URL,
          tokens=auth.StaticTokenSource('fake-static-token'),
          github_client=None,
          dry_run_github=True,
          override_changed_files=['main.tf'],
      )
      self.assertEqual(exit_code, 0)
      with open(tf_path, encoding='utf-8') as tf_file:
        updated_tf = tf_file.read()
      self.assertIn('uniform_bucket_level_access = true', updated_tf)

  @mock.patch.object(requests, 'post', autospec=True)
  def test_runner_default_inline_comments_posts_pr_review_without_companion_pr(
      self, mock_post
  ):
    remediated_md = (
        '### Findings\nAdded uniform_bucket_level_access.\n\n'
        '```hcl title="main.tf"\n'
        'resource "google_storage_bucket" "demo" {\n'
        '  uniform_bucket_level_access = true\n'
        '}\n'
        '```\n'
    )
    rpc_response = {
        'jsonrpc': '2.0',
        'id': '1',
        'result': {
            'structuredContent': {
                'content': remediated_md,
                'context_id': 'ctx-inline-1',
            }
        },
    }
    mock_post.return_value = mock.MagicMock(
        status_code=200, text=json.dumps(rpc_response)
    )

    mock_gh = mock.MagicMock()
    mock_gh.list_pr_changed_files.return_value = ['main.tf']
    mock_gh.list_issue_comments.return_value = []
    mock_gh.list_pr_review_bodies.return_value = []

    with tempfile.TemporaryDirectory() as tmp_dir:
      cfg_path = _write_test_config(tmp_dir)
      tf_path = os.path.join(tmp_dir, 'main.tf')
      with open(tf_path, 'w', encoding='utf-8') as tf_file:
        tf_file.write('resource "google_storage_bucket" "demo" {}\n')

      event_payload = {
          'action': 'opened',
          'pull_request': {
              'number': 42,
              'title': 'Add GCS bucket',
              'draft': False,
              'author_association': 'OWNER',
              'head': {'ref': 'feat/bucket'},
          },
      }
      exit_code = runner_main.run_action(
          workspace_dir=tmp_dir,
          config_path=cfg_path,
          event_name='pull_request',
          event_payload=event_payload,
          repo_full_name='org/demo',
          mcp_url=mcp_client.DEFAULT_PROD_MCP_URL,
          tokens=auth.StaticTokenSource('fake-static-token'),
          github_client=mock_gh,
          dry_run_github=False,
      )
      self.assertEqual(exit_code, 0)
      mock_gh.post_pr_review.assert_called_once()
      mock_gh.create_or_update_companion_pr.assert_not_called()
      _, kwargs = mock_gh.post_pr_review.call_args
      self.assertLen(kwargs['inline_comments'], 1)
      self.assertEqual(kwargs['inline_comments'][0].path, 'main.tf')
      self.assertIn('```suggestion', kwargs['inline_comments'][0].body)

  @mock.patch.object(github_pr, 'checkout_pr_head', autospec=True)
  @mock.patch.object(requests, 'post', autospec=True)
  def test_runner_issue_comment_skips_companion_pr_branch(
      self, mock_post, mock_checkout
  ):
    mock_gh = mock.MagicMock()
    mock_gh.get_pr_metadata.return_value = (
        '[Cloud Operator] IaC & Code Remediations for PR #42',
        'cloud-operator/remediate-pr-42',
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
      cfg_path = _write_test_config(tmp_dir)
      event_payload = {
          'action': 'created',
          'issue': {'number': 99, 'pull_request': {}},
          'comment': {
              'author_association': 'OWNER',
              'body': '/cloud-operator review',
          },
      }
      exit_code = runner_main.run_action(
          workspace_dir=tmp_dir,
          config_path=cfg_path,
          event_name='issue_comment',
          event_payload=event_payload,
          repo_full_name='org/demo',
          mcp_url=mcp_client.DEFAULT_PROD_MCP_URL,
          tokens=auth.StaticTokenSource('fake-static-token'),
          github_client=mock_gh,
          dry_run_github=False,
      )
      self.assertEqual(exit_code, 0)
      mock_checkout.assert_not_called()
      mock_post.assert_not_called()

  @mock.patch.object(github_pr, 'checkout_pr_head', autospec=True)
  def test_runner_issue_comment_propagates_checkout_error(self, mock_checkout):
    mock_checkout.side_effect = github_pr.GitHubIntegrationError(
        'git fetch failed'
    )
    mock_gh = mock.MagicMock()
    mock_gh.get_pr_metadata.return_value = ('Add GCS bucket', 'feat/bucket')
    mock_gh.is_pr_from_fork.return_value = False

    with tempfile.TemporaryDirectory() as tmp_dir:
      cfg_path = _write_test_config(tmp_dir)
      event_payload = {
          'action': 'created',
          'issue': {'number': 42, 'pull_request': {}},
          'comment': {
              'author_association': 'OWNER',
              'body': '/cloud-operator review',
          },
      }
      with self.assertRaisesRegex(
          github_pr.GitHubIntegrationError, 'git fetch failed'
      ):
        runner_main.run_action(
            workspace_dir=tmp_dir,
            config_path=cfg_path,
            event_name='issue_comment',
            event_payload=event_payload,
            repo_full_name='org/demo',
            mcp_url=mcp_client.DEFAULT_PROD_MCP_URL,
            tokens=auth.StaticTokenSource('fake-static-token'),
            github_client=mock_gh,
            dry_run_github=False,
        )

  @mock.patch.object(github_pr, 'checkout_pr_head', autospec=True)
  @mock.patch.object(requests, 'post', autospec=True)
  def test_runner_issue_comment_appends_comment_body_to_prompt(
      self, mock_post, mock_checkout
  ):
    rpc_response = {
        'jsonrpc': '2.0',
        'id': '1',
        'result': {
            'structuredContent': {
                'content': '### Findings\nVPC-SC looks good.',
                'context_id': 'ctx-turn-2',
            }
        },
    }
    mock_post.return_value = mock.MagicMock(
        status_code=200, text=json.dumps(rpc_response)
    )

    mock_gh = mock.MagicMock()
    mock_gh.get_pr_metadata.return_value = ('Add GCS bucket', 'feat/bucket')
    mock_gh.is_pr_from_fork.return_value = False
    mock_gh.list_pr_changed_files.return_value = ['main.tf']
    mock_gh.list_issue_comments.return_value = [
        parser.embed_context_id_marker('Prior summary.', 'ctx-turn-1')
    ]
    mock_gh.list_pr_review_bodies.return_value = []

    with tempfile.TemporaryDirectory() as tmp_dir:
      cfg_path = _write_test_config(tmp_dir)
      tf_path = os.path.join(tmp_dir, 'main.tf')
      with open(tf_path, 'w', encoding='utf-8') as tf_file:
        tf_file.write('resource "google_storage_bucket" "demo" {}\n')

      event_payload = {
          'action': 'created',
          'issue': {'number': 42, 'pull_request': {}},
          'comment': {
              'author_association': 'OWNER',
              'body': (
                  '/cloud-operator review please focus on VPC Service Controls'
              ),
          },
      }
      exit_code = runner_main.run_action(
          workspace_dir=tmp_dir,
          config_path=cfg_path,
          event_name='issue_comment',
          event_payload=event_payload,
          repo_full_name='org/demo',
          mcp_url=mcp_client.DEFAULT_PROD_MCP_URL,
          tokens=auth.StaticTokenSource('fake-static-token'),
          github_client=mock_gh,
          dry_run_github=False,
      )
      self.assertEqual(exit_code, 0)
      mock_checkout.assert_called_once_with(tmp_dir, 42)
      sent_rpc = mock_post.call_args.kwargs['json']
      sent_args = sent_rpc['params']['arguments']
      self.assertEqual(sent_args['contextId'], 'ctx-turn-1')
      self.assertIn(
          '/cloud-operator review please focus on VPC Service Controls',
          sent_args['userQuery'],
      )


if __name__ == '__main__':
  absltest.main()
