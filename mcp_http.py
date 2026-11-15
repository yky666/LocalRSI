"""MCP Streamable HTTP (2025 session protocol), for trusted server configuration."""
import json,os,threading,urllib.request,urllib.parse,urllib.error

SUPPORTED=('2025-11-25','2025-06-18','2025-03-26')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class HttpSession:
    def __init__(self,spec):
        self.url=spec['url'];parsed=urllib.parse.urlparse(self.url)
        if parsed.username or parsed.password or parsed.fragment or parsed.scheme not in ('http','https'):raise ValueError('Invalid MCP URL')
        if parsed.scheme=='http' and parsed.hostname not in ('127.0.0.1','localhost','::1'):raise ValueError('Use HTTPS for non-loopback MCP')
        self.timeout=max(1,min(120,float(spec.get('timeout',30))));self.serial=0;self.session_id=None;self.protocol=SUPPORTED[0];self.lock=threading.Lock();self.closed=False
        self.key=os.environ.get(spec.get('api_key_env',''),'')
        self.opener=urllib.request.build_opener(NoRedirect(),*( [urllib.request.ProxyHandler({})] if parsed.hostname in ('localhost','127.0.0.1','::1') else []))
        try:
            result=self.request('initialize',{'protocolVersion':self.protocol,'capabilities':{},'clientInfo':{'name':'LocalRSI','version':'0.4'}})
            if result.get('protocolVersion') not in SUPPORTED or 'tools' not in result.get('capabilities',{}):raise ValueError('MCP server protocol/tools unsupported')
            self.protocol=result['protocolVersion'];self._send({'jsonrpc':'2.0','method':'notifications/initialized'})
        except Exception:
            self.close()
            raise

    def alive(self):return not self.closed

    def _headers(self):
        headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream','MCP-Protocol-Version':self.protocol}
        if self.session_id:headers['Mcp-Session-Id']=self.session_id
        if self.key:headers['Authorization']='Bearer '+self.key
        return headers

    def _send(self,message):
        request=urllib.request.Request(self.url,data=json.dumps(message).encode(),headers=self._headers())
        with self.opener.open(request,timeout=self.timeout) as response:
            session=response.headers.get('Mcp-Session-Id')
            if session:
                if len(session)>1024 or any(ord(c)<33 or ord(c)>126 for c in session):raise ValueError('Invalid MCP session ID')
                self.session_id=session
            if 'id' not in message:return {}
            content_type=response.headers.get('Content-Type','').split(';')[0]
            if content_type=='application/json':
                raw=response.read(1048577)
                if len(raw)>1048576:raise ValueError('MCP result exceeds 1MB')
                return self._result(json.loads(raw),message['id'])
            if content_type!='text/event-stream':raise ValueError('MCP response must be JSON or SSE')
            total=0;event=[]
            while True:
                raw=response.readline(1048577);total+=len(raw)
                if total>1048576:raise ValueError('MCP SSE exceeds 1MB')
                if not raw:raise EOFError('MCP SSE ended without result')
                line=raw.decode('utf-8').rstrip('\r\n')
                if line.startswith('data:'):event.append(line[5:].lstrip())
                elif not line and event:
                    value=json.loads('\n'.join(event));event=[]
                    if value.get('id')==message['id']:return self._result(value,message['id'])

    def _result(self,value,serial):
        if value.get('jsonrpc')!='2.0' or value.get('id')!=serial:raise ValueError('MCP response ID mismatch')
        if 'error' in value:raise RuntimeError('MCP returned an error: '+str(value['error'])[:2000])
        return value['result']

    def request(self,method,params):
        with self.lock:
            if self.closed:raise RuntimeError('MCP session closed')
            self.serial+=1
            # No automatic retry of tools/call: a dropped response may follow a completed action.
            return self._send({'jsonrpc':'2.0','id':self.serial,'method':method,'params':params})

    def close(self):
        self.closed=True
        if self.session_id:
            try:
                with self.opener.open(urllib.request.Request(self.url,method='DELETE',headers=self._headers()),timeout=2):pass
            except (OSError,urllib.error.HTTPError):pass
