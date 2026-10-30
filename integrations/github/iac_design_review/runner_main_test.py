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
      pos_args, kwargs = mock_gh.post_pr_review.call_args
      posted_review_body = pos_args[2]
      self.assertIn('### Findings', posted_review_body)
      self.assertIn(
          'ℹ️ **Run / Session ID:** `ctx-inline-1`', posted_review_body
      )
      self.assertIn(
          '👇 **Detailed inline comments and 1-click code suggestions are '
          'added on the affected files below.**',
          posted_review_body,
      )
      self.assertNotIn('title="main.tf"', posted_review_body)
      self.assertNotIn('resource "google_storage_bucket"', posted_review_body)
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

  @mock.patch.object(
      github_pr, 'commit_and_push_companion_branch', autospec=True
  )
  @mock.patch.object(github_pr, 'checkout_branch', autospec=True)
  @mock.patch.object(requests, 'post', autospec=True)
  def test_runner_issue_opened_creates_companion_pr_and_comments_on_issue(
      self, mock_post, mock_checkout_branch, mock_commit_push
  ):
    implemented_md = (
        '### Implementation Summary\nCreated private Cloud Storage bucket.\n\n'
        '```hcl title="storage.tf"\n'
        'resource "google_storage_bucket" "logs" {\n'
        '  name                        = "acme-audit-logs"\n'
        '  location                    = "US"\n'
        '  uniform_bucket_level_access = true\n'
        '}\n'
        '```\n'
    )
    rpc_response = {
        'jsonrpc': '2.0',
        'id': '1',
        'result': {
            'structuredContent': {
                'content': implemented_md,
                'context_id': 'ctx-issue-11',
            }
        },
    }
    mock_post.return_value = mock.MagicMock(
        status_code=200, text=json.dumps(rpc_response)
    )
    mock_commit_push.return_value = True

    mock_gh = mock.MagicMock()
    mock_gh.list_issue_comments.return_value = []
    mock_gh.has_open_companion_pr.return_value = False
    mock_gh.create_or_update_companion_pr.return_value = (
        'https://github.com/org/demo/pull/12'
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
      cfg_path = _write_test_config(tmp_dir)
      with open(cfg_path, 'a', encoding='utf-8') as cfg_file:
        cfg_file.write(
            'scenarios:\n  issue_implementation:\n    enabled: true\n'
            '    base_branch: "main"\n'
        )
      with open(
          os.path.join(tmp_dir, 'main.tf'), 'w', encoding='utf-8'
      ) as tf_file:
        tf_file.write('terraform {}\n')

      event_payload = {
          'action': 'opened',
          'issue': {
              'number': 11,
              'title': 'Add private audit logs bucket',
              'body': 'Provision a GCS bucket for audit logs in US.',
              'author_association': 'OWNER',
              'labels': [{'name': 'enhancement'}],
          },
      }
      exit_code = runner_main.run_action(
          workspace_dir=tmp_dir,
          config_path=cfg_path,
          event_name='issues',
          event_payload=event_payload,
          repo_full_name='org/demo',
          mcp_url=mcp_client.DEFAULT_PROD_MCP_URL,
          tokens=auth.StaticTokenSource('fake-static-token'),
          github_client=mock_gh,
          dry_run_github=False,
      )
      self.assertEqual(exit_code, 0)
      mock_checkout_branch.assert_called_once_with(tmp_dir, 'main')
      mock_commit_push.assert_called_once_with(
          workspace_dir=tmp_dir,
          companion_branch='cloud-operator/issue-11',
          written_paths=['storage.tf'],
          issue_number=11,
          push_remote=True,
      )
      mock_gh.create_or_update_companion_pr.assert_called_once_with(
          repo_full_name='org/demo',
          source_issue_number=11,
          issue_title='Add private audit logs bucket',
          pr_head_branch='main',
          companion_branch='cloud-operator/issue-11',
          summary_markdown=(
              '### Implementation Summary\n'
              'Created private Cloud Storage bucket.'
          ),
      )
      mock_gh.post_issue_comment.assert_called_once()
      posted_body = mock_gh.post_issue_comment.call_args.args[2]
      self.assertIn(
          '### Cloud Operator Pull Request Opened: '
          'https://github.com/org/demo/pull/12',
          posted_body,
      )
      self.assertNotIn('title="storage.tf"', posted_body)
      self.assertNotIn('resource "google_storage_bucket"', posted_body)
      self.assertIn(
          '<!-- cloud-operator-context-id: ctx-issue-11 -->', posted_body
      )

  @mock.patch.object(
      github_pr, 'commit_and_push_companion_branch', autospec=True
  )
  @mock.patch.object(github_pr, 'checkout_branch', autospec=True)
  @mock.patch.object(requests, 'post', autospec=True)
  def test_runner_issue_comment_follow_up_without_files_posts_comment_only(
      self, mock_post, mock_checkout_branch, mock_commit_push
  ):
    rpc_response = {
        'jsonrpc': '2.0',
        'id': '1',
        'result': {
            'structuredContent': {
                'content': 'Which GCP region should the GKE cluster use?',
                'context_id': 'ctx-issue-11-turn-2',
            }
        },
    }
    mock_post.return_value = mock.MagicMock(
        status_code=200, text=json.dumps(rpc_response)
    )

    mock_gh = mock.MagicMock()
    mock_gh.list_issue_comments.return_value = [
        parser.embed_context_id_marker('Initial reply.', 'ctx-issue-11-turn-1')
    ]
    mock_gh.has_open_companion_pr.return_value = True

    with tempfile.TemporaryDirectory() as tmp_dir:
      cfg_path = _write_test_config(tmp_dir)
      with open(cfg_path, 'a', encoding='utf-8') as cfg_file:
        cfg_file.write(
            'scenarios:\n  issue_implementation:\n    enabled: true\n'
        )

      event_payload = {
          'action': 'created',
          'issue': {
              'number': 11,
              'title': 'Add GKE cluster',
              'body': 'Add Autopilot cluster.',
              'labels': [],
          },
          'comment': {
              'author_association': 'MEMBER',
              'body': '/cloud-operator implement check regional requirements',
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
      mock_checkout_branch.assert_called_once_with(
          tmp_dir, 'cloud-operator/issue-11'
      )
      mock_commit_push.assert_not_called()
      mock_gh.create_or_update_companion_pr.assert_not_called()
      sent_args = mock_post.call_args.kwargs['json']['params']['arguments']
      self.assertEqual(sent_args['contextId'], 'ctx-issue-11-turn-1')
      mock_gh.post_issue_comment.assert_called_once()

  @mock.patch.object(requests, 'request', autospec=True)
  @mock.patch.object(requests, 'post', autospec=True)
  def test_runner_pr_review_strips_remediated_block_and_highlights_out_of_diff_suggestions_in_body(
      self, mock_mcp_post, mock_gh_request
  ):
    original_main_tf = (
        'resource "google_storage_bucket" "pr_bucket" {\n'
        '  name                        = "pr-bucket"\n'
        '  uniform_bucket_level_access = false\n'
        '}\n'
        '\n'
        'resource "google_storage_bucket" "legacy_bucket" {\n'
        '  name                        = "legacy-bucket"\n'
        '  uniform_bucket_level_access = false\n'
        '}\n'
    )
    remediated_md = (
        '### Findings\n'
        'Both buckets should enable `uniform_bucket_level_access`.\n\n'
        '```hcl title="main.tf"\n'
        'resource "google_storage_bucket" "pr_bucket" {\n'
        '  name                        = "pr-bucket"\n'
        '  uniform_bucket_level_access = true\n'
        '}\n'
        '\n'
        'resource "google_storage_bucket" "legacy_bucket" {\n'
        '  name                        = "legacy-bucket"\n'
        '  uniform_bucket_level_access = true\n'
        '}\n'
        '```\n\n'
        '```json title="cloud-operator-inline-comments"\n'
        '[\n'
        '  {\n'
        '    "path": "main.tf",\n'
        '    "line": 3,\n'
        '    "body": "Enable UBLA on pr_bucket.",\n'
        '    "suggestion": "  uniform_bucket_level_access = true"\n'
        '  }\n'
        ']\n'
        '```\n'
    )
    rpc_response = {
        'jsonrpc': '2.0',
        'id': '1',
        'result': {
            'structuredContent': {
                'content': remediated_md,
                'context_id': 'ctx-out-of-diff',
            }
        },
    }
    mock_mcp_post.return_value = mock.MagicMock(
        status_code=200, text=json.dumps(rpc_response)
    )

    files_resp = mock.MagicMock(status_code=200, text='[...]')
    files_resp.json.return_value = [
        {
            'filename': 'main.tf',
            'status': 'modified',
            'patch': (
                '@@ -1,4 +1,4 @@\n'
                ' resource "google_storage_bucket" "pr_bucket" {\n'
                '   name                        = "pr-bucket"\n'
                '-  uniform_bucket_level_access = true\n'
                '+  uniform_bucket_level_access = false\n'
                ' }'
            ),
        }
    ]
    empty_list_resp = mock.MagicMock(status_code=200, text='[]')
    empty_list_resp.json.return_value = []
    review_resp = mock.MagicMock(
        status_code=200,
        text=(
            '{"html_url": '
            '"https://github.com/org/demo/pull/5#pullrequestreview-1"}'
        ),
    )
    review_resp.json.return_value = {
        'html_url': 'https://github.com/org/demo/pull/5#pullrequestreview-1'
    }
    mock_gh_request.side_effect = [
        files_resp,
        empty_list_resp,
        empty_list_resp,
        review_resp,
    ]

    gh_client = github_pr.GitHubClient(github_token='fake-gh-token')
    with tempfile.TemporaryDirectory() as tmp_dir:
      cfg_path = _write_test_config(tmp_dir)
      with open(
          os.path.join(tmp_dir, 'main.tf'), 'w', encoding='utf-8'
      ) as tf_file:
        tf_file.write(original_main_tf)

      event_payload = {
          'action': 'opened',
          'pull_request': {
              'number': 5,
              'title': 'Update pr_bucket',
              'draft': False,
              'author_association': 'OWNER',
              'head': {'ref': 'feat/pr-bucket'},
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
          github_client=gh_client,
          dry_run_github=False,
      )
      self.assertEqual(exit_code, 0)

    review_call = mock_gh_request.call_args_list[3]
    sent_review = review_call.kwargs['json']
    # 1. Full remediated file block is NOT in the review body.
    self.assertNotIn('title="main.tf"', sent_review['body'])
    self.assertNotIn(
        'resource "google_storage_bucket" "pr_bucket"', sent_review['body']
    )
    # 2. Line 3 (inside the PR diff hunk 1..4) is posted as an inline comment.
    self.assertLen(sent_review['comments'], 1)
    self.assertEqual(sent_review['comments'][0]['path'], 'main.tf')
    self.assertEqual(sent_review['comments'][0]['line'], 3)
    # 3. Line 8 (outside the PR diff hunk 1..4) is highlighted in the body.
    self.assertIn(
        '### Additional Findings (Outside PR Diff Hunks)', sent_review['body']
    )
    self.assertIn('`main.tf:L8`', sent_review['body'])
    self.assertIn(
        '```suggestion\n  uniform_bucket_level_access = true\n```',
        sent_review['body'],
    )

  @mock.patch.object(requests, 'post', autospec=True)
  def test_runner_comment_only_mode_preserves_remediated_block_in_comment(
      self, mock_post
  ):
    remediated_md = (
        '### Summary\n'
        'Enable uniform bucket-level access.\n\n'
        '```hcl title="main.tf"\n'
        'resource "google_storage_bucket" "b" {\n'
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
                'context_id': 'ctx-comment-only',
            }
        },
    }
    mock_post.return_value = mock.MagicMock(
        status_code=200, text=json.dumps(rpc_response)
    )

    mock_gh = mock.MagicMock()
    mock_gh.list_pr_changed_files.return_value = ['main.tf']
    mock_gh.list_pr_comments.return_value = []

    with tempfile.TemporaryDirectory() as tmp_dir:
      cfg_path = _write_test_config(tmp_dir)
      with open(cfg_path, 'a', encoding='utf-8') as cfg_file:
        cfg_file.write(
            'scenarios:\n  code_changes:\n    pr_mode: "comment_only"\n'
        )
      with open(
          os.path.join(tmp_dir, 'main.tf'), 'w', encoding='utf-8'
      ) as tf_file:
        tf_file.write('resource "google_storage_bucket" "b" {}\n')

      event_payload = {
          'action': 'opened',
          'pull_request': {
              'number': 9,
              'title': 'Add bucket',
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
      mock_gh.post_issue_comment.assert_called_once()
      posted_comment = mock_gh.post_issue_comment.call_args.args[2]
      self.assertIn('title="main.tf"', posted_comment)
      self.assertIn('uniform_bucket_level_access = true', posted_comment)


if __name__ == '__main__':
  absltest.main()
