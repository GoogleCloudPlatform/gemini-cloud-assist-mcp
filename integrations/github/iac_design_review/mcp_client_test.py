"""Unit tests for mcp_client.py."""

import json
from unittest import mock

from absl.testing import absltest
import requests

from iac_design_review import auth
from iac_design_review import mcp_client


class McpClientTest(absltest.TestCase):
  """Tests MCP JSON-RPC calls, prompt builder, and SSE progress streaming."""

  @mock.patch.object(requests, 'post', autospec=True)
  def test_ask_cloud_operator_sends_camelcase_args_and_headers(
      self, mock_post
  ):
    rpc_response = {
        'jsonrpc': '2.0',
        'id': 'corr-1',
        'result': {
            'structuredContent': {
                'content': 'Review complete.',
                'context_id': 'ctx-777',
            }
        },
    }
    mock_resp = mock.MagicMock(
        status_code=200, text=json.dumps(rpc_response)
    )
    mock_post.return_value = mock_resp

    tokens = auth.StaticTokenSource('fake-static-token')
    ans = mcp_client.ask_cloud_operator(
        tokens=tokens,
        mcp_url=mcp_client.DEFAULT_PROD_MCP_URL,
        project_id='projects/my-gcp-project',
        agent_id='operator-prod',
        user_query='Review main.tf',
        context_id='ctx-000',
        correlation_id='corr-1',
    )

    self.assertEqual(ans.content, 'Review complete.')
    self.assertEqual(ans.context_id, 'ctx-777')

    sent_json = mock_post.call_args.kwargs['json']
    sent_headers = mock_post.call_args.kwargs['headers']
    self.assertEqual(
        sent_headers['X-Goog-User-Project'], 'my-gcp-project'
    )
    self.assertEqual(sent_headers['Authorization'], 'Bearer fake-static-token')
    self.assertEqual(
        sent_json['params']['arguments'],
        {
            'project': 'projects/my-gcp-project',
            'userQuery': 'Review main.tf',
            'agentId': 'operator-prod',
            'contextId': 'ctx-000',
        },
    )
    self.assertEqual(
        sent_json['params']['_meta'],
        {'progressToken': 'corr-1'},
    )
    self.assertTrue(mock_post.call_args.kwargs['stream'])
    self.assertFalse(mock_post.call_args.kwargs['allow_redirects'])

  @mock.patch.object(requests, 'post', autospec=True)
  def test_ask_cloud_operator_streams_sse_progress_and_stops_on_result(
      self, mock_post
  ):
    sse_lines = [
        b'event: message',
        (
            b'data: {"jsonrpc":"2.0","method":"notifications/progress",'
            b'"params":{"progressToken":"corr-sse","progress":1,'
            b'"message":"**Running tool: get_project_effective_org_policies**"}}'
        ),
        b'',
        b'event: message',
        (
            b'data: {"jsonrpc":"2.0","id":"corr-sse","result":'
            b'{"structuredContent":{"content":"SSE review done.",'
            b'"context_id":"ctx-sse-99"}}}'
        ),
    ]
    mock_resp = mock.MagicMock(status_code=200, text='')
    mock_resp.iter_lines.return_value = iter(sse_lines)
    mock_post.return_value = mock_resp

    ans = mcp_client.ask_cloud_operator(
        tokens=auth.StaticTokenSource('fake-static-token'),
        mcp_url=mcp_client.DEFAULT_PROD_MCP_URL,
        project_id='my-gcp-project',
        agent_id='operator-prod',
        user_query='Review main.tf',
        correlation_id='corr-sse',
    )
    self.assertEqual(ans.content, 'SSE review done.')
    self.assertEqual(ans.context_id, 'ctx-sse-99')
    mock_resp.close.assert_called_once()

  @mock.patch.object(requests, 'post', autospec=True)
  def test_ask_cloud_operator_raises_on_incomplete_sse_stream(self, mock_post):
    sse_lines = [
        b'event: message',
        (
            b'data: {"jsonrpc":"2.0","method":"notifications/progress",'
            b'"params":{"progressToken":"corr-sse","progress":1,'
            b'"message":"Still working..."}}'
        ),
    ]
    mock_resp = mock.MagicMock(status_code=200, text='')
    mock_resp.iter_lines.return_value = iter(sse_lines)
    mock_post.return_value = mock_resp

    with self.assertRaises(mcp_client.McpTransportError) as ctx:
      mcp_client.ask_cloud_operator(
          tokens=auth.StaticTokenSource('fake-static-token'),
          mcp_url=mcp_client.DEFAULT_PROD_MCP_URL,
          project_id='my-gcp-project',
          agent_id='operator-prod',
          user_query='Review main.tf',
      )
    self.assertIn('terminal JSON-RPC response', str(ctx.exception))
    mock_resp.close.assert_called_once()

  @mock.patch.object(requests, 'post', autospec=True)
  def test_ask_cloud_operator_omits_agent_id_when_empty(self, mock_post):
    rpc_response = {
        'jsonrpc': '2.0',
        'id': 'corr-2',
        'result': {
            'structuredContent': {
                'content': 'Personal agent review complete.',
            }
        },
    }
    mock_post.return_value = mock.MagicMock(
        status_code=200, text=json.dumps(rpc_response)
    )

    mcp_client.ask_cloud_operator(
        tokens=auth.StaticTokenSource('fake-static-token'),
        mcp_url=mcp_client.DEFAULT_PROD_MCP_URL,
        project_id='my-gcp-project',
        agent_id='',
        user_query='Review main.tf',
    )
    sent_args = mock_post.call_args.kwargs['json']['params']['arguments']
    self.assertNotIn('agentId', sent_args)

  def test_ask_cloud_operator_rejects_non_https_or_untrusted_url(self):
    tokens = auth.StaticTokenSource('fake-static-token')
    for bad_url in (
        'http://geminicloudassist.googleapis.com/mcp',
        'https://evil.example.com/mcp',
        'https://geminicloudassist.googleapis.com.evil.com/mcp',
    ):
      with self.assertRaises(ValueError):
        mcp_client.ask_cloud_operator(
            tokens=tokens,
            mcp_url=bad_url,
            project_id='my-gcp-project',
            agent_id='',
            user_query='test',
        )

  @mock.patch.object(requests, 'post', autospec=True)
  def test_ask_cloud_operator_includes_http_error_detail_on_non_200(
      self, mock_post
  ):
    error_body = json.dumps({
        'error': {
            'code': 403,
            'status': 'PERMISSION_DENIED',
            'message': 'Gemini Cloud Assist API has not been used in project.',
        }
    })
    mock_resp = mock.MagicMock(status_code=403, text=error_body)
    mock_post.return_value = mock_resp

    with self.assertRaises(mcp_client.McpTransportError) as ctx:
      mcp_client.ask_cloud_operator(
          tokens=auth.StaticTokenSource('fake-static-token'),
          mcp_url=mcp_client.DEFAULT_PROD_MCP_URL,
          project_id='my-gcp-project',
          agent_id='',
          user_query='Review main.tf',
      )
    self.assertEqual(ctx.exception.status_code, 403)
    self.assertIn('HTTP 403', str(ctx.exception))
    self.assertIn('PERMISSION_DENIED', str(ctx.exception))
    self.assertIn('Gemini Cloud Assist API', str(ctx.exception))
    mock_resp.close.assert_called_once()

  def test_build_pr_review_prompt_modes_and_dynamic_fences(self):
    inline_prompt = mcp_client.build_pr_review_prompt(
        project_id='my-gcp-project',
        repo_full_name='acme/infra',
        pr_number=42,
        pr_title='Add bucket',
        changed_files={'main.tf': 'resource "google_storage_bucket" "b" {}'},
        pr_mode='inline_comments',
    )
    self.assertIn(
        'IaC Review: Review Terraform against Google Best Practices',
        inline_prompt,
    )
    self.assertNotIn('docs/AGENTS.md', inline_prompt)
    self.assertIn('cloud-operator-inline-comments', inline_prompt)
    self.assertIn(
        '1: resource "google_storage_bucket" "b" {}', inline_prompt
    )

    companion_prompt = mcp_client.build_pr_review_prompt(
        project_id='my-gcp-project',
        repo_full_name='acme/infra',
        pr_number=42,
        pr_title='Add bucket',
        changed_files={
            'README.md': 'Example:\n```hcl\nresource "null_resource" "x" {}\n```'
        },
        pr_mode='companion_pr',
    )
    self.assertNotIn('cloud-operator-inline-comments', companion_prompt)
    self.assertNotIn('1: Example:', companion_prompt)
    self.assertIn('````\nExample:\n```hcl', companion_prompt)

  def test_build_issue_implementation_prompt_bundles_context_and_empty_repos(
      self,
  ):
    with_files_prompt = mcp_client.build_issue_implementation_prompt(
        project_id='my-gcp-project',
        repo_full_name='acme/infra',
        issue_number=15,
        issue_title='Add Cloud Armor WAF policy to load balancer',
        issue_body='Please add a Cloud Armor security policy blocking SQLi.',
        issue_labels=['enhancement', 'security'],
        comment_body='/cloud-operator implement also rate limit to 1000 rpm',
        repo_files={
            'main.tf': 'resource "google_compute_backend_service" "web" {}',
            'README.md': 'Docs:\n```hcl\nmodule "lb" {}\n```',
        },
    )
    self.assertIn('GitHub Issue #15 in repository `acme/infra`', with_files_prompt)
    self.assertIn('target Google Cloud project: `my-gcp-project`', with_files_prompt)
    self.assertIn(
        '- **Title**: Add Cloud Armor WAF policy to load balancer',
        with_files_prompt,
    )
    self.assertIn('- **Labels**: enhancement, security', with_files_prompt)
    self.assertIn(
        'Please add a Cloud Armor security policy blocking SQLi.',
        with_files_prompt,
    )
    self.assertIn('### Follow-Up Issue Comment', with_files_prompt)
    self.assertIn('rate limit to 1000 rpm', with_files_prompt)
    self.assertIn('title="<relative/path/to/file>"', with_files_prompt)
    self.assertNotIn('1: resource', with_files_prompt)
    self.assertIn('````\nDocs:\n```hcl', with_files_prompt)

    empty_repo_prompt = mcp_client.build_issue_implementation_prompt(
        project_id='my-gcp-project',
        repo_full_name='acme/greenfield',
        issue_number=1,
        issue_title='Provision private GKE Autopilot cluster',
        issue_body='',
        repo_files={},
    )
    self.assertIn('- **Labels**: None', empty_repo_prompt)
    self.assertIn('_(No description provided.)_', empty_repo_prompt)
    self.assertNotIn('### Follow-Up Issue Comment', empty_repo_prompt)
    self.assertIn(
        '_(No existing IaC files found in repository; generate new files as '
        'needed.)_',
        empty_repo_prompt,
    )


if __name__ == '__main__':
  absltest.main()
