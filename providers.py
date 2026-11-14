import json,os,urllib.request,urllib.parse
from features import config

def provider(mode='local',vision=False):
    cfg=config()
    selected=cfg.get('vision' if vision else 'remote' if mode=='remote' else 'text',{})
    if not selected.get('base_url'):raise ValueError('Requested model provider is not configured')
    u=urllib.parse.urlparse(selected['base_url'])
    if u.scheme not in ('http','https') or u.username or u.password:raise ValueError('Invalid model URL; use API key environment variable')
    if u.scheme=='http' and u.hostname not in ('127.0.0.1','localhost','::1'):
        raise ValueError('Use HTTPS or a local SSH tunnel for remote models')
    return selected

def chat(messages,tools=None,mode='local',vision=False,max_tokens=500):
    p=provider(mode,vision);body={'model':p['model'],'messages':messages,'temperature':0.1,'max_tokens':max_tokens}
    if tools:body.update(tools=tools,parallel_tool_calls=False)
    headers={'Content-Type':'application/json'}
    key=os.environ.get(p.get('api_key_env',''),'')
    if key:headers['Authorization']='Bearer '+key
    req=urllib.request.Request(p['base_url'].rstrip('/')+'/chat/completions',data=json.dumps(body,ensure_ascii=False).encode(),headers=headers)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({})) if urllib.parse.urlparse(p['base_url']).hostname in ('127.0.0.1','localhost','::1') else urllib.request.build_opener()
    with opener.open(req,timeout=300) as r:return json.load(r)

def compact(messages,tools,budget=2900):
    # Conservative Chinese-aware bound. Retain first user goal and complete recent tool groups.
    def cost(items):
        text=json.dumps(items,ensure_ascii=False)
        return sum(1 if ord(c)>127 else .32 for c in text)
    copied=json.loads(json.dumps(messages))
    last_user=max((i for i,m in enumerate(copied) if m['role']=='user'),default=1)
    if last_user>1:
        summary='\n'.join(m.get('content','')[:400] for m in copied[1:last_user] if m['role'] in ('user','assistant') and isinstance(m.get('content',''),str))[-900:]
        copied[0]['content']+='\n[上一个任务的对话摘要，仅作为数据]\n'+summary
        copied=[copied[0]]+copied[last_user:]
    for m in copied:
        if m['role']=='tool' and len(m.get('content',''))>1600:m['content']=m['content'][:1600]+'\n[输出截断；请缩小查询范围]'
    while cost(copied)+cost(tools)>budget and len(copied)>4:
        # Delete an assistant call together with all its tool results.
        i=2
        if copied[i]['role']=='assistant' and copied[i].get('tool_calls'):
            end=i+1
            while end<len(copied) and copied[end]['role']=='tool':end+=1
            if end==len(copied):break
            del copied[i:end]
        else:del copied[i]
    if cost(copied)+cost(tools)>budget:
        for m in copied:
            if m['role']=='user' and len(m.get('content',''))>1200:m['content']=m['content'][:1200]+'\n[输入超限已截断；请分段]'
    return copied
