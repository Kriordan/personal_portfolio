"""Provider boundaries: fixed destinations, one call, bounded outputs and safe errors."""
import io
import json
import os
import subprocess
import unittest
from unittest.mock import Mock, patch

from project.jobwizard import extraction_worker as worker
from project.jobwizard.extraction_errors import SuggestionError
from project.services import jobwizard_extraction as service
from tests.test_jobwizard_extraction_service import SOURCE, URL


def response(value, status=200):
    result = Mock(status_code=status, headers={'Content-Type': 'application/json'})
    result.iter_content.return_value = [json.dumps(value).encode()]
    result.__enter__ = Mock(return_value=result); result.__exit__ = Mock(return_value=False)
    return result


class WorkerTests(unittest.TestCase):
    def test_source_read_uses_fixed_provider_and_rejects_private_or_unsupported_target(self):
        client = Mock(); client.__enter__ = Mock(return_value=client); client.__exit__ = Mock(return_value=False)
        client.post.return_value = response({'data': {'error': 'page_blocked'}})
        with patch.object(worker.requests, 'Session', return_value=client), patch.object(worker, 'validate_public_target'), patch.dict(os.environ, BROWSERLESS_API_TOKEN='fixture'):
            with self.assertRaises(SuggestionError) as error: worker.read_listing(URL)
            self.assertEqual(error.exception.code, 'page_blocked')
            self.assertEqual(client.post.call_count, 1)
            args, kwargs = client.post.call_args
            self.assertEqual(args[0], 'https://production-sfo.browserless.io/function')
            self.assertFalse(kwargs['allow_redirects']); self.assertFalse(client.trust_env)
            with self.assertRaises(SuggestionError): worker.read_listing('http://127.0.0.1/private')
            self.assertEqual(client.post.call_count, 1)

    def test_invalid_refused_incomplete_summary_and_usage_boundaries(self):
        client = Mock(); client.__enter__ = Mock(return_value=client); client.__exit__ = Mock(return_value=False)
        cases = [({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]}, 'refused'),
                 ({'status': 'incomplete', 'output': []}, 'invalid_summary'),
                 ({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'not json'}]}]}, 'invalid_summary')]
        with patch.object(worker.requests, 'Session', return_value=client), patch.dict(os.environ, OPENAI_API_KEY='fixture'):
            for payload, code in cases:
                client.post.return_value = response(payload)
                with self.assertRaises(SuggestionError) as error: worker.summarize(SOURCE, 'gpt-6-luna')
                self.assertEqual(error.exception.code, code)
            sent = client.post.call_args.kwargs['json']
            self.assertFalse(sent['store']); self.assertNotIn('tools', sent)
            self.assertEqual(set(json.loads(sent['input'])), {'source_blocks'})

    def test_http_errors_bounds_and_subprocess_deadlines_do_not_expose_credentials(self):
        for status, expected in [(401, 'provider_auth'), (429, 'provider_quota'), (504, 'timeout')]:
            with self.assertRaises(SuggestionError) as error: worker.read_json(response({'secret': 'TOKEN'}, status), 20)
            self.assertEqual(error.exception.code, expected)
        with self.assertRaises(SuggestionError): worker.read_json(response({'large': 'x' * 1000}), 20)
        for stage, deadline in [('read', 19), ('summary', 11)]:
            with patch.object(service.subprocess, 'run', side_effect=subprocess.TimeoutExpired('hidden', deadline)) as run:
                with self.assertRaises(SuggestionError) as error: service._run(stage, url=URL)
                self.assertEqual(error.exception.code, 'timeout'); self.assertEqual(run.call_args.kwargs['timeout'], deadline)
        with patch.object(worker.sys, 'stdin', io.StringIO(json.dumps(dict(parent_pid=123, stage='read', url=URL)))), patch.object(worker, 'guard_worker'), patch.object(worker.signal, 'alarm'), patch.object(worker, 'read_listing', side_effect=RuntimeError('SECRET')), patch.object(worker.sys, 'stdout', new_callable=io.StringIO) as output:
            self.assertEqual(worker.main(), 1); self.assertEqual(json.loads(output.getvalue()), {'error': 'failed'})
