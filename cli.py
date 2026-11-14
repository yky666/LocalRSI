import argparse,base64,json,mimetypes,pathlib,time,urllib.request

def api(path,body=None):
    req=urllib.request.Request('http://127.0.0.1:8090'+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=30) as r:return json.load(r)

def main():
    p=argparse.ArgumentParser(description='LocalRSI local agent CLI')
    p.add_argument('prompt',nargs='?');p.add_argument('--image');p.add_argument('--note');p.add_argument('--status',action='store_true')
    p.add_argument('--provider',choices=['local','remote'],default='local');p.add_argument('--groups',default='');p.add_argument('--continue-task');p.add_argument('--index');p.add_argument('--search');p.add_argument('--record',action='store_true');a=p.parse_args()
    if a.status:print(json.dumps(api('/api/status'),ensure_ascii=False,indent=2));return
    if a.note:print(api('/api/notes',{'text':a.note}));return
    if a.index:print(json.dumps(api('/api/index',{'path':a.index}),ensure_ascii=False,indent=2));return
    if a.search:print(json.dumps(api('/api/search',{'query':a.search}),ensure_ascii=False,indent=2));return
    if a.record:print(api('/api/record',{})['text']);return
    parent=a.continue_task
    while True:
        prompt=a.prompt or input('\nLocalRSI > ')
        if prompt.strip() in ('/exit','/quit'):return
        body={'prompt':prompt,'provider':a.provider,'parent':parent,'groups':[s for s in a.groups.split(',') if s]}
        if a.image:
            image=pathlib.Path(a.image);mime=mimetypes.guess_type(image.name)[0]
            if mime not in ('image/png','image/jpeg') or image.stat().st_size>5*1024*1024:raise ValueError('Use PNG/JPEG under 5MB')
            body['image']='data:'+mime+';base64,'+base64.b64encode(image.read_bytes()).decode()
        task=api('/api/tasks',body)['id'];seen=0
        while True:
            t=api('/api/tasks/'+task)
            for e in t['events'][seen:]:print('  '+e['text'])
            seen=len(t['events'])
            if t['status']=='approval':
                print(json.dumps(t['pending'].get('preview',t['pending']['arguments']),ensure_ascii=False,indent=2))
                approved=input('Approve this exact action? [y/N] ').strip().lower()=='y'
                api('/api/approve',{'id':task,'approve':approved})
            elif t['status'] in ('done','error','interrupted','cancelled'):print('\n'+t['answer']);parent=task if t['status']=='done' else None;break
            time.sleep(1)
        if a.prompt:return

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: print('\nCLI closed; an active server task may continue.')
