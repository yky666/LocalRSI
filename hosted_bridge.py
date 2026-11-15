"""Outbound HTTPS relay. One restricted backend process and data root per member.

Credentials come only from environment; no inbound public port is opened.
"""
import atexit, hashlib, json, os, pathlib, socket, subprocess, sys, threading, time, urllib.request, urllib.error

ROOT=pathlib.Path(__file__).resolve().parent
SITE=os.environ.get('LOCALRSI_SITE','').rstrip('/')
KEY=os.environ.get('LOCALRSI_BRIDGE_KEY','')
SITE_KEY=os.environ.get('LOCALRSI_SITE_KEY','')
MEMBERS=ROOT/'data'/'hosted-members'
SERVICES={}
STOP=threading.Event()
NO_WINDOW=0x08000000 if os.name=='nt' else 0

def request(url,body=None,headers=None,timeout=30):
    h={'Content-Type':'application/json',**(headers or {})}
    req=urllib.request.Request(url,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,headers=h)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({})) if url.startswith('http://127.0.0.1:') else urllib.request.build_opener()
    try:
        with opener.open(req,timeout=timeout) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as exc:
        try:return exc.code,json.load(exc)
        except ValueError:return exc.code,{'error':'HTTP request failed'}

def relay(path,body):
    status,result=request(SITE+path,body,{'X-LocalRSI-Bridge':KEY,'OAI-Sites-Authorization':'Bearer '+SITE_KEY},40)
    if status>=400:raise RuntimeError('Relay returned HTTP '+str(status))
    return result

def backend(owner):
    member=hashlib.sha256(owner.encode()).hexdigest()
    if member in SERVICES and SERVICES[member]['process'].poll() is None:return SERVICES[member]['port']
    if len([s for s in SERVICES.values() if s['process'].poll() is None])>=8:raise RuntimeError('Member capacity reached')
    folder=MEMBERS/member;folder.mkdir(parents=True,exist_ok=True)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    environ=os.environ.copy()
    # Member services do not inherit any cloud transport credentials.
    for key in ('LOCALRSI_BRIDGE_KEY','LOCALRSI_SITE_KEY','LOCALRSI_SITE'):environ.pop(key,None)
    environ.update(LOCALRSI_DATA=str(folder/'data'),LOCALRSI_WORKSPACE=str(folder/'workspace'),LOCALRSI_PORT=str(port),LOCALRSI_HOSTED='1')
    with (folder/'service.log').open('ab') as log:
        process=subprocess.Popen([sys.executable,'-u',str(ROOT/'app.py')],cwd=ROOT,env=environ,stdout=log,stderr=log,creationflags=NO_WINDOW)
    SERVICES[member]={'process':process,'port':port}
    for _ in range(80):
        if process.poll() is not None:raise RuntimeError('Member backend failed to start')
        try:
            code,result=request(f'http://127.0.0.1:{port}/api/capabilities',timeout=1)
            if code==200 and result.get('shared_hosting'):return port
        except (OSError,ValueError):pass
        time.sleep(.25)
    process.terminate();raise RuntimeError('Member backend startup timeout')

def execute(job):
    path=job['path']
    if not path.startswith('/api/') or '?' in path or '#' in path or '..' in path:raise ValueError('Invalid API path')
    port=backend(job['owner'])
    payload=json.loads(job['payload']) if job['method']=='POST' else None
    status,result=request(f'http://127.0.0.1:{port}'+path,payload,timeout=150)
    if path=='/api/status' and status==200:result['workspace']='个人独立工作区'
    return {'id':job['id'],'lease':job['lease'],'status':status,'body':result}

def shutdown():
    STOP.set()
    for service in SERVICES.values():
        process=service['process']
        if process.poll() is None:process.terminate()
    for service in SERVICES.values():
        try:service['process'].wait(timeout=5)
        except subprocess.TimeoutExpired:service['process'].kill()

def heartbeat():
    while not STOP.is_set():
        try:relay('/relay/heartbeat',{})
        except Exception:pass
        STOP.wait(15)

def main():
    if not SITE.startswith('https://') or not KEY or not SITE_KEY:raise RuntimeError('Configure HTTPS site and relay credentials')
    MEMBERS.mkdir(parents=True,exist_ok=True)
    atexit.register(shutdown)
    threading.Thread(target=heartbeat,daemon=True).start()
    print('Hosted relay started; no public listener',flush=True)
    while not STOP.is_set():
        try:
            job=relay('/relay/claim',{}).get('job')
            if not job:STOP.wait(1.5);continue
            try:result=execute(job)
            except Exception:result={'id':job['id'],'lease':job['lease'],'status':503,'body':{'error':'计算端暂时无法处理请求，请稍后检查任务状态。'}}
            # Retry publishing the same result, never replay the underlying action.
            while not STOP.is_set():
                try:relay('/relay/result',result);break
                except Exception:STOP.wait(3)
        except (OSError,RuntimeError,ValueError):STOP.wait(5)

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:shutdown()
