"""Experiment utilities must preserve unknown scores and treat .env as data."""
import json
import contextlib
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.compare_evals import compare, usage_totals
from scripts.evaluate import load_env, main
from scripts import run_comparison


class ExperimentScriptTests(unittest.TestCase):
    def test_failed_comparison_does_not_publish_partial_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('eval_before.json', 'eval_after.json', 'eval_bonus.json'):
                (root / name).write_text('original result', encoding='utf-8')
            with patch.object(run_comparison, 'ROOT', root), \
                    patch('sys.argv', ['run_comparison.py', '--resume']), \
                    patch.object(run_comparison.subprocess, 'run', return_value=SimpleNamespace(returncode=1)), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run_comparison.main(), 1)
            for name in ('eval_before.json', 'eval_after.json', 'eval_bonus.json'):
                self.assertEqual((root / name).read_text(encoding='utf-8'), 'original result')
    def test_resume_preserves_zero_and_only_rejudges_a_completed_answer(self):
        import run_evals
        config = {'provider': 'openrouter', 'model': 'test', 'judge_provider': 'openrouter',
                  'judge_model': 'test', 'max_steps': 8, 'dataset': 'core'}
        zero = {'id': 'zero', 'question': 'q', 'expected': 'e', 'scenario': 'normal',
                'result': {'status': 'max_steps', 'answer': '', 'trace': []},
                'grade': {'score': 0, 'status': 'scored'}}
        pending = {'id': 'pending', 'question': 'q', 'expected': 'e', 'scenario': 'normal',
                   'result': {'status': 'completed', 'answer': 'original answer', 'trace': []},
                   'grade': {'score': None, 'status': 'unscored'}}
        with tempfile.TemporaryDirectory() as directory:
            for name in ('evals/cases.json', 'bonus/cases.json', 'evals/scenarios.py', 'evals/grading.py', 'RUBRIC.md'):
                fixture = Path(directory) / name
                fixture.parent.mkdir(parents=True, exist_ok=True)
                fixture.write_text('test', encoding='utf-8')
            output = Path(directory) / 'report.json'
            output.write_text(json.dumps({'config': config, 'cases': [zero, pending],
                                         'experiment': {'variant': 'after', 'max_tokens': 4096}}), encoding='utf-8')

            def fake_main():
                args = SimpleNamespace(**{k: v for k, v in config.items() if k != 'dataset'}, bonus=False)
                cases = [run_evals.run_case(item, args) for item in (zero, pending)]
                output.write_text(json.dumps({'config': config, 'cases': cases}), encoding='utf-8')
                return 0

            with patch.dict(os.environ, {'MAX_TOKENS': '4096'}), \
                    patch('scripts.evaluate.ROOT', Path(directory)), \
                    patch('sys.argv', ['evaluate.py', '--resume', '--output', str(output)]), \
                    patch.object(run_evals, 'run_case') as execute_agent, \
                    patch.object(run_evals, 'main', side_effect=fake_main), \
                    patch.object(run_evals, 'Provider'), \
                    patch.object(run_evals, 'grade_case', return_value={'score': 75, 'status': 'scored'}) as judge, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
                execute_agent.assert_not_called()
                judge.assert_called_once()
                self.assertEqual(judge.call_args.args[1]['answer'], 'original answer')
            report = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual([c['grade']['score'] for c in report['cases']], [0, 75])
            self.assertEqual(report['experiment']['preserved_scored_cases'], ['zero'])
            self.assertEqual(report['experiment']['rejudged_without_rerunning_agent'], ['pending'])
    def test_env_is_data_and_shell_environment_has_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('export MODEL="file-model"\nPROVIDER=openrouter\nLITERAL=$(not-a-command)\n', encoding='utf-8')
            with patch.dict(os.environ, {'MODEL': 'shell-model'}, clear=True):
                load_env(path)
                self.assertEqual(os.environ['MODEL'], 'shell-model')
                self.assertEqual(os.environ['PROVIDER'], 'openrouter')
                self.assertEqual(os.environ['LITERAL'], '$(not-a-command)')

    def test_unknown_cost_and_unscored_result_are_not_fabricated(self):
        self.assertIsNone(usage_totals([{'total_tokens': 10}])['cost_usd'])
        base = {'config': {'model': 'same-model'}, 'experiment': {'max_tokens': 4096},
                'summary': {'score_0_100': None},
                'cases': [{'id': 'X', 'result': {'trace': [], 'usage': []},
                           'grade': {'score': None}}]}
        report = compare(base, json.loads(json.dumps(base)))
        self.assertIsNone(report['score_delta'])
        self.assertIsNone(report['cases'][0]['delta'])
        changed = json.loads(json.dumps(base))
        changed['experiment']['max_tokens'] = 2048
        self.assertFalse(compare(base, changed)['same_config'])
