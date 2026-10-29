"""Unit tests for parser.py SSE decoding, error handling, and file extraction."""

import json

from absl.testing import absltest

from iac_design_review import parser


class ParserTest(absltest.TestCase):
  """Tests `ask_cloud_operator` response parsing and path sanitization."""

  def test_parse_sse_extracts_final_json_message(self):
    sse_stream = (
        'event: message\n'
        'data: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n'
        'event: message\n'
        'data: {"jsonrpc":"2.0","id":"1","result":{"content":[{"type":"text",'
        '"text":"ok"}]}}\n\n'
        'data: [DONE]\n'
    )
    decoded = json.loads(parser.parse_sse(sse_stream))
    self.assertEqual(decoded['id'], '1')

  def test_parse_sse_preserves_plain_json_containing_data_colon(self):
    plain_json = json.dumps({
        'jsonrpc': '2.0',
        'id': '1',
        'result': {
            'structuredContent': {
                'content': 'apiVersion: v1\nkind: ConfigMap\ndata:\n  k: v\n',
            }
        },
    })
    self.assertEqual(parser.parse_sse(plain_json), plain_json)

  def test_parse_sse_raises_on_incomplete_sse_stream_without_result(self):
    sse_stream = (
        'event: message\n'
        'data: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n'
    )
    with self.assertRaises(parser.McpError) as ctx:
      parser.parse_sse(sse_stream)
    self.assertEqual(ctx.exception.status, 'UNAVAILABLE')

  def test_extract_answer_structured_content(self):
    payload = {
        'jsonrpc': '2.0',
        'id': 'req-1',
        'result': {
            'structuredContent': {
                'content': 'All IaC resources look healthy.',
                'context_id': 'ctx-abc-123',
            }
        },
    }
    answer = parser.extract_answer(payload)
    self.assertEqual(answer.content, 'All IaC resources look healthy.')
    self.assertEqual(answer.context_id, 'ctx-abc-123')

  def test_extract_answer_raises_on_failed_task_state(self):
    for bad_state in ('FAILED', 'CANCELLED', 'REJECTED'):
      payload = {
          'jsonrpc': '2.0',
          'id': 'req-state',
          'result': {
              'structuredContent': {
                  'task_state': bad_state,
                  'content': f'Task ended with {bad_state}.',
              }
          },
      }
      with self.assertRaises(parser.McpError) as ctx:
        parser.extract_answer(payload)
      self.assertEqual(ctx.exception.status, f'TASK_{bad_state}')

  def test_extract_answer_deduplicates_duplicate_and_cumulative_chunks(self):
    payload = {
        'jsonrpc': '2.0',
        'id': 'req-dedup',
        'result': {
            'content': [
                {'type': 'text', 'text': 'Review finding 1.'},
                {
                    'type': 'text',
                    'text': json.dumps({
                        'structuredContent': {
                            'content': 'Review finding 1.',
                            'context_id': 'ctx-dedup',
                        }
                    }),
                },
            ]
        },
    }
    answer = parser.extract_answer(payload)
    self.assertEqual(answer.content, 'Review finding 1.')
    self.assertEqual(answer.context_id, 'ctx-dedup')

  def test_raises_mcp_error_for_http_200_is_error_true(self):
    error_json = json.dumps({
        'error': {
            'code': 403,
            'status': 'PERMISSION_DENIED',
            'message': 'Caller lacks cloudaicompanion.entitlements.get.',
        }
    })
    payload = {
        'jsonrpc': '2.0',
        'id': 'req-2',
        'result': {
            'isError': True,
            'content': [{'type': 'text', 'text': error_json}],
        },
    }
    with self.assertRaises(parser.McpError) as ctx:
      parser.extract_answer(payload)
    self.assertEqual(ctx.exception.code, 403)
    self.assertEqual(ctx.exception.status, 'PERMISSION_DENIED')

  def test_raises_mcp_error_handles_non_numeric_error_code(self):
    payload = {
        'jsonrpc': '2.0',
        'id': 'req-bad-code',
        'error': {
            'code': 'INVALID_ARGUMENT',
            'status': 'INVALID_ARGUMENT',
            'message': 'Bad request.',
        },
    }
    with self.assertRaises(parser.McpError) as ctx:
      parser.extract_answer(payload)
    self.assertEqual(ctx.exception.code, 0)
    self.assertEqual(ctx.exception.status, 'INVALID_ARGUMENT')

  def test_sanitize_relative_repo_path_blocks_traversal_and_protected(self):
    self.assertEqual(
        parser.sanitize_relative_repo_path('envs/prod/main.tf'),
        'envs/prod/main.tf',
    )
    for bad_path in (
        '/etc/passwd',
        '../outside.tf',
        'envs/../../secret.tf',
        '.git/config',
        'sub/.git/config',
        '.github/workflows/autocloud.yml',
        'nested/.github/workflows/ci.yml',
        '',
    ):
      with self.assertRaises(ValueError):
        parser.sanitize_relative_repo_path(bad_path)

  def test_extract_remediated_files_fenced_and_skips_unsafe(self):
    markdown = (
        '### Findings\n'
        '1. Enable uniform bucket-level access.\n\n'
        '```hcl title="envs/prod/storage.tf"\n'
        'resource "google_storage_bucket" "b" {\n'
        '  uniform_bucket_level_access = true\n'
        '}\n'
        '```\n\n'
        '```yaml title=".github/workflows/pwn.yml"\n'
        'malicious: true\n'
        '```\n'
    )
    files = parser.extract_remediated_files(markdown)
    self.assertLen(files, 1)
    self.assertEqual(files[0].path, 'envs/prod/storage.tf')
    self.assertIn('uniform_bucket_level_access = true', files[0].content)

  def test_extract_remediated_files_supports_file_headers_and_joins_same_path(
      self,
  ):
    markdown = (
        '**File:** `main.tf`\n'
        '```hcl\n'
        'resource "google_storage_bucket" "b1" {\n'
        '  name = "b1"\n'
        '}\n'
        '```\n\n'
        '```hcl\n'
        '# File: variables.tf\n'
        'variable "project_id" {\n'
        '  type = string\n'
        '}\n'
        '```\n\n'
        '### File: `main.tf`\n'
        '```terraform\n'
        'resource "google_storage_bucket" "b2" {\n'
        '  name = "b2"\n'
        '}\n'
        '```\n'
    )
    files = parser.extract_remediated_files(markdown)
    self.assertLen(files, 2)
    self.assertEqual(files[0].path, 'main.tf')
    self.assertIn('google_storage_bucket" "b1"', files[0].content)
    self.assertIn('google_storage_bucket" "b2"', files[0].content)
    self.assertEqual(files[1].path, 'variables.tf')
    self.assertIn('variable "project_id"', files[1].content)
    self.assertNotIn('# File:', files[1].content)

  def test_extract_remediated_files_falls_back_to_main_tf_for_unlabeled_hcl(
      self,
  ):
    markdown = (
        'Here is the updated configuration:\n\n'
        '```hcl\n'
        'resource "google_storage_bucket" "b" {\n'
        '  uniform_bucket_level_access = true\n'
        '}\n'
        '```\n'
    )
    files = parser.extract_remediated_files(markdown)
    self.assertLen(files, 1)
    self.assertEqual(files[0].path, 'main.tf')
    self.assertIn('uniform_bucket_level_access = true', files[0].content)

  def test_context_id_marker_roundtrip(self):
    comment = parser.embed_context_id_marker(
        'Review complete.', 'cloud-operator-ctx-99'
    )
    self.assertIn(
        '<!-- cloud-operator-context-id: cloud-operator-ctx-99 -->', comment
    )
    extracted = parser.extract_context_id_marker(['Older comment', comment])
    self.assertEqual(extracted, 'cloud-operator-ctx-99')

  def test_extract_inline_comments_parses_json_and_suggestion(self):
    markdown = (
        '### Summary\nFound 1 issue.\n\n'
        '```json title="cloud-operator-inline-comments"\n'
        '[\n'
        '  {\n'
        '    "path": "main.tf",\n'
        '    "line": 5,\n'
        '    "body": "Enable uniform bucket-level access.",\n'
        '    "suggestion": "  uniform_bucket_level_access = true"\n'
        '  }\n'
        ']\n'
        '```\n'
    )
    comments = parser.extract_inline_comments(markdown)
    self.assertLen(comments, 1)
    self.assertEqual(comments[0].path, 'main.tf')
    self.assertEqual(comments[0].line, 5)
    self.assertIn('```suggestion', comments[0].body)
    self.assertIn('uniform_bucket_level_access = true', comments[0].body)
    stripped = parser.strip_inline_comments_json_block(markdown)
    self.assertNotIn('cloud-operator-inline-comments', stripped)

  def test_extract_inline_comments_swaps_inverted_range_and_unwraps_fences(
      self,
  ):
    markdown = (
        '```json title="cloud-operator-inline-comments"\n'
        '[\n'
        '  {\n'
        '    "path": "main.tf",\n'
        '    "start_line": 10,\n'
        '    "line": 6,\n'
        '    "body": "Fix block.",\n'
        '    "suggestion": "```hcl\\n  uniform_bucket_level_access = true\\n```"\n'
        '  },\n'
        '  {\n'
        '    "path": "main.tf",\n'
        '    "line": true,\n'
        '    "body": "Boolean line should be ignored."\n'
        '  }\n'
        ']\n'
        '```\n'
    )
    comments = parser.extract_inline_comments(markdown)
    self.assertLen(comments, 1)
    self.assertEqual(comments[0].start_line, 6)
    self.assertEqual(comments[0].line, 10)
    self.assertNotIn('```hcl', comments[0].body)
    self.assertIn(
        '```suggestion\n  uniform_bucket_level_access = true\n```',
        comments[0].body,
    )

  def test_build_inline_comments_from_remediated_files_diffs_lines(self):
    original = {
        'main.tf': (
            'resource "google_storage_bucket" "b" {\n'
            '  name = "my-bucket"\n'
            '  uniform_bucket_level_access = false\n'
            '}\n'
        )
    }
    remediated = [
        parser.RemediatedFile(
            path='main.tf',
            content=(
                'resource "google_storage_bucket" "b" {\n'
                '  name = "my-bucket"\n'
                '  uniform_bucket_level_access = true\n'
                '}\n'
            ),
        )
    ]
    inline = parser.build_inline_comments_from_remediated_files(
        original, remediated
    )
    self.assertLen(inline, 1)
    self.assertEqual(inline[0].path, 'main.tf')
    self.assertEqual(inline[0].line, 3)
    self.assertIsNone(inline[0].start_line)
    self.assertIn(
        '```suggestion\n  uniform_bucket_level_access = true\n```',
        inline[0].body,
    )

  def test_clamp_inline_comments_to_files_shifts_overshot_range(self):
    variables_tf = '\n'.join(f'line_{i}' for i in range(1, 24))
    comments = [
        parser.InlineReviewComment(
            path='variables.tf',
            start_line=21,
            line=25,
            body='Use Artifact Registry instead of gcr.io.',
        )
    ]
    clamped = parser.clamp_inline_comments_to_files(
        comments, {'variables.tf': variables_tf}
    )
    self.assertLen(clamped, 1)
    self.assertEqual(clamped[0].start_line, 19)
    self.assertEqual(clamped[0].line, 23)


if __name__ == '__main__':
  absltest.main()
