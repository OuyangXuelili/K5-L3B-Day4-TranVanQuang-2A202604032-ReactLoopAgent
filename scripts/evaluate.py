"""Run the original evaluator with an explicit baseline/after variant and .env."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'evals'))


def load_env(path):
    """Load KEY=value or export KEY=value as data; never evaluate shell code."""
    for number, raw in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        name, separator, value = line.partition('=')
        name, value = name.strip(), value.strip()
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
            raise ValueError(f'Dòng {number}: cần KEY=value, không phải lệnh shell.')
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f'Dòng {number}: thiếu dấu đóng chuỗi.')
            value = value[1:-1]
        os.environ.setdefault(name, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__, add_help=False, allow_abbrev=False)
    parser.add_argument('--variant', choices=['before', 'after'], default='after')
    parser.add_argument('--env-file', help='File cấu hình tùy chọn; không được đọc tự động')
    parser.add_argument('--resume', action='store_true', help='Chỉ chạy lại case unscored, giữ mọi điểm đã chấm')
    parser.add_argument('--request-interval', type=float, default=0,
                        help='Khoảng cách tối thiểu giữa các lần bắt đầu gọi LLM, tính bằng giây')
    args, forwarded = parser.parse_known_args()
    if args.env_file:
        try:
            load_env(args.env_file)
        except (OSError, ValueError) as exc:
            print(f'Lỗi cấu hình: {exc}', file=sys.stderr)
            return 1

    import run_evals
    if args.request_interval < 0 or args.request_interval > 60:
        print('--request-interval phải từ 0 đến 60 giây.', file=sys.stderr)
        return 1
    if args.request_interval:
        request_lock = threading.Lock()
        next_request_at = 0.0

        class PacedProvider(run_evals.Provider):
            def complete(self, messages, schemas):
                nonlocal next_request_at
                with request_lock:
                    delay = max(0.0, next_request_at - time.monotonic())
                    if delay:
                        time.sleep(delay)
                    next_request_at = time.monotonic() + args.request_interval
                return super().complete(messages, schemas)

        run_evals.Provider = PacedProvider
    if args.variant == 'before':
        from experiments.baseline_agent import run_agent
        run_evals.run_agent = run_agent
    if not any(x == '--output' or x.startswith('--output=') for x in forwarded):
        filename = 'eval_bonus.json' if '--bonus' in forwarded else f'eval_{args.variant}.json'
        forwarded.extend(['--output', str(ROOT / filename)])
    output_parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    output_parser.add_argument('--output')
    output_args, _ = output_parser.parse_known_args(forwarded)
    output = Path(output_args.output)
    implementation_files = (['experiments/previous_agent.py', 'experiments/baseline_agent.py']
                            if args.variant == 'before' else ['agent.py', 'investigation.py'])
    implementation_files.append('providers.py')
    implementation_hashes = {name: hashlib.sha256((ROOT / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                             for name in implementation_files if (ROOT / name).exists()}
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    skipped = []
    rejudged = []
    archive = None
    if args.resume:
        if not output.is_file():
            print('--resume cần file kết quả đã có.', file=sys.stderr)
            return 1
        previous = json.loads(output.read_text(encoding='utf-8'))
        previous_variant = previous.get('experiment', {}).get('variant', args.variant)
        if previous_variant != args.variant:
            print('Không được resume khác variant.', file=sys.stderr)
            return 1
        if previous.get('experiment', {}).get('implementation_sha256', {}) != implementation_hashes:
            print('Không được resume kết quả từ implementation khác; cần một lượt chạy mới.', file=sys.stderr)
            return 1
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        archive = ROOT / 'artifacts' / f'{output.stem}_partial_{stamp}.json'
        archive.parent.mkdir(exist_ok=True)
        archive.write_bytes(output.read_bytes())
        cached = {c['id']: c for c in previous['cases']}
        original_run_case = run_evals.run_case

        def resume_case(case, config):
            fields = ('provider', 'model', 'judge_provider', 'judge_model', 'max_steps')
            if any(previous['config'].get(k) != getattr(config, k) for k in fields):
                raise ValueError('Không được resume khác model/provider/max_steps.')
            dataset = 'bonus' if config.bonus else 'core'
            if previous['config']['dataset'] != dataset:
                raise ValueError('Không được resume khác dataset.')
            if previous.get('experiment', {}).get('max_tokens', int(os.getenv('MAX_TOKENS', '4096'))) != int(os.getenv('MAX_TOKENS', '4096')):
                raise ValueError('Không được resume khác MAX_TOKENS.')
            if previous.get('experiment', {}).get('reasoning_enabled') != os.getenv('REASONING_ENABLED'):
                raise ValueError('Không được resume khác REASONING_ENABLED.')
            if previous.get('experiment', {}).get('gemini_reasoning_effort') != os.getenv('GEMINI_REASONING_EFFORT'):
                raise ValueError('Không được resume khác GEMINI_REASONING_EFFORT.')
            item = cached.get(case['id'])
            if item and (item['question'] != case['question'] or item['expected'] != case['expected'] or item['scenario'] != case.get('scenario', 'normal')):
                raise ValueError('Dataset đã thay đổi; cần chạy mới.')
            # Preserve low scores and max_steps=0 scores too; never cherry-pick them away.
            if item and item['grade']['score'] is not None:
                skipped.append(case['id'])
                print(f'{case["id"]}: giữ nguyên điểm đã chấm', flush=True)
                return item
            if item and item['result']['status'] == 'completed':
                # A failed judge does not require another agent trajectory.
                rejudged.append(case['id'])
                print(f'{case["id"]}: chấm lại cùng answer và trace, không chạy lại agent', flush=True)
                try:
                    judge = run_evals.Provider(config.judge_provider, config.judge_model)
                    grade = run_evals.grade_case(case, item['result'], judge)
                except Exception as exc:
                    grade = {'score': None, 'status': 'unscored', 'judge_usage': {},
                             'reason': f'Judge setup error ({type(exc).__name__}).'}
                return {**item, 'grade': grade}
            return original_run_case(case, config)

        run_evals.run_case = resume_case
    print(f'Variant: {args.variant}; source validation: {args.variant == "after"}', flush=True)
    sys.argv = [str(ROOT / 'evals' / 'run_evals.py'), *forwarded]
    exit_code = run_evals.main()
    report = json.loads(output.read_text(encoding='utf-8'))
    protected = list((ROOT / 'fixtures').glob('*.json')) + list((ROOT / 'bonus' / 'fixtures').glob('*.json'))
    protected += [ROOT / p for p in ('evals/cases.json', 'bonus/cases.json', 'evals/scenarios.py', 'evals/grading.py', 'RUBRIC.md')]
    report['experiment'] = {'variant': args.variant, 'source_validation': args.variant == 'after',
                            'hash_normalization': 'lf',
                            'max_tokens': int(os.getenv('MAX_TOKENS', '4096')), 'started_at_utc': started,
                            'request_interval_seconds': args.request_interval,
                            'reasoning_enabled': os.getenv('REASONING_ENABLED'),
                            'gemini_reasoning_effort': os.getenv('GEMINI_REASONING_EFFORT'),
                            'implementation': 'v1-baseline' if args.variant == 'before' else 'v2-investigation-checklist',
                            'implementation_sha256': implementation_hashes,
                            'preserved_scored_cases': sorted(skipped),
                            'rejudged_without_rerunning_agent': sorted(rejudged),
                            'previous_attempt': str(archive.relative_to(ROOT)).replace('\\', '/') if archive else None,
                            'protected_sha256': {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in protected}}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
