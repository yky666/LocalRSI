"""Deterministic MCP subprocess for integration tests; no external dependencies."""
import json, sys, time
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
initialized = False
for line in sys.stdin:
    req = json.loads(line)
    method = req['method']
    if method == 'notifications/initialized':
        initialized = True
        continue
    if 'id' not in req: continue
    if method == 'initialize':
        result = {'protocolVersion': req['params']['protocolVersion'], 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'fixture', 'version': '1'}}
    elif not initialized:
        raise RuntimeError('Missing initialized notification')
    elif method == 'tools/list':
        if req.get('params', {}).get('cursor') == 'second': result = {'tools': []}
        else: result = {'tools': [{'name': 'echo', 'description': 'Echo text', 'inputSchema': {'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text']}}], 'nextCursor': 'second'}
    elif method == 'tools/call':
        text = req['params']['arguments']['text']
        if text == 'timeout': time.sleep(5)
        result = {'content': [{'type': 'text', 'text': text}], 'isError': False}
    else: result = {}
    print(json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'result': result}), flush=True)
