"""Demonstrate source repair with scripted replies and the unchanged snapshot."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import run_agent
from experiments.baseline_agent import run_agent as run_baseline
from status_tools import StatusTools


def call(call_id, name, arguments):
    raw = json.dumps(arguments, ensure_ascii=False)
    return {'message': {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': call_id, 'type': 'function', 'function': {'name': name, 'arguments': raw}}]},
        'calls': [{'id': call_id, 'name': name, 'arguments': raw}],
        'finish': 'tool_calls', 'usage': {}}


class DemoProvider:
    """A test double, not an LLM and not a substitute for the 22-case eval."""
    def __init__(self):
        self.calls = 0
        self.details = None

    def complete(self, messages, schemas):
        self.calls += 1
        if self.calls == 1:
            return call('status', 'get_status', {'provider': 'cloudflare', 'component': 'Cache Purge'})
        if self.calls == 2:
            status = json.loads(messages[-1]['content'])
            return call('details', 'get_incident_details',
                        {'provider': status['provider'], 'incident_id': status['incidents'][0]['id']})
        if self.calls == 3:
            self.details = json.loads(messages[-1]['content'])
        details = self.details
        answer = (f'Theo snapshot {details["captured_at"]}, incident "{details["name"]}" '
                  f'có trạng thái {details["status"]}. Đây là bằng chứng snapshot, '
                  'chưa xác nhận tình trạng thực tế hay nguyên nhân lỗi của người dùng.')
        if self.calls > 3:
            answer += ' Nguồn: ' + details['url']
        return {'message': {'role': 'assistant', 'content': answer},
                'calls': [], 'finish': 'stop', 'usage': {}}


def main():
    report = {'kind': 'offline_scripted_demo', 'uses_real_llm': False,
              'note': 'Cố ý mô phỏng final thiếu URL để kiểm tra validator; không có điểm LLM judge.'}
    for variant, runner in [('before', run_baseline), ('after', run_agent)]:
        provider = DemoProvider()
        report[variant] = runner('Kiểm tra Cache Purge và dẫn nguồn.', provider, StatusTools(), max_steps=5)
        print(f'{variant}: {report[variant]["status"]}; scripted calls: {provider.calls}')
    output = ROOT / 'artifacts' / 'offline_demo.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Trace: {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
