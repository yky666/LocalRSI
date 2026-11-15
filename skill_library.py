"""Bundled, reviewable instruction skills. Skills never grant tool permissions."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'skills'

def catalog():
    result=[]
    for path in sorted(ROOT.glob('*/SKILL.md')):
        text=path.read_text(encoding='utf-8')
        result.append({'id':path.parent.name,'title':text.splitlines()[0].lstrip('# '),
                       'sha256':hashlib.sha256(text.encode()).hexdigest(),'instructions':text})
    return result

def select(ids):
    if not isinstance(ids,list) or len(ids)>3 or any(not isinstance(i,str) for i in ids):
        raise ValueError('Select at most three bundled skills')
    available={s['id']:s for s in catalog()}
    if any(i not in available for i in ids):raise ValueError('Unknown skill')
    return [available[i] for i in dict.fromkeys(ids)]
