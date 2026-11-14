"""Opt-in live checks; never performs desktop or external browser actions."""
import json,pathlib,sys,time,urllib.request,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def api(path,body=None):
    r=urllib.request.Request('http://127.0.0.1:8090'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(r,timeout=60) as x:return json.load(x)

def wait(id):
    for _ in range(240):
        t=api('/api/tasks/'+id)
        if t['status'] in ('done','error','approval','cancelled'):return t
        time.sleep(.5)
    raise TimeoutError()

if __name__=='__main__':
    start=time.perf_counter()
    t=wait(api('/api/tasks',{'prompt':'只输出：本地运行'})['id'])
    assert t['status']=='done',t
    print(json.dumps({'test':'live_text','seconds':round(time.perf_counter()-start,3),'answer':t['answer'],'metrics':t.get('metrics')},ensure_ascii=False))
