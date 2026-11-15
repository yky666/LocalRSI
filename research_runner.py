"""Bounded experiment runner for reviewed commands; not an OS security sandbox.

No GPU jobs are started without explicit UUIDs in a supplied manifest. Does not
generate arbitrary commands, crawl the web, install dependencies, or deploy weights.
"""
import argparse,hashlib,json,math,os,pathlib,signal,subprocess,time,uuid

def validate(plan):
    for name in ('question','metric','evaluation_file'):
        if not isinstance(plan.get(name),str) or not plan[name]:raise ValueError('Missing '+name)
    if plan.get('direction') not in ('min','max'):raise ValueError('Use min or max')
    budget=plan.get('budget_seconds');timeout=plan.get('trial_seconds')
    if type(budget) is not int or not 1<=budget<=86400:raise ValueError('Budget must be 1–86400 seconds')
    if type(timeout) is not int or not 1<=timeout<=budget:raise ValueError('Invalid trial timeout')
    jobs=plan.get('trials')
    if not isinstance(jobs,list) or not 2<=len(jobs)<=20:raise ValueError('Use baseline plus 1–19 candidates')
    ids=[]
    for job in jobs:
        if not isinstance(job.get('id'),str) or not job['id']:raise ValueError('Missing trial ID')
        ids.append(job['id']);command=job.get('command')
        if not isinstance(command,list) or not command or any(not isinstance(c,str) or not c for c in command):raise ValueError('Use argv arrays, not shell strings')
    if len(ids)!=len(set(ids)) or ids[0]!='baseline':raise ValueError('First trial must be baseline; IDs must be unique')
    devices=plan.get('gpu_uuids',[])
    if not isinstance(devices,list) or any(not isinstance(d,str) or not d.startswith('GPU-') for d in devices):raise ValueError('Use GPU UUIDs')
    return plan

def ensure_idle(devices):
    if not devices:return
    available=subprocess.check_output(['nvidia-smi','--query-gpu=uuid','--format=csv,noheader'],text=True).splitlines()
    if any(d not in available for d in devices):raise ValueError('Allocated GPU not found on this host')
    occupied=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid','--format=csv,noheader'],text=True).splitlines()
    if set(devices)&set(occupied):raise RuntimeError('Allocated GPU already has compute processes; experiment deferred')

def stop_tree(process):
    if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    else:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    process.wait()

def run(plan,root,output):
    validate(plan);root=pathlib.Path(root).resolve();evaluation=(root/plan['evaluation_file']).resolve()
    if root not in evaluation.parents or not evaluation.is_file():raise ValueError('Evaluation file must exist within experiment directory')
    fingerprint=lambda:hashlib.sha256(evaluation.read_bytes()).hexdigest()
    digest=fingerprint();output=pathlib.Path(output)/uuid.uuid4().hex;output.mkdir(parents=True)
    (output/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    results=[];started=time.monotonic();env=os.environ.copy();env['CUDA_VISIBLE_DEVICES']=','.join(plan.get('gpu_uuids',[]))
    env['LOCALRSI_EVALUATION_FILE']=str(evaluation)
    for index,trial in enumerate(plan['trials']):
        remaining=plan['budget_seconds']-(time.monotonic()-started)
        if remaining<1:break
        ensure_idle(plan.get('gpu_uuids',[]))
        if fingerprint()!=digest:raise RuntimeError('Evaluation changed; refuse further trials')
        log=output/(str(index)+'.log');record={'id':trial['id'],'status':'failed'};begin=time.monotonic()
        with log.open('wb') as stream:
            process=subprocess.Popen(trial['command'],cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=os.name!='nt')
            try:record['exit_code']=process.wait(timeout=min(remaining,plan['trial_seconds']))
            except subprocess.TimeoutExpired:stop_tree(process);record['status']='timeout'
        record['seconds']=round(time.monotonic()-begin,3)
        if fingerprint()!=digest:record['status']='invalid_evaluation_modified'
        elif record.get('exit_code')==0:
            try:
                # Only the final JSON line defines a measured metric, not narrative claims.
                with log.open('rb') as stream:
                    stream.seek(max(0,log.stat().st_size-65536));last=stream.read().decode('utf-8').splitlines()[-1]
                value=json.loads(last)[plan['metric']]
                if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Non-finite metric')
                record.update(status='measured',value=value)
            except (ValueError,KeyError,IndexError,UnicodeError):record['status']='missing_metric'
        results.append(record)
        report={'question':plan['question'],'evaluation_sha256':digest,'trials':results,'deployed':False,'scope':'Configured metric only; independent holdout and regression checks required before promotion'}
        baseline=results[0]
        candidates=[r for r in results[1:] if r['status']=='measured' and baseline['status']=='measured' and ((r['value']<baseline['value']) if plan['direction']=='min' else (r['value']>baseline['value']))]
        report['improved_candidates']=[r['id'] for r in candidates]
        (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if record['status']=='invalid_evaluation_modified':break
    return str(output)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('manifest');parser.add_argument('--output',required=True);parser.add_argument('--run',action='store_true')
    args=parser.parse_args();path=pathlib.Path(args.manifest).resolve();plan=validate(json.loads(path.read_text(encoding='utf-8')))
    print(run(plan,path.parent,args.output) if args.run else 'Manifest valid. No commands executed. Use --run only after reviewing command arrays and resource allocation.')
