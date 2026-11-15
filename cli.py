import argparse,base64,json,mimetypes,pathlib,time,urllib.request,sys

def api(path,body=None):
    req=urllib.request.Request('http://127.0.0.1:8090'+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=30) as r:return json.load(r)

def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    p=argparse.ArgumentParser(description='LocalRSI local agent CLI')
    p.add_argument('prompt',nargs='?');p.add_argument('--image');p.add_argument('--note');p.add_argument('--status',action='store_true')
    p.add_argument('--skills',default='',help='Comma-separated bundled skill IDs')
    p.add_argument('--attach',action='append',default=[],help='Existing workspace file path; repeat up to eight times')
    p.add_argument('--thinking',choices=['fast','standard','deep'],default='standard');p.add_argument('--mode',choices=['chat','plan','agent'],default='agent');p.add_argument('--goal',action='store_true');p.add_argument('--mcp',default='');p.add_argument('--resume');p.add_argument('--capabilities',action='store_true');p.add_argument('--provider',choices=['local','remote'],default='local');p.add_argument('--groups',default='');p.add_argument('--continue-task');p.add_argument('--index');p.add_argument('--search');p.add_argument('--record',action='store_true');a=p.parse_args()
    if a.capabilities:print(json.dumps(api('/api/capabilities'),ensure_ascii=False,indent=2));return
    if a.status:print(json.dumps(api('/api/status'),ensure_ascii=False,indent=2));return
    if a.note:print(api('/api/notes',{'text':a.note}));return
    if a.index:print(json.dumps(api('/api/index',{'path':a.index}),ensure_ascii=False,indent=2));return
    if a.search:print(json.dumps(api('/api/search',{'query':a.search}),ensure_ascii=False,indent=2));return
    if a.record:print(api('/api/record',{})['text']);return
    parent=a.continue_task
    while True:
        prompt=a.prompt or ('继续目标' if a.resume else input('\nLocalRSI > '))
        if prompt.strip() in ('/exit','/quit'):return
        body={'thinking':a.thinking,'agent_mode':a.mode,'goal':a.goal,'mcp_servers':[s for s in a.mcp.split(',') if s],'prompt':prompt,'provider':a.provider,'parent':parent,'groups':[s for s in a.groups.split(',') if s]}
        body.update(skills=[s for s in a.skills.split(',') if s],attachments=a.attach)
        if a.image:
            image=pathlib.Path(a.image);mime=mimetypes.guess_type(image.name)[0]
            if mime not in ('image/png','image/jpeg') or image.stat().st_size>5*1024*1024:raise ValueError('Use PNG/JPEG under 5MB')
            body['image']='data:'+mime+';base64,'+base64.b64encode(image.read_bytes()).decode()
        task=(api('/api/resume',{'id':a.resume}) if a.resume else api('/api/tasks',body))['id'];seen=0
        while True:
            t=api('/api/tasks/'+task)
            for e in t['events'][seen:]:print('  '+e['text'])
            seen=len(t['events'])
            if t['status']=='approval':
                print(json.dumps(t['pending'].get('preview',t['pending']['arguments']),ensure_ascii=False,indent=2))
                approved=input('Approve this exact action? [y/N] ').strip().lower()=='y'
                api('/api/approve',{'id':task,'approve':approved})
            elif t['status'] in ('done','error','interrupted','cancelled','budget_exhausted'):print('\n'+t['answer']);parent=task if t['status']=='done' else None;break
            time.sleep(1)
        if a.prompt or a.resume:return

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: print('\nCLI closed; an active server task may continue.')
