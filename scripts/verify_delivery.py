"""Audit final reports, protected data and credentials without calling an API."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.compare_evals import compare, metrics


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    protected = sorted([*ROOT.glob('fixtures/*.json'), *ROOT.glob('bonus/fixtures/*.json')])
    protected += [ROOT / name for name in (
        'evals/cases.json', 'bonus/cases.json', 'evals/scenarios.py', 'evals/grading.py', 'RUBRIC.md')]
    protected_hashes = {}
    for path in protected:
        name = path.relative_to(ROOT).as_posix()
        original = subprocess.check_output(['git', 'show', f'HEAD:{name}'], cwd=ROOT)
        assert original.replace(b'\r\n', b'\n') == path.read_bytes().replace(b'\r\n', b'\n'), name
        protected_hashes[name] = digest(path)

    source = sorted([*ROOT.glob('*.py'), *ROOT.glob('scripts/*.py'),
                     *ROOT.glob('experiments/*.py'), *ROOT.glob('evals/*.py'),
                     *ROOT.glob('bonus/*.py'), *ROOT.glob('tests/*.py')])
    for path in source:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path), feature_version=(3, 10))
    subprocess.run(['git', 'diff', '--check'], cwd=ROOT, check=True)
    subprocess.run(['git', 'check-ignore', '-q', '.env'], cwd=ROOT, check=True)

    secrets = []
    for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
        name, separator, value = line.removeprefix('export ').partition('=')
        if separator and name.strip().endswith('API_KEY'):
            value = value.strip().strip('\"\'')
            if value and value != 'YOUR_KEY':
                secrets.append(value.encode('utf-8'))
    candidates = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT)
    scanned = 0
    for raw in candidates.split(b'\0'):
        if not raw:
            continue
        path = ROOT / raw.decode('utf-8')
        if not path.is_file():
            continue
        content = path.read_bytes()
        assert not any(secret in content for secret in secrets), f'Credential in {path.name}'
        assert not re.search(rb'sk-or-v1-[a-f0-9]{64}', content), f'Credential pattern in {path.name}'
        assert not re.search(rb'AIza[0-9A-Za-z_-]{35}', content), f'Credential pattern in {path.name}'
        assert not re.search(rb'AQ\.[0-9A-Za-z_-]{20,}', content), f'Credential pattern in {path.name}'
        scanned += 1

    reports = {name: read_json(ROOT / f'eval_{name}.json') for name in ('before', 'after', 'bonus')}
    for name, report in reports.items():
        total = 10 if name == 'bonus' else 22
        assert len(report['cases']) == total
        assert report['summary']['scored_cases'] == total
        scores = [case['grade']['score'] for case in report['cases']]
        assert all(isinstance(score, (int, float)) for score in scores)
        assert report['summary']['score_0_100'] == round(sum(scores) / total, 2)
        assert report['experiment']['protected_sha256'] == protected_hashes
        for filename, expected in report['experiment']['implementation_sha256'].items():
            assert digest(ROOT / filename) == expected, f'{name}: source hash mismatch: {filename}'
        assert (ROOT / f'eval_{name}.json').read_bytes() == (ROOT / 'artifacts/v2' / f'eval_{name}.json').read_bytes()
    assert reports['bonus']['summary']['bonus_points_0_15'] == round(
        reports['bonus']['summary']['score_0_100'] * 0.15, 2)
    comparison = compare(reports['before'], reports['after'])
    assert comparison['same_config']
    assert comparison == read_json(ROOT / 'artifacts/eval_comparison.json')
    test_log = (ROOT / 'artifacts/test_results.txt').read_text(encoding='utf-8')
    test_counts = [int(n) for n in re.findall(r'Ran (\d+) tests? in ', test_log)]
    assert len(test_counts) == 2 and test_log.count('\nOK\n') == 2

    source_hashes = {p.relative_to(ROOT).as_posix(): digest(p) for p in source}
    report_hashes = {f'eval_{name}.json': digest(ROOT / f'eval_{name}.json') for name in reports}
    config = reports['after']['config']
    manifest = {
        'implementation': 'v2-investigation-checklist',
        'hash_normalization': 'lf',
        'git_base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'config_core': config, 'config_bonus': reports['bonus']['config'],
        'max_tokens': reports['after']['experiment']['max_tokens'],
        'gemini_reasoning_effort': reports['after']['experiment']['gemini_reasoning_effort'],
        'reasoning_enabled': reports['after']['experiment']['reasoning_enabled'],
        'protected_sha256': protected_hashes, 'delivery_source_sha256': source_hashes,
        'final_report_sha256': report_hashes,
        'metrics': {name: metrics(report) for name, report in reports.items()},
        'historical_experiments': {
            'v1': 'artifacts/v1', 'gemini31_initial': 'artifacts/v2a',
            'gemini31_before_id_binding_fix': 'artifacts/v2b',
            'gemini35_before_latest_and_scope_fixes': 'artifacts/v2c',
            'gemini31_incomplete_rerun': 'artifacts/gemini31_partial'},
        'limitations': ['One retained scored trajectory per case and implementation; same-model judge.',
                        'Usage excludes discarded failed attempts and separate probes; no Gemini cost field.',
                        'Eval score is not the main lab rubric grade.']}
    verification = {
        'verified_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'hash_normalization': 'lf',
        'implementation': 'v2-investigation-checklist', 'tests_passed': sum(test_counts),
        'test_suites': {'tests': test_counts[0], 'bonus': test_counts[1]},
        'real_llm_eval_status': 'all_scored', 'root_reports_match_current_source': True,
        'scored_cases': {name: len(report['cases']) for name, report in reports.items()},
        'same_core_config': True, 'api_key_absent_from_deliverable_files': True,
        'deliverable_files_scanned': scanned, 'env_ignored': True,
        'protected_files_unchanged': len(protected), 'python_3_10_syntax_compatible': len(source),
        'git_diff_check': 'pass', 'final_report_sha256': report_hashes}
    for case_id, filename in [('H1', 'demo_trace.json'), ('H7', 'error_demo.json')]:
        case = next(c for c in reports['after']['cases'] if c['id'] == case_id)
        write_json(ROOT / 'artifacts' / filename, {
            'kind': 'real_llm_eval_trace', 'uses_real_llm': True,
            'source': 'eval_after.json', 'config': config,
            'id': case_id, 'question': case['question'], 'result': case['result'], 'grade': case['grade']})
    write_json(ROOT / 'artifacts/experiment_manifest.json', manifest)
    write_json(ROOT / 'artifacts/verification.json', verification)
    print(json.dumps(verification, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
