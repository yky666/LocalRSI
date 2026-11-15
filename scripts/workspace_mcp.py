"""Bundled read-only MCP stdio server. Scope: LocalRSI workspace only."""
import json, pathlib, sys
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
ROOT = pathlib.Path(__file__).resolve().parents[1] / 'workspace'
initialized = False
TOOLS = [
    {'name':'list_files','description':'List files in the LocalRSI workspace','inputSchema':{'type':'object','properties':{'path':{'type':'string'}},'required':['path'],'additionalProperties':False}},
    {'name':'read_text','description':'Read a UTF-8 file in the LocalRSI workspace (maximum 32KB)','inputSchema':{'type':'object','properties':{'path':{'type':'string'}},'required':['path'],'additionalProperties':False}},
]

def execute(name, arguments):
    raw = arguments['path']
    if not isinstance(raw, str): raise ValueError('Path must be a string')
    p = (ROOT / raw).resolve()
    if p != ROOT.resolve() and ROOT.resolve() not in p.parents: raise ValueError('Path escapes workspace')
    q = ROOT
    for part in pathlib.Path(raw).parts:
        q = q / part
        if q.is_symlink() or (hasattr(q, 'is_junction') and q.is_junction()): raise ValueError('Links are not allowed')
    if name == 'list_files': return [{'name': f.name, 'directory': f.is_dir()} for f in list(p.iterdir())[:100]]
    if name == 'read_text':
        if p.stat().st_size > 32768: raise ValueError('File exceeds 32KB')
        return p.read_text(encoding='utf-8')
    raise ValueError('Unknown tool')

for line in sys.stdin:
    req = json.loads(line)
    method = req.get('method')
    if method == 'notifications/initialized': initialized = True; continue
    if 'id' not in req: continue
    response = {'jsonrpc':'2.0', 'id':req['id']}
    try:
        if method == 'initialize': result = {'protocolVersion':'2025-11-25','capabilities':{'tools':{}},'serverInfo':{'name':'localrsi-workspace','version':'1.0'}}
        elif method == 'ping': result = {}
        elif not initialized: raise ValueError('Initialize first')
        elif method == 'tools/list': result = {'tools':TOOLS}
        elif method == 'tools/call':
            try:
                value = execute(req['params']['name'], req['params'].get('arguments', {}))
                result = {'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'isError':False}
            except Exception as exc: result = {'content':[{'type':'text','text':str(exc)}],'isError':True}
        else:
            response['error'] = {'code':-32601,'message':'Method not found'}
            result = None
        if 'error' not in response: response['result'] = result
    except Exception as exc: response['error'] = {'code':-32602,'message':str(exc)}
    print(json.dumps(response,ensure_ascii=False),flush=True)
