import json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import research_runner as runner

class ResearchTests(unittest.TestCase):
    def test_budget_and_measured_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);(root/'eval.json').write_text('[1,2]')
            plan={'question':'Harness test, not model improvement','metric':'loss','direction':'min','evaluation_file':'eval.json','budget_seconds':10,'trial_seconds':3,'gpu_uuids':[],
                  'trials':[{'id':name,'command':[sys.executable,'-c',f'print({{"loss":{loss}}})'.replace("'loss'",'"loss"')]} for name,loss in [('baseline',2),('candidate',1)]]}
            # Emit strict JSON, independently of Python's dict rendering.
            for trial,loss in zip(plan['trials'],[2,1]):trial['command']=[sys.executable,'-c','import json; print(json.dumps({"loss":'+str(loss)+'}))']
            report=json.loads((pathlib.Path(runner.run(plan,root,root/'runs'))/'report.json').read_text())
            self.assertEqual(report['improved_candidates'],['candidate']);self.assertFalse(report['deployed'])
    def test_busy_gpu_deferred(self):
        with patch.object(runner.subprocess,'check_output',side_effect=['GPU-test\n','GPU-test\n']):
            with self.assertRaises(RuntimeError):runner.ensure_idle(['GPU-test'])
    def test_reject_unbounded_plan(self):
        with self.assertRaises(ValueError):runner.validate({'question':'x'})
