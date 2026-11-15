"""Opt-in MCP stdio client (2025-11-25 / 2025-06-18 / 2024-11-05).

Server commands are trusted local configuration, never model supplied.
All tool calls pass through the application's approval gate.
"""
import atexit, hashlib, json, os, queue, subprocess, sys, threading, time
import features

class Session:
    def __init__(self, spec):
        command = spec.get('command')
        args = spec.get('args', [])
        if not isinstance(command, str) or not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ValueError('MCP requires a command and argument array')
        if command == '{python}': command = sys.executable
        self.lock = threading.Lock()
        self.serial = 0
        self.responses = queue.Queue(maxsize=128)
        self.timeout = max(1, min(120, float(spec.get('timeout', 30))))
        self.process = subprocess.Popen([command] + args, cwd=features.ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding='utf-8', bufsize=1,
            creationflags=0x08000000 if os.name == 'nt' else 0)
        threading.Thread(target=self._read, daemon=True).start()
        try:
            result = self.request('initialize', {'protocolVersion': '2025-11-25',
                'capabilities': {}, 'clientInfo': {'name': 'LocalRSI', 'version': '0.3.0'}})
            if result.get('protocolVersion') not in ('2025-11-25', '2025-06-18', '2025-03-26', '2024-11-05'):
                raise ValueError('Unsupported MCP protocol version')
            if 'tools' not in result.get('capabilities', {}):
                raise ValueError('MCP server does not advertise tools')
            self._send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(1048577)
                if not line:
                    raise EOFError('MCP server closed stdout')
                if len(line) > 1048576:
                    raise ValueError('MCP message exceeds 1MB')
                self.responses.put(json.loads(line), timeout=1)
        except Exception as exc:
            try: self.responses.put(exc, timeout=1)
            except queue.Full: pass

    def _send(self, message):
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + '\n')
        self.process.stdin.flush()

    def request(self, method, params):
        with self.lock:
            self.serial += 1
            serial = self.serial
            self._send({'jsonrpc': '2.0', 'id': serial, 'method': method, 'params': params})
            deadline = time.monotonic() + self.timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise TimeoutError('MCP request timed out')
                try: message = self.responses.get(timeout=remaining)
                except queue.Empty: raise TimeoutError('MCP request timed out') from None
                if isinstance(message, Exception): raise message
                if 'method' in message:
                    if 'id' in message:
                        response = {'jsonrpc': '2.0', 'id': message['id']}
                        if message['method'] == 'ping': response['result'] = {}
                        else: response['error'] = {'code': -32601, 'message': 'Capability not supported'}
                        self._send(response)
                    continue
                if message.get('id') != serial: continue
                if 'error' in message: raise RuntimeError('MCP error: ' + str(message['error']))
                return message['result']

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.close()
                self.process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                self.process.terminate()
                try: self.process.wait(timeout=2)
                except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()
        for stream in (self.process.stdin, self.process.stdout):
            if stream and not stream.closed: stream.close()

_sessions = {}
_registry = {}
_lock = threading.RLock()

def configured():
    return features.config().get('mcp_servers', {})

def _session(server):
    spec = configured().get(server)
    if not spec: raise ValueError('MCP server not configured: ' + server)
    fingerprint = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
    old = _sessions.get(server)
    if old and (old[0] != fingerprint or old[1].process.poll() is not None):
        old[1].close(); del _sessions[server]; old = None
    if not old: _sessions[server] = (fingerprint, Session(spec))
    return _sessions[server]

def schemas(servers):
    result = []
    with _lock:
        for server in servers:
            fingerprint, session = _session(server)
            cursor = None
            for _ in range(10):
                page = session.request('tools/list', {'cursor': cursor} if cursor else {})
                for t in page.get('tools', []):
                    identity = server + ':' + t['name']
                    name = 'mcp_' + hashlib.sha256(identity.encode()).hexdigest()[:24]
                    _registry[name] = (server, t['name'], fingerprint)
                    result.append({'type': 'function', 'function': {'name': name,
                        'description': (identity + ': ' + t.get('description', ''))[:1000],
                        'parameters': t['inputSchema']}})
                    if len(result) > 64: raise ValueError('Select fewer MCP tools/servers (maximum 64)')
                cursor = page.get('nextCursor')
                if not cursor: break
            else: raise ValueError('MCP tool pagination exceeds limit')
    return result

def preview(name, arguments):
    server, tool, fingerprint = _registry[name]
    return {'server': server, 'tool': tool, 'arguments': arguments, 'config_fingerprint': fingerprint}

def call(name, arguments):
    with _lock:
        server, tool, expected = _registry[name]
        current = hashlib.sha256(json.dumps(configured().get(server), sort_keys=True).encode()).hexdigest()
        if current != expected: raise ValueError('MCP config changed; start a new task for approval')
        _, session = _session(server)
        try: return session.request('tools/call', {'name': tool, 'arguments': arguments})
        except Exception:
            session.close(); _sessions.pop(server, None)
            raise

def close_all():
    for _, session in list(_sessions.values()): session.close()
    _sessions.clear()

atexit.register(close_all)
