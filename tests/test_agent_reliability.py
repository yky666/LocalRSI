import io,json,pathlib,sys,unittest,tempfile
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import providers,app,features

class ReliabilityTests(unittest.TestCase):
    def test_workspace_search_and_numbered_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);(root/'code.py').write_text('first\nneedle\nlast\n')
            with patch.object(app,'WORK',root):
                result=app.tool('search_files',{'path':'.','query':'needle'})
                self.assertEqual(result['matches'][0]['line'],2)
                self.assertEqual(app.tool('read_file_lines',{'path':'code.py','start':2,'end':2})['text'],'2: needle')
                with self.assertRaises(ValueError):app.tool('search_files',{'path':'..','query':'needle'})
    def test_bad_protocol_gets_one_repair_without_executing_tool(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(app,'DATA',pathlib.Path(directory)):
            task={'id':'repair','messages':[{'role':'system','content':'system'},{'role':'user','content':'hello'}],'events':[],'rounds':0,'groups':[],'provider':'remote','thinking':'standard','agent_mode':'agent'}
            response={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'fixed'}}]}
            with patch('providers.chat',side_effect=[providers.ToolProtocolError('invalid JSON'),response]),patch('app.tool') as execute:app.run(task)
            self.assertEqual(task['status'],'done');self.assertEqual(task['protocol_repairs'],1);execute.assert_not_called()
    def test_invalid_arguments_fail_before_execution(self):
        schema={'type':'object','properties':{'expression':{'type':'string'}},'required':['expression'],'additionalProperties':False}
        for args in ({},{'expression':1},{'expression':'1+2','command':'extra'}):
            with self.assertRaises(providers.ToolProtocolError):providers.validate_arguments(args,schema)
        providers.validate_arguments({'expression':'1+2'},schema)
    def test_context_keeps_goal_and_complete_tool_pairs(self):
        messages=[{'role':'system','content':'system'},{'role':'user','content':'original goal'}]
        for index in range(6):messages.extend([{'role':'assistant','content':None,'tool_calls':[{'id':str(index)}]},{'role':'tool','tool_call_id':str(index),'content':'x'*500}])
        result,removed=providers.remote_context(messages,[],budget=1000,objective='current goal')
        self.assertGreater(removed,0);self.assertIn('current goal',result[0]['content'])
        self.assertEqual(len(messages),14)
        ids={c['id'] for m in result for c in m.get('tool_calls',[])}
        self.assertTrue(all(m['tool_call_id'] in ids for m in result if m['role']=='tool'))
    def test_thinking_overrides_config_without_mutation(self):
        config={'base_url':'http://127.0.0.1:18088/v1','model':'test','native_thinking':True,'chat_template_kwargs':{'enable_thinking':False}}
        response={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'internal</think>391'}}]}
        with patch('providers.provider',return_value=config),patch('urllib.request.OpenerDirector.open',return_value=io.BytesIO(json.dumps(response).encode())) as request:
            result=providers.chat([{'role':'user','content':'question'}],thinking=True)
        body=json.loads(request.call_args.args[0].data)
        self.assertTrue(body['chat_template_kwargs']['enable_thinking'])
        self.assertFalse(config['chat_template_kwargs']['enable_thinking'])
        self.assertEqual(result['choices'][0]['message']['content'],'391')
    def test_exhausted_reasoning_is_not_shown_as_answer(self):
        config={'base_url':'http://127.0.0.1:18088/v1','model':'test','native_thinking':True}
        response={'choices':[{'finish_reason':'length','message':{'role':'assistant','content':'unfinished reasoning'}}]}
        with patch('providers.provider',return_value=config),patch('urllib.request.OpenerDirector.open',return_value=io.BytesIO(json.dumps(response).encode())):
            result=providers.chat([{'role':'user','content':'question'}],thinking=True)
        self.assertEqual(result['choices'][0]['message']['content'],'')
