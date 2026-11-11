"""Run a matched free-model experiment and publish results only after full scoring."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', default='.env')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--request-interval', type=float, default=6.2)
    args = parser.parse_args()
    output_dir = ROOT / 'artifacts' / 'v2'
    output_dir.mkdir(parents=True, exist_ok=True)
    for variant, bonus in [('before', False), ('after', False), ('after', True)]:
        output = output_dir / ('eval_bonus.json' if bonus else f'eval_{variant}.json')
        command = [sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / 'evaluate.py'),
                   '--env-file', args.env_file, '--variant', variant, '--max-steps', '16' if bonus else '8',
                   '--workers', str(args.workers), '--request-interval', str(args.request_interval), '--output', str(output)]
        if bonus:
            command.append('--bonus')
        if args.resume and output.exists():
            command.append('--resume')
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            print('Chưa có bộ kết quả đầy đủ; giữ nguyên kết quả cũ. Sửa cấu hình/hạn mức rồi chạy lại với --resume.')
            return result.returncode
    for name in ('eval_before.json', 'eval_after.json', 'eval_bonus.json'):
        report = json.loads((output_dir / name).read_text(encoding='utf-8'))
        if report['summary']['score_0_100'] is None:
            raise RuntimeError('Không được công bố điểm khi còn case unscored.')
    sys.path.insert(0, str(ROOT))
    from scripts.compare_evals import compare
    before = json.loads((output_dir / 'eval_before.json').read_text(encoding='utf-8'))
    after = json.loads((output_dir / 'eval_after.json').read_text(encoding='utf-8'))
    comparison = compare(before, after)
    if not comparison['same_config']:
        raise RuntimeError('Hai bản eval không cùng cấu hình.')
    for name in ('eval_before.json', 'eval_after.json', 'eval_bonus.json'):
        shutil.copyfile(output_dir / name, ROOT / name)
    for destination in (output_dir / 'eval_comparison.json', ROOT / 'artifacts' / 'eval_comparison.json'):
        destination.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Đã công bố đủ ba bộ kết quả mới. Đọc trace và cập nhật báo cáo theo số liệu thực tế.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
