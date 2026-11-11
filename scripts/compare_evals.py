"""Summarize original eval reports without inventing missing scores or costs."""
import argparse
import json
from pathlib import Path


def usage_totals(entries):
    tokens = 0
    costs = []
    for usage in entries:
        tokens += usage.get('total_tokens', usage.get('input_tokens', 0) + usage.get('output_tokens', 0))
        costs.append(usage.get('cost'))
    known_cost = bool(costs) and all(isinstance(c, (int, float)) for c in costs)
    return {'tokens': tokens, 'cost_usd': round(sum(costs), 8) if known_cost else None}


def metrics(report):
    cases = report['cases']
    agent_usage = [u for c in cases for u in c['result'].get('usage', [])]
    judge_usage = [c['grade'].get('judge_usage', {}) for c in cases]
    agent = usage_totals(agent_usage)
    judge = usage_totals(judge_usage)
    total_cost = agent['cost_usd'] + judge['cost_usd'] if agent['cost_usd'] is not None and judge['cost_usd'] is not None else None
    return {**report['summary'],
            'agent_model_calls': sum(len({e['step'] for e in c['result'].get('trace', [])
                                         if e['event'] in ('model', 'provider_error')}) for c in cases),
            'source_revision_events': sum(e['event'] == 'validation_missing_source'
                                         for c in cases for e in c['result'].get('trace', [])),
            'agent_usage': agent, 'judge_usage': judge,
            'total_cost_usd': round(total_cost, 8) if total_cost is not None else None,
            'mechanical_violations': {c['id']: c['grade']['mechanical']['violations'] for c in cases
                                      if c['grade'].get('mechanical', {}).get('violations')}}


def compare(before, after):
    fields = ('provider', 'model', 'judge_provider', 'judge_model', 'max_steps', 'dataset')
    differences = {k: [before['config'].get(k), after['config'].get(k)] for k in fields
                   if before['config'].get(k) != after['config'].get(k)}
    for field in ('max_tokens', 'reasoning_enabled', 'gemini_reasoning_effort', 'protected_sha256'):
        left = before.get('experiment', {}).get(field)
        right = after.get('experiment', {}).get(field)
        if left != right:
            differences[field] = [left, right]
    old = {c['id']: c for c in before['cases']}
    new = {c['id']: c for c in after['cases']}
    if set(old) != set(new):
        raise ValueError('Hai file phải chứa cùng các case.')
    left, right = metrics(before), metrics(after)
    complete = left['score_0_100'] is not None and right['score_0_100'] is not None
    rows = []
    for case_id in old:
        a, b = old[case_id]['grade']['score'], new[case_id]['grade']['score']
        rows.append({'id': case_id, 'before': a, 'after': b,
                     'delta': b - a if a is not None and b is not None else None})
    return {'same_config': not differences, 'config_differences': differences,
            'before': left, 'after': right,
            'score_delta': round(right['score_0_100'] - left['score_0_100'], 2) if complete and not differences else None,
            'cases': rows,
            'limitations': 'Một lần chạy mỗi phiên bản; judge có thể sai. Không suy ra quan hệ nhân quả từ chênh lệch điểm.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', default='eval_before.json')
    parser.add_argument('--after', default='eval_after.json')
    parser.add_argument('--output', default='artifacts/eval_comparison.json')
    args = parser.parse_args()
    before = json.loads(Path(args.before).read_text(encoding='utf-8'))
    after = json.loads(Path(args.after).read_text(encoding='utf-8'))
    report = compare(before, after)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}, ensure_ascii=False, indent=2))
    print(f'Comparison: {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
