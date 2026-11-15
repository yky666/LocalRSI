import json,os,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import sandbox

@unittest.skipUnless(sandbox.available(),'WASI runtime must be installed for integration checks')
class SandboxTests(unittest.TestCase):
    def test_calculation_and_explicit_readonly_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'data.csv';path.write_text('x\n1\n2\n')
            result=sandbox.run("import csv; print(sum(int(r['x']) for r in csv.DictReader(open('/inputs/input'))))",path)
            self.assertEqual(result['exit_code'],0);self.assertEqual(result['stdout'].strip(),'3')
            result=sandbox.run("open('/inputs/input','w').write('modified')",path)
            self.assertNotEqual(result['exit_code'],0);self.assertEqual(path.read_text(),'x\n1\n2\n')
    def test_host_files_environment_and_processes_unavailable(self):
        os.environ['LOCALRSI_TEST_SECRET']='do-not-inherit'
        try:
            code="""import os,json
results={'secret':os.environ.get('LOCALRSI_TEST_SECRET')}
for name,action in [('host',lambda:open('C:/Windows/win.ini').read()),('traversal',lambda:open('/usr/local/../../Windows/win.ini').read())]:
 try:action();results[name]='ALLOWED'
 except Exception:results[name]='blocked'
print(json.dumps(results))"""
            result=sandbox.run(code);self.assertEqual(result['exit_code'],0)
            self.assertEqual(json.loads(result['stdout']),{'secret':None,'host':'blocked','traversal':'blocked'})
            for code in ["import os; os.system('whoami'); print('completed')", "import socket; socket.create_connection(('127.0.0.1',8090),timeout=1); print('completed')"]:
                result=sandbox.run(code);self.assertNotEqual(result['exit_code'],0);self.assertNotIn('completed',result.get('stdout',''))
        finally:os.environ.pop('LOCALRSI_TEST_SECRET',None)
    def test_infinite_loop_fuel_and_memory_limits(self):
        result=sandbox.run('while True: pass')
        self.assertNotEqual(result['exit_code'],0)
        result=sandbox.run("value=bytearray(400*1024*1024)")
        self.assertNotEqual(result['exit_code'],0)
    def test_output_is_bounded(self):
        result=sandbox.run("print('x'*1000000)")
        self.assertLessEqual(len(result['stdout']),65536);self.assertTrue(result['truncated'])
