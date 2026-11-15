import json,pathlib,sys,threading,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from mcp_http import HttpSession

class HTTPTests(unittest.TestCase):
 def test_session_json_sse_and_no_retry(self):
  calls=[];headers=[]
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_DELETE(self):calls.append('DELETE');self.send_response(204);self.end_headers()
   def do_POST(self):
    data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));method=data['method'];calls.append(method);headers.append(dict(self.headers))
    if 'id' not in data:self.send_response(202);self.end_headers();return
    result={'protocolVersion':'2025-11-25','capabilities':{'tools':{}}} if method=='initialize' else {'tools':[]}
    value={'jsonrpc':'2.0','id':data['id'],'result':result}
    if method=='tools/call':value={'jsonrpc':'2.0','id':data['id'],'error':{'code':-32000,'message':'failed'}}
    raw=json.dumps(value).encode();sse=method=='tools/list'
    if sse:raw=b'data: '+raw+b'\n\n'
    self.send_response(200);self.send_header('Content-Type','text/event-stream' if sse else 'application/json');self.send_header('Mcp-Session-Id','test-session');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   session=HttpSession({'url':f'http://127.0.0.1:{server.server_port}/mcp'})
   self.assertEqual(session.request('tools/list',{}),{'tools':[]})
   with self.assertRaises(RuntimeError):session.request('tools/call',{})
   self.assertEqual(calls.count('tools/call'),1);self.assertEqual(headers[1]['Mcp-Session-Id'],'test-session');session.close();self.assertEqual(calls[-1],'DELETE')
  finally:server.shutdown();server.server_close();thread.join()
 def test_rejects_cleartext_external_and_url_password(self):
  for url in ('http://example.com/mcp','https://user:pass@example.com/mcp'):
   with self.assertRaises(ValueError):HttpSession({'url':url})
