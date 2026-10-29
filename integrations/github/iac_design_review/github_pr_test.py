"""Unit tests for github_pr.py workspace writer and GitHub REST API client."""

import os
import tempfile
from unittest import mock

from absl.testing import absltest
import requests

from iac_design_review import github_pr
from iac_design_review import parser


class GitHubPrTest(absltest.TestCase):
  """Tests safe workspace file writing, branch validation, and PR API calls."""

  def test_write_remediated_files_safely_writes_within_workspace(self):
    with tempfile.TemporaryDirectory() as tmp_dir:
      files = [
          parser.RemediatedFile(
              path='envs/prod/main.tf',
              content='resource "google_storage_bucket" "b" {}',
          )
      ]
      written = github_pr.write_remediated_files_safely(tmp_dir, files)
      self.assertEqual(written, ['envs/prod/main.tf'])
      full_path = os.path.join(tmp_dir, 'envs/prod/main.tf')
      with open(full_path, encoding='utf-8') as f:
        self.assertEqual(
            f.read(), 'resource "google_storage_bucket" "b" {}\n'
        )

  def test_write_remediated_files_rejects_symlink_escape(self):
    with tempfile.TemporaryDirectory() as workspace_dir, (
        tempfile.TemporaryDirectory()
    ) as outside_dir:
      escape_link = os.path.join(workspace_dir, 'escaped_dir')
      os.symlink(outside_dir, escape_link)

      files = [
          parser.RemediatedFile(
              path='escaped_dir/pwn.tf',
              content='malicious = true',
          )
      ]
      with self.assertRaises(ValueError):
        github_pr.write_remediated_files_safely(workspace_dir, files)

  def test_validate_branch_name_blocks_option_injection(self):
    self.assertEqual(
        github_pr.validate_branch_name('cloud-operator/remediate-pr-42'),
        'cloud-operator/remediate-pr-42',
    )
    for unsafe_branch in (
        '--upload-pack=evil',
        '-f',
        'feat/../main',
        'branch with spaces',
        '',
    ):
      with self.assertRaises(ValueError):
        github_pr.validate_branch_name(unsafe_branch)

  @mock.patch.object(requests, 'request', autospec=True)
  def test_create_or_update_companion_pr_creates_new_pr(self, mock_request):
    list_resp = mock.MagicMock(status_code=200, text='[]')
    list_resp.json.return_value = []
    create_resp = mock.MagicMock(
        status_code=201,
        text='{"html_url": "https://github.com/org/repo/pull/99"}',
    )
    create_resp.json.return_value = {
        'html_url': 'https://github.com/org/repo/pull/99'
    }
    mock_request.side_effect = [list_resp, create_resp]

    client = github_pr.GitHubClient(github_token='fake-github-token')
    pr_url = client.create_or_update_companion_pr(
        repo_full_name='org/repo',
        source_pr_number=42,
        pr_head_branch='feat/new-bucket',
        companion_branch='cloud-operator/remediate-pr-42',
        summary_markdown='Fixed public access prevention.',
    )

    self.assertEqual(pr_url, 'https://github.com/org/repo/pull/99')
    self.assertEqual(mock_request.call_count, 2)
    post_call = mock_request.call_args_list[1]
    self.assertEqual(post_call.kwargs['method'], 'POST')
    self.assertEqual(
        post_call.kwargs['json']['base'], 'feat/new-bucket'
    )
    self.assertEqual(
        post_call.kwargs['json']['head'], 'cloud-operator/remediate-pr-42'
    )

  @mock.patch.object(requests, 'request', autospec=True)
  def test_post_pr_review_sends_inline_comments(self, mock_request):
    review_resp = mock.MagicMock(
        status_code=200,
        text=(
            '{"html_url": '
            '"https://github.com/org/repo/pull/42#pullrequestreview-1"}'
        ),
    )
    review_resp.json.return_value = {
        'html_url': 'https://github.com/org/repo/pull/42#pullrequestreview-1'
    }
    mock_request.return_value = review_resp

    client = github_pr.GitHubClient(github_token='fake-github-token')
    url = client.post_pr_review(
        repo_full_name='org/repo',
        pr_number=42,
        body='Summary of findings.',
        inline_comments=[
            parser.InlineReviewComment(
                path='main.tf',
                line=10,
                start_line=8,
                body='Fix this block.',
            )
        ],
    )
    self.assertEqual(
        url, 'https://github.com/org/repo/pull/42#pullrequestreview-1'
    )
    call_kwargs = mock_request.call_args.kwargs
    self.assertEqual(call_kwargs['method'], 'POST')
    self.assertIn('/repos/org/repo/pulls/42/reviews', call_kwargs['url'])
    self.assertEqual(call_kwargs['json']['event'], 'COMMENT')
    self.assertEqual(
        call_kwargs['json']['comments'],
        [{
            'path': 'main.tf',
            'line': 10,
            'side': 'RIGHT',
            'start_line': 8,
            'start_side': 'RIGHT',
            'body': 'Fix this block.',
        }],
    )

  @mock.patch.object(requests, 'request', autospec=True)
  def test_post_pr_review_falls_back_to_issue_comment_on_422(
      self, mock_request
  ):
    err_resp = mock.MagicMock(status_code=422, text='{"message": "Invalid"}')
    fallback_resp = mock.MagicMock(
        status_code=201,
        text='{"html_url": "https://github.com/org/repo/pull/42#issuecomment-1"}',
    )
    fallback_resp.json.return_value = {
        'html_url': 'https://github.com/org/repo/pull/42#issuecomment-1'
    }
    mock_request.side_effect = [err_resp, fallback_resp]

    client = github_pr.GitHubClient(github_token='fake-github-token')
    url = client.post_pr_review(
        repo_full_name='org/repo',
        pr_number=42,
        body='Summary of findings.',
        inline_comments=[
            parser.InlineReviewComment(
                path='main.tf',
                line=999,
                body='Line outside diff hunk.',
            )
        ],
    )
    self.assertEqual(
        url, 'https://github.com/org/repo/pull/42#issuecomment-1'
    )
    self.assertEqual(mock_request.call_count, 2)

  @mock.patch.object(requests, 'request', autospec=True)
  def test_post_pr_review_clamps_and_partitions_against_diff_hunks(
      self, mock_request
  ):
    files_resp = mock.MagicMock(status_code=200, text='[...] ')
    files_resp.json.return_value = [
        {
            'filename': 'variables.tf',
            'status': 'added',
            'patch': '@@ -0,0 +1,23 @@\n+variable "project_id" {}',
        },
        {
            'filename': 'main.tf',
            'status': 'modified',
            'patch': '@@ -10,4 +10,6 @@\n+resource "a" "b" {}',
        },
    ]
    review_resp = mock.MagicMock(
        status_code=200,
        text=(
            '{"html_url": '
            '"https://github.com/org/repo/pull/1#pullrequestreview-9"}'
        ),
    )
    review_resp.json.return_value = {
        'html_url': 'https://github.com/org/repo/pull/1#pullrequestreview-9'
    }
    mock_request.side_effect = [files_resp, review_resp]

    client = github_pr.GitHubClient(github_token='fake-github-token')
    changed = client.list_pr_changed_files('org/repo', 1)
    self.assertEqual(changed, ['variables.tf', 'main.tf'])

    url = client.post_pr_review(
        repo_full_name='org/repo',
        pr_number=1,
        body='Summary of findings.',
        inline_comments=[
            parser.InlineReviewComment(
                path='variables.tf',
                start_line=21,
                line=25,
                body='Migrate gcr.io to Artifact Registry.',
            ),
            parser.InlineReviewComment(
                path='main.tf',
                line=100,
                body='Untouched line outside PR diff hunk.',
            ),
        ],
    )
    self.assertEqual(
        url, 'https://github.com/org/repo/pull/1#pullrequestreview-9'
    )
    review_call = mock_request.call_args_list[1]
    sent_json = review_call.kwargs['json']
    self.assertEqual(
        sent_json['comments'],
        [{
            'path': 'variables.tf',
            'start_line': 19,
            'start_side': 'RIGHT',
            'line': 23,
            'side': 'RIGHT',
            'body': 'Migrate gcr.io to Artifact Registry.',
        }],
    )
    self.assertIn(
        '### Additional Findings (Outside PR Diff Hunks)', sent_json['body']
    )
    self.assertIn('`main.tf:L100`', sent_json['body'])

  @mock.patch.object(requests, 'request', autospec=True)
  def test_post_pr_review_routes_partially_out_of_hunk_suggestions_to_body(
      self, mock_request
  ):
    files_resp = mock.MagicMock(status_code=200, text='[...]')
    files_resp.json.return_value = [
        {
            'filename': 'main.tf',
            'status': 'modified',
            'patch': '@@ -10,4 +10,6 @@\n+resource "a" "b" {}',
        },
        {
            'filename': 'variables.tf',
            'status': 'added',
            'patch': '@@ -0,0 +1,23 @@\n+variable "project_id" {}',
        },
    ]
    review_resp = mock.MagicMock(
        status_code=200,
        text=(
            '{"html_url": '
            '"https://github.com/org/repo/pull/2#pullrequestreview-10"}'
        ),
    )
    review_resp.json.return_value = {
        'html_url': 'https://github.com/org/repo/pull/2#pullrequestreview-10'
    }
    mock_request.side_effect = [files_resp, review_resp]

    client = github_pr.GitHubClient(github_token='fake-github-token')
    client.list_pr_changed_files('org/repo', 2)

    client.post_pr_review(
        repo_full_name='org/repo',
        pr_number=2,
        body='Summary of findings.',
        inline_comments=[
            parser.InlineReviewComment(
                path='main.tf',
                start_line=11,
                line=14,
                body='In-hunk fix.\n```suggestion\nfixed = true\n```',
            ),
            parser.InlineReviewComment(
                path='main.tf',
                start_line=8,
                line=12,
                body='Starts before hunk.\n```suggestion\na = 1\n```',
            ),
            parser.InlineReviewComment(
                path='main.tf',
                start_line=13,
                line=18,
                body='Ends after hunk.\n```suggestion\nb = 2\n```',
            ),
            parser.InlineReviewComment(
                path='variables.tf',
                start_line=21,
                line=25,
                body='Whole-file EOF shift.\n```suggestion\nc = 3\n```',
            ),
        ],
    )

    sent_json = mock_request.call_args_list[1].kwargs['json']
    self.assertEqual(
        sent_json['comments'],
        [
            {
                'path': 'main.tf',
                'start_line': 11,
                'start_side': 'RIGHT',
                'line': 14,
                'side': 'RIGHT',
                'body': 'In-hunk fix.\n```suggestion\nfixed = true\n```',
            },
            {
                'path': 'variables.tf',
                'start_line': 19,
                'start_side': 'RIGHT',
                'line': 23,
                'side': 'RIGHT',
                'body': 'Whole-file EOF shift.\n```suggestion\nc = 3\n```',
            },
        ],
    )
    self.assertIn('`main.tf:L8-L12`', sent_json['body'])
    self.assertIn('`main.tf:L13-L18`', sent_json['body'])

  def test_companion_branch_for_issue_and_collect_workspace_files(self):
    self.assertEqual(
        github_pr.companion_branch_for_issue(12), 'cloud-operator/issue-12'
    )
    with self.assertRaises(ValueError):
      github_pr.companion_branch_for_issue(0)

    with tempfile.TemporaryDirectory() as tmp_dir:
      os.makedirs(os.path.join(tmp_dir, '.github', 'workflows'), exist_ok=True)
      os.makedirs(os.path.join(tmp_dir, '.terraform'), exist_ok=True)
      os.makedirs(os.path.join(tmp_dir, 'envs', 'prod'), exist_ok=True)

      with open(
          os.path.join(tmp_dir, '.github', 'cloud-operator.yml'),
          'w',
          encoding='utf-8',
      ) as f:
        f.write('version: 1\n')
      with open(
          os.path.join(tmp_dir, '.terraform.lock.hcl'), 'w', encoding='utf-8'
      ) as f:
        f.write('provider "registry.terraform.io/hashicorp/google" {}\n')
      with open(
          os.path.join(tmp_dir, 'README.md'), 'w', encoding='utf-8'
      ) as f:
        f.write('# Infra Repo\n')
      with open(
          os.path.join(tmp_dir, 'envs', 'prod', 'main.tf'),
          'w',
          encoding='utf-8',
      ) as f:
        f.write('resource "google_storage_bucket" "b" {}\n')
      with open(os.path.join(tmp_dir, 'binary.tf'), 'wb') as f:
        f.write(b'\x00\x01\x02')

      collected = github_pr.collect_workspace_files(tmp_dir)
      self.assertEqual(
          list(collected.keys()),
          ['envs/prod/main.tf', 'README.md'],
      )
      self.assertIn('google_storage_bucket', collected['envs/prod/main.tf'])

  @mock.patch.object(requests, 'request', autospec=True)
  def test_create_or_update_companion_pr_supports_issue_resolution(
      self, mock_request
  ):
    list_resp = mock.MagicMock(status_code=200, text='[]')
    list_resp.json.return_value = []
    create_resp = mock.MagicMock(
        status_code=201,
        text='{"html_url": "https://github.com/org/repo/pull/105"}',
    )
    create_resp.json.return_value = {
        'html_url': 'https://github.com/org/repo/pull/105'
    }
    open_list_resp = mock.MagicMock(status_code=200, text='[{"number": 105}]')
    open_list_resp.json.return_value = [{'number': 105}]
    mock_request.side_effect = [list_resp, create_resp, open_list_resp]

    client = github_pr.GitHubClient(github_token='fake-github-token')
    pr_url = client.create_or_update_companion_pr(
        repo_full_name='org/repo',
        source_issue_number=12,
        issue_title='Add Cloud Armor WAF policy',
        pr_head_branch='main',
        companion_branch='cloud-operator/issue-12',
        summary_markdown='Added Cloud Armor security policy.',
    )

    self.assertEqual(pr_url, 'https://github.com/org/repo/pull/105')
    post_call = mock_request.call_args_list[1]
    self.assertEqual(post_call.kwargs['method'], 'POST')
    self.assertEqual(post_call.kwargs['json']['base'], 'main')
    self.assertEqual(
        post_call.kwargs['json']['head'], 'cloud-operator/issue-12'
    )
    self.assertEqual(
        post_call.kwargs['json']['title'],
        '[Cloud Operator] Resolve Issue #12: Add Cloud Armor WAF policy',
    )
    self.assertIn('Closes #12', post_call.kwargs['json']['body'])

    self.assertTrue(
        client.has_open_companion_pr(
            repo_full_name='org/repo',
            base_branch='main',
            companion_branch='cloud-operator/issue-12',
        )
    )


if __name__ == '__main__':
  absltest.main()
