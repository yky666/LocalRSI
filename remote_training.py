"""Generate reviewable upload/launch plans. No implicit SSH or CUDA changes."""
import json,pathlib,shlex,re
import features

def plan(dataset,model='Qwen/Qwen3-4B-Instruct-2507',qlora=True):
    cfg=features.config()['training']
    for name in ('ssh_host','ssh_user','remote_directory','gpu'):
        if not cfg.get(name):raise ValueError('Configure training.'+name+' before planning a remote job')
    host=cfg['ssh_host'];user=cfg['ssh_user'];directory=cfg['remote_directory'];gpu=cfg['gpu'];python=cfg.get('python','python')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',host) or host.startswith('-'):raise ValueError('Invalid SSH host')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',user) or user.startswith('-'):raise ValueError('Invalid SSH user')
    if not directory.startswith('/') or not re.fullmatch(r'[A-Za-z0-9_./-]+',directory):raise ValueError('Use an absolute remote path without spaces')
    if not re.fullmatch(r'[0-9,]+',gpu):raise ValueError('Use explicit GPU indices, e.g. 1')
    dataset=pathlib.Path(dataset).resolve()
    if features.DATA.resolve() not in dataset.parents:raise ValueError('Dataset must be a reviewed local export')
    command=f'cd {shlex.quote(directory)} && CUDA_VISIBLE_DEVICES={shlex.quote(gpu)} {shlex.quote(python)} train_lora.py --model {shlex.quote(model)} --data dataset --output adapter --steps 100'+(' --qlora' if qlora else '')
    return {'destination':user+'@'+host,'remote_directory':directory,'upload_files':[str(features.ROOT/'train_lora.py'),str(dataset/'train.jsonl'),str(dataset/'test.jsonl')],'launch_command':command,'requirements':'Create a separate environment manually using requirements-training.txt. No driver/CUDA changes are performed.','status':'plan_only','approval_required':True}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('dataset');p.add_argument('--model',default='Qwen/Qwen3-4B-Instruct-2507');a=p.parse_args()
    print(json.dumps(plan(a.dataset,a.model),ensure_ascii=False,indent=2))
