import pathlib,sys,tempfile,unittest,os,json
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import app,features,mcp_bridge,skill_library

class ConversationTests(unittest.TestCase):
    def test_restart_restores_without_replaying(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(app,'DATA',pathlib.Path(directory)),patch.dict(app.TASKS,{},clear=True),patch('threading.Thread') as launch:
            original={'id':'restart','status':'running','dialogue':[{'role':'user','content':'goal'}],'messages':[{'role':'assistant','tool_calls':[{'id':'unknown'}]}]}
            app.persist(original);app.restore_tasks()
            self.assertEqual(app.TASKS['restart']['status'],'interrupted');launch.assert_not_called()
            with self.assertRaises(ValueError):app.resume_task('restart')
    def test_followup_keeps_dialogue_and_parent_unchanged(self):
        parent={'id':'parent','status':'done','messages':[{'role':'system','content':'s'},{'role':'user','content':'one'},{'role':'assistant','content':'two'}],'dialogue':[{'role':'user','content':'one'},{'role':'assistant','content':'two'}]}
        with tempfile.TemporaryDirectory() as directory,patch.object(app,'DATA',pathlib.Path(directory)),patch.dict(app.TASKS,{'parent':parent},clear=True),patch('threading.Thread'),patch('evolution.active',return_value=''),patch('providers.provider'):
            task=app.TASKS[app.start_task({'prompt':'follow up','parent':'parent'})['id']]
            self.assertEqual(task['conversation_id'],'parent');self.assertEqual(len(task['dialogue']),3)
            self.assertEqual(len(parent['dialogue']),2)
            parent['status']='running'
            with self.assertRaises(ValueError):app.start_task({'prompt':'follow up','parent':'parent'})
    def test_skill_routing_and_manual_selection(self):
        self.assertEqual([s['id'] for s in skill_library.route('分析论文并设计消融实验',[])],['paper-review','experiment-design'])
        self.assertEqual([s['id'] for s in skill_library.route('分析论文',['code-change'])],['code-change'])
    def test_bundled_mcp_uses_member_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            base=pathlib.Path(directory);one=base/'one';two=base/'two';one.mkdir();two.mkdir();(one/'private.txt').write_text('member one')
            try:
                with patch.dict(os.environ,{'LOCALRSI_HOSTED':'1'}),patch.object(features,'WORK',one):
                    schema=mcp_bridge.schemas(['workspace']);read=next(s['function']['name'] for s in schema if 'read_text' in s['function']['description'])
                    self.assertIn('member one',json.dumps(mcp_bridge.call(read,{'path':'private.txt'})))
                mcp_bridge.close_all()
                with patch.dict(os.environ,{'LOCALRSI_HOSTED':'1'}),patch.object(features,'WORK',two):
                    mcp_bridge.schemas(['workspace'])
                    self.assertTrue(mcp_bridge.call(read,{'path':'private.txt'})['isError'])
                    self.assertTrue(mcp_bridge.call(read,{'path':'../one/private.txt'})['isError'])
            finally:mcp_bridge.close_all()
