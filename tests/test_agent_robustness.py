"""Regression tests for failure recovery, retry limits and source validation."""
import datetime
import email.utils
import json
import unittest
from unittest.mock import patch

from agent import run_agent
from bonus.tools import BonusTools
from status_tools import StatusTools
from test_lab import FakeProvider, final, tool_call


class LoopRobustnessTests(unittest.TestCase):
    def test_assistant_message_is_preserved_and_usage_is_accumulated(self):
        first = tool_call('a', 'get_status', '{"provider":"github"}')
        first['message']['provider_metadata'] = {'keep': True}
        first['usage'] = {'total_tokens': 10}
        last = final()
        last['usage'] = {'total_tokens': 20}
        provider = FakeProvider([first, last])
        result = run_agent('kiểm tra', provider, StatusTools())
        self.assertIs(provider.histories[1][2], first['message'])
        self.assertEqual(result['usage'], [{'total_tokens': 10}, {'total_tokens': 20}])
        self.assertEqual([t['step'] for t in result['trace'] if t['event'] == 'model'], [1, 2])

    def test_non_object_and_non_standard_json_are_observations(self):
        for raw in ('[]', 'null', '12', 'NaN', '{"provider": NaN}'):
            with self.subTest(raw=raw):
                provider = FakeProvider([tool_call('a', 'get_status', raw), final()])
                tools = StatusTools()
                with patch.object(tools, 'execute') as execute:
                    result = run_agent('kiểm tra', provider, tools)
                execute.assert_not_called()
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(json.loads(provider.histories[1][-1]['content'])['error'], 'INVALID_ARGUMENTS')

    def test_provider_exception_does_not_leak_exception_text(self):
        secret = 'dummy-secret-never-log'

        class BrokenProvider:
            def complete(self, messages, schemas):
                raise RuntimeError('Authorization: Bearer ' + secret)

        result = run_agent('kiểm tra', BrokenProvider(), StatusTools())
        self.assertEqual(result['status'], 'error')
        self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(result['trace'][0]['event'], 'provider_error')

    def test_unexpected_finish_never_executes_tools(self):
        for finish in ('length', 'content_filter', None):
            with self.subTest(finish=finish):
                reply = tool_call('a', 'get_status', '{"provider":"github"}')
                reply['finish'] = finish
                tools = StatusTools()
                with patch.object(tools, 'execute') as execute:
                    result = run_agent('kiểm tra', FakeProvider([reply]), tools)
                self.assertEqual(result['status'], 'error')
                execute.assert_not_called()

    def test_unhandled_tool_timeout_is_returned_and_other_calls_continue(self):
        first = tool_call('a', 'get_status', '{"provider":"github"}')
        other = tool_call('b', 'get_status', '{"provider":"cloudflare"}')
        first['calls'] += other['calls']
        first['message']['tool_calls'] += other['message']['tool_calls']
        provider = FakeProvider([first, final('Chỉ lấy được một nguồn.')])
        tools = StatusTools()
        with patch.object(tools, 'execute', side_effect=[TimeoutError('offline'), {'provider': 'cloudflare'}]):
            result = run_agent('kiểm tra cả hai', provider, tools)
        observations = provider.histories[1][-2:]
        self.assertEqual([m['tool_call_id'] for m in observations], ['a', 'b'])
        self.assertEqual(json.loads(observations[0]['content'])['error'], 'TimeoutError')
        self.assertEqual(result['status'], 'completed')

    def test_unknown_tool_and_invalid_provider_can_be_reported(self):
        for name, arguments in [('missing', '{}'), ('get_status', '{"provider":"invalid"}')]:
            with self.subTest(name=name):
                provider = FakeProvider([tool_call('a', name, arguments), final('Không đủ dữ liệu.')])
                result = run_agent('kiểm tra', provider, StatusTools())
                self.assertFalse(json.loads(provider.histories[1][-1]['content'])['ok'])
                self.assertEqual(result['status'], 'completed')

    def test_malformed_response_and_empty_answer_are_errors(self):
        for reply in (None, {}, {'message': None, 'calls': [], 'finish': 'stop'}, final('   ')):
            with self.subTest(reply=reply):
                self.assertEqual(run_agent('x', FakeProvider([reply]), StatusTools())['status'], 'error')

    def test_invalid_budget_never_calls_provider(self):
        for budget in (0, -1, True, 2.5):
            with self.subTest(budget=budget):
                provider = FakeProvider([])
                self.assertEqual(run_agent('x', provider, StatusTools(), budget)['status'], 'error')
                self.assertEqual(provider.histories, [])


class RetryTests(unittest.TestCase):
    def test_persistent_rate_limit_has_at_most_three_real_attempts(self):
        tools = BonusTools(scenario='rate_limit_always')
        replies = [tool_call(str(i), 'get_vercel_status', '{}') for i in range(4)]
        provider = FakeProvider(replies + [final('Không xác nhận được Vercel do 429.')])
        result = run_agent('kiểm tra', provider, tools, max_steps=6)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(tools.calls[('get_vercel_status', 'vercel')], 3)
        self.assertEqual(json.loads(provider.histories[4][-1]['content'])['error'], 'RETRY_LIMIT_REACHED')
        self.assertEqual(sum(t['event'] == 'tool_blocked' for t in result['trace']), 1)

    def test_short_retry_after_is_waited_before_retry(self):
        tools = StatusTools()
        replies = [tool_call(str(i), 'get_status', '{"provider":"github"}') for i in range(2)]
        limited = {'ok': False, 'error': 'RATE_LIMITED', 'retry_after': '1'}
        with patch.object(tools, 'execute', side_effect=[limited, {'provider': 'github'}]), \
                patch('agent.time.monotonic', return_value=100), patch('agent.time.sleep') as sleep:
            result = run_agent('kiểm tra', FakeProvider(replies + [final()]), tools)
        sleep.assert_called_once_with(1.0)
        self.assertEqual(result['status'], 'completed')

    def test_long_numeric_or_http_date_retry_after_is_deferred(self):
        future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=2)
        for delay in ('120', email.utils.format_datetime(future, usegmt=True)):
            with self.subTest(delay=delay):
                tools = StatusTools()
                limited = {'ok': False, 'error': 'RATE_LIMITED', 'retry_after': delay}
                replies = [tool_call(str(i), 'get_status', '{"provider":"github"}') for i in range(2)]
                provider = FakeProvider(replies + [final('Không xác nhận được.')])
                with patch.object(tools, 'execute', return_value=limited) as execute, patch('agent.time.sleep') as sleep:
                    result = run_agent('kiểm tra', provider, tools)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(execute.call_count, 1)
                sleep.assert_not_called()
                self.assertEqual(json.loads(provider.histories[2][-1]['content'])['error'], 'RETRY_DEFERRED')


class SourceTests(unittest.TestCase):
    def test_each_provider_needs_an_observed_incident_source(self):
        tools = StatusTools()
        gh = tools.get_incident_details('github', 'xr3myzj7ms51')['url']
        cf = tools.get_incident_details('cloudflare', 'wp49bp8bqo6c')['url']
        first = tool_call('a', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}')
        other = tool_call('b', 'get_incident_details', '{"provider":"cloudflare","incident_id":"wp49bp8bqo6c"}')
        first['calls'] += other['calls']
        first['message']['tool_calls'] += other['message']['tool_calls']
        provider = FakeProvider([first, final('Nguồn GitHub: ' + gh), final(f'Nguồn: {gh} và {cf}')])
        result = run_agent('so sánh', provider, tools)
        self.assertEqual(result['status'], 'completed')
        event = next(t for t in result['trace'] if t['event'] == 'validation_missing_source')
        self.assertEqual(event['missing_sources'], {'cloudflare': [cf]})

    def test_fabricated_url_with_valid_prefix_needs_revision(self):
        tools = StatusTools()
        url = tools.get_incident_details('github', 'xr3myzj7ms51')['url']
        first = tool_call('a', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}')
        provider = FakeProvider([first, final(url + '-fabricated'), final(f'[Nguồn]({url}).')])
        result = run_agent('x', provider, tools)
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(any(t['event'] == 'validation_missing_source' for t in result['trace']))

    def test_markdown_url_label_and_bold_url_are_valid_sources(self):
        tools = StatusTools()
        url = tools.get_incident_details('github', 'xr3myzj7ms51')['url']
        for answer in (f'[{url}]({url})', f'**{url}**', f'<{url}>', f'|{url}|'):
            with self.subTest(answer=answer):
                first = tool_call('a', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}')
                result = run_agent('x', FakeProvider([first, final(answer)]), tools, max_steps=2)
                self.assertEqual(result['status'], 'completed')
                self.assertFalse(any(t['event'] == 'validation_missing_source' for t in result['trace']))

    def test_pagination_uses_the_actual_next_offset(self):
        class TimelineProvider:
            def __init__(self):
                self.pages = []

            def complete(self, messages, schemas):
                if messages[-1]['role'] == 'user':
                    return tool_call('page-0', 'get_incident_details', json.dumps(
                        {'provider': 'vercel', 'incident_id': 'sps6n39gm4sg'}))
                page = json.loads(messages[-1]['content'])
                self.pages.append(page['offset'])
                if page['next_offset'] is not None:
                    return tool_call(f'page-{page["next_offset"]}', 'get_incident_details', json.dumps(
                        {'provider': 'vercel', 'incident_id': page['id'], 'offset': page['next_offset']}))
                return final('Đã đọc hết các trang. Nguồn: ' + page['url'])

        provider = TimelineProvider()
        result = run_agent('Đọc toàn bộ timeline', provider, BonusTools(), max_steps=6)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(provider.pages, [0, 2, 4, 6])


class ProviderBudgetTests(unittest.TestCase):
    @patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test', 'MAX_TOKENS': '2048'})
    @patch('providers.post_json')
    def test_output_budget_is_sent_to_api(self, post):
        from providers import Provider
        post.return_value = {'choices': [{'message': {'role': 'assistant', 'content': 'ok'}, 'finish_reason': 'stop'}]}
        Provider('openrouter', 'test-model').complete([{'role': 'user', 'content': 'hi'}], [])
        self.assertEqual(post.call_args.args[2]['max_tokens'], 2048)
