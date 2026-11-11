"""Offline replay of premature-final failures; this does not measure LLM quality."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import run_agent
from bonus.tools import BonusTools
from status_tools import StatusTools


class ChecklistProvider:
    """A fake model deliberately stops early, then follows the evidence checklist."""
    def __init__(self):
        self.count = 0

    def complete(self, messages, schemas):
        self.count += 1
        pending = []
        tail = messages[0]['content'].rsplit('\n', 1)[-1]
        if tail.startswith('['):
            pending = json.loads(tail)
        if pending and self.count > 1:
            calls = [{'id': f'{self.count}-{i}', 'name': task['name'],
                      'arguments': json.dumps(task['arguments'])} for i, task in enumerate(pending)]
            message = {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': call['id'], 'type': 'function', 'function': {
                    'name': call['name'], 'arguments': call['arguments']}} for call in calls]}
            return {'message': message, 'calls': calls, 'finish': 'tool_calls', 'usage': {}}
        sources = set()
        for message in messages:
            if message['role'] == 'tool':
                observation = json.loads(message['content'])
                for key in ('source', 'url'):
                    if observation.get(key):
                        sources.add(observation[key])
        answer = 'Demo scripted: đã hoàn tất các lượt tra cứu yêu cầu. ' + ' '.join(sorted(sources))
        return {'message': {'role': 'assistant', 'content': answer},
                'calls': [], 'finish': 'stop', 'usage': {}}


def main():
    records = []
    for dataset, selected in [('evals/cases.json', {'E2', 'H1', 'H2', 'H3', 'H6'}), ('bonus/cases.json', {'B6'})]:
        for case in json.loads((ROOT / dataset).read_text(encoding='utf-8')):
            if case['id'] not in selected:
                continue
            # Only the question is supplied. expected, grades and tool requirements
            # from the dataset are never passed to the agent or scripted provider.
            tools = BonusTools(scenario='noisy') if dataset.startswith('bonus') else StatusTools()
            result = run_agent(case['question'], ChecklistProvider(), tools, max_steps=8)
            if result['status'] != 'completed':
                raise RuntimeError(f'Offline checklist replay did not finish: {case["id"]}')
            assert any(e['event'] == 'validation_incomplete_investigation' for e in result['trace'])
            records.append({'id': case['id'], 'question': case['question'], 'result': result})
            print(case['id'], result['status'], [e['name'] for e in result['trace'] if e['event'] == 'tool'])
    report = {'kind': 'offline_scripted_evidence_replay', 'uses_real_llm': False, 'score': None,
              'note': 'Kiểm tra cơ chế bắt thiếu tool, không thay thế eval LLM thật.', 'cases': records}
    output = ROOT / 'artifacts' / 'v2' / 'offline_investigation.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
