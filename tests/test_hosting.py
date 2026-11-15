import io,json,pathlib,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import app,providers

class HostingTests(unittest.TestCase):
    def test_dangerous_tools_denied_even_after_approval(self):
        with patch.object(app,'HOSTED',True):
            for tool in ('run_command','run_tests','desktop_click','browser_open','mcp_external'):
                with self.assertRaises(ValueError):app.tool(tool,{})
    def test_shared_vision_cannot_stop_common_model(self):
        with patch.object(app,'HOSTED',True),patch('features.config',return_value={'vision':{}}),patch('app.ps') as process:
            with self.assertRaises(ValueError):app.vision('data:image/png;base64,AA==')
        process.assert_not_called()
    def test_json_tools_become_validated_tool_calls(self):
        schema=[{'type':'function','function':{'name':'calculate','parameters':{'type':'object'}}}]
        config={'base_url':'http://127.0.0.1:18088/v1','model':'test','tool_protocol':'json'}
        data={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'reasoning</think>\n{"tool":"calculate","arguments":{"expression":"17*23"}}'}}]}
        with patch('providers.provider',return_value=config),patch('urllib.request.OpenerDirector.open',return_value=io.BytesIO(json.dumps(data).encode())):
            result=providers.chat([{'role':'system','content':'system'},{'role':'user','content':'calculate'}],schema)
        call=result['choices'][0]['message']['tool_calls'][0]
        self.assertEqual(call['function']['name'],'calculate')
        self.assertEqual(json.loads(call['function']['arguments']),{'expression':'17*23'})
    def test_json_adapter_rejects_unadvertised_tool(self):
        data={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'{"tool":"run_command","arguments":{}}'}}]}
        config={'base_url':'http://127.0.0.1:18088/v1','model':'test','tool_protocol':'json'}
        with patch('providers.provider',return_value=config),patch('urllib.request.OpenerDirector.open',return_value=io.BytesIO(json.dumps(data).encode())):
            with self.assertRaises(ValueError):providers.chat([{'role':'system','content':'system'}],[{'function':{'name':'calculate'}}])

if __name__=='__main__':unittest.main()
