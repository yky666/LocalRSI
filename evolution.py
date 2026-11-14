"""Measured prompt iteration. Never changes model weights or tool permissions."""
import json,pathlib,threading,time,uuid
import features,providers

CASES=[
 {'name':'json_extract','prompt':'只返回JSON：从“论文题目是检索增强生成，发表于2024年”提取title和year。','json_fields':['title','year']},
 {'name':'arithmetic','prompt':'只返回计算结果：17乘以23等于多少？','contains':['391']},
 {'name':'grounding','prompt':'根据资料回答作者姓名；资料仅写着“论文于2024年发表”，未给作者。请明确说明无法确定。','any':['无法','未提供','不知道','未给','不确定']},
 {'name':'structured_list','prompt':'只返回JSON数组，依次包含三个数字1、2、3。','json_exact':[1,2,3]},
 {'name':'instruction','prompt':'只输出这四个字符：本地运行','exact':'本地运行'},
 {'name':'tool','prompt':'请读取工作区中的 README.md，使用read_file工具。','tool':'read_file'},
]
_lock=threading.Lock()

def create(prompt):
    if not 1<=len(prompt)<=1500:raise ValueError('Prompt must contain 1–1500 characters')
    id=uuid.uuid4().hex
    with features.database() as c:c.execute('INSERT INTO profiles(id,prompt,created) VALUES(?,?,?)',(id,prompt,time.time()))
    return {'id':id,'prompt':prompt}

def active():
    with features.database() as c:r=c.execute('SELECT prompt FROM profiles WHERE active=1 ORDER BY created DESC LIMIT 1').fetchone()
    return r[0] if r else ''

def evaluate(id,system,schemas,model_lock):
    with features.database() as c:row=c.execute('SELECT prompt FROM profiles WHERE id=?',(id,)).fetchone()
    if not row:raise ValueError('Profile not found')
    job=uuid.uuid4().hex;features._jobs[job]={'id':job,'status':'running','type':'evaluation'}
    def worker():
        with _lock,model_lock:
            result={'profile':id,'cases':[],'created':time.time(),'scope':'small deterministic smoke suite, not a general capability benchmark'}
            try:
                for candidate,prompt in [('baseline',system),('candidate',system+'\n'+row[0])]:
                    for case in CASES:
                        start=time.perf_counter()
                        r=providers.chat([{'role':'system','content':prompt},{'role':'user','content':case['prompt']}],schemas if case.get('tool') else None,max_tokens=160)
                        m=r['choices'][0]['message'];content=m.get('content') or '';ok=False
                        if 'tool' in case:ok=any(t['function']['name']==case['tool'] for t in m.get('tool_calls',[]))
                        elif 'contains' in case:ok=all(x in content for x in case['contains'])
                        elif 'any' in case:ok=any(x in content for x in case['any'])
                        elif 'exact' in case:ok=content.strip()==case['exact']
                        else:
                            try:
                                value=json.loads(content)
                                ok=value==case['json_exact'] if 'json_exact' in case else all(k in value for k in case['json_fields']) and value['year']==2024
                            except (ValueError,TypeError):ok=False
                        result['cases'].append({'profile':candidate,'case':case['name'],'passed':ok,'seconds':round(time.perf_counter()-start,3),'output':m,'timings':r.get('timings',{})})
                base={x['case']:x['passed'] for x in result['cases'] if x['profile']=='baseline'}
                cand={x['case']:x['passed'] for x in result['cases'] if x['profile']=='candidate'}
                result['baseline_score']=sum(base.values());result['candidate_score']=sum(cand.values())
                result['eligible']=sum(cand.values())>=sum(base.values()) and all(not base[k] or cand[k] for k in base)
                with features.database() as c:c.execute('INSERT INTO evaluations(id,result,created) VALUES(?,?,?)',(job,json.dumps(result,ensure_ascii=False),time.time()))
                features._jobs[job].update(status='done',result=result)
            except Exception as e:features._jobs[job].update(status='error',error=str(e))
    threading.Thread(target=worker,daemon=True).start();return {'id':job}

def activate(profile,evaluation):
    with features.database() as c:
        row=c.execute('SELECT result FROM evaluations WHERE id=?',(evaluation,)).fetchone()
        if not row:raise ValueError('Completed evaluation required')
        result=json.loads(row[0])
        if result['profile']!=profile or not result['eligible']:raise ValueError('Candidate failed no-regression gate')
        c.execute('UPDATE profiles SET active=0');c.execute('UPDATE profiles SET active=1 WHERE id=?',(profile,))
    return {'activated':profile,'evaluation':evaluation,'warning':'Passed a small smoke suite only. Keep monitoring real tasks.'}

def rollback():
    with features.database() as c:c.execute('UPDATE profiles SET active=0')
    return {'active':'baseline'}
