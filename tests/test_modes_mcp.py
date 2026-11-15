import json, pathlib, sys, tempfile, unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import app, features, mcp_bridge, modes

def response(content='ok', calls=None, finish='stop'):
    return {'choices':[{'message':{'role':'assistant','content':content,**({'tool_calls':calls} if calls else {})},'finish_reason':finish}]}

class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.data=patch.object(app,'DATA',pathlib.Path(self.tmp.name));self.data.start()
        self.t={'id':'test','status':'queued','events':[],'messages':[{'role':'system','content':'test'},{'role':'user','content':'hello'}],'rounds':0,'groups':[],'provider':'remote','thinking':'standard','agent_mode':'agent','answer':''}
    def tearDown(self):self.data.stop();self.tmp.cleanup()
    def test_deep_has_separate_review(self):
        self.t['thinking']='deep'
        with patch('providers.chat',side_effect=[response('draft'),response('verified')]) as call:
            app.run(self.t)
        self.assertEqual(call.call_count,2);self.assertEqual(self.t['answer'],'verified');self.assertEqual(self.t['status'],'done')
    def test_plan_cannot_execute_tools(self):
        self.t['agent_mode']='plan';self.t['groups']=['coding']
        with patch('providers.chat',return_value=response()) as call:app.run(self.t)
        self.assertEqual(call.call_args.args[1],[])
    def test_chat_does_not_launch_mcp(self):
        self.t.update(agent_mode='chat',mcp_servers=['fixture'])
        with patch('mcp_bridge.schemas') as discover,patch('providers.chat',return_value=response()):app.run(self.t)
        discover.assert_not_called()
    def test_approval_bound_to_mcp_config(self):
        self.t['pending']={'name':'mcp_test','arguments':{},'preview':{'config_fingerprint':'old'},'call_id':'x'}
        with patch('mcp_bridge.preview',return_value={'config_fingerprint':'new'}),patch('mcp_bridge.call') as execute,patch('providers.chat',return_value=response()):app.run(self.t,True)
        execute.assert_not_called()
        result=next(m['content'] for m in self.t['messages'] if m['role']=='tool')
        self.assertIn('changed since approval',result)
    def test_limit_is_not_completion(self):
        self.t['round_limit']=0
        with patch('providers.chat') as call:app.run(self.t)
        call.assert_not_called();self.assertEqual(self.t['status'],'budget_exhausted')
    def test_truncated_output_is_not_completion(self):
        with patch('providers.chat',return_value=response('partial',finish='length')):app.run(self.t)
        self.assertEqual(self.t['status'],'budget_exhausted')
    def test_resume_preserves_goal(self):
        self.t.update(status='budget_exhausted',rounds=12,goal=True,objective='original')
        with patch.dict(app.TASKS,{'test':self.t}),patch('threading.Thread'):
            app.resume_task('test')
        self.assertEqual(self.t['round_limit'],24);self.assertEqual(self.t['objective'],'original')
    def test_unknown_action_not_replayed(self):
        self.t['status']='interrupted';self.t['messages'].append({'role':'assistant','tool_calls':[{'id':'x'}]})
        with patch.dict(app.TASKS,{'test':self.t}),self.assertRaises(ValueError):app.resume_task('test')
    def test_goal_needs_plan_evidence(self):
        with self.assertRaises(ValueError):app.update_plan(self.t,{'steps':[{'step':'test','status':'completed','evidence':''}]})
        self.t.update(goal=True,round_limit=1)
        with patch('providers.chat',return_value=response('done')):app.run(self.t)
        self.assertEqual(self.t['status'],'budget_exhausted')
    def test_mcp_requires_approval(self):
        schema={'type':'function','function':{'name':'mcp_test','parameters':{'type':'object'}}}
        calls=[{'id':'x','type':'function','function':{'name':'mcp_test','arguments':'{}'}}]
        with patch('mcp_bridge.schemas',return_value=[schema]),patch('mcp_bridge.preview',return_value={'tool':'test'}),patch('mcp_bridge.call') as execute,patch('providers.chat',return_value=response(calls=calls)):
            app.run(self.t)
        execute.assert_not_called();self.assertEqual(self.t['status'],'approval')

class MCPTests(unittest.TestCase):
    def setUp(self):
        self.spec={'fixture':{'command':sys.executable,'args':[str(pathlib.Path(__file__).with_name('mcp_fixture.py'))],'timeout':1}}
        self.config=patch('mcp_bridge.configured',return_value=self.spec);self.config.start()
    def tearDown(self):mcp_bridge.close_all();self.config.stop()
    def test_initialize_paginate_call(self):
        schemas=mcp_bridge.schemas(['fixture']);self.assertEqual(len(schemas),1)
        result=mcp_bridge.call(schemas[0]['function']['name'],{'text':'你好'})
        self.assertEqual(result['content'][0]['text'],'你好')
    def test_changed_config_cannot_execute(self):
        name=mcp_bridge.schemas(['fixture'])[0]['function']['name']
        self.spec['fixture']['timeout']=2
        with self.assertRaises(ValueError):mcp_bridge.call(name,{'text':'blocked'})
    def test_timeout_cleans_session(self):
        name=mcp_bridge.schemas(['fixture'])[0]['function']['name']
        with self.assertRaises(TimeoutError):mcp_bridge.call(name,{'text':'timeout'})
        self.assertNotIn('fixture',mcp_bridge._sessions)

if __name__=='__main__':unittest.main()
