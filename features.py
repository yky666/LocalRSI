"""Document, retrieval, browser and feedback capabilities; imports are lazy."""
import base64, concurrent.futures, difflib, hashlib, json, math, os, pathlib, queue, re, sqlite3, subprocess, threading, time, urllib.parse, uuid

ROOT=pathlib.Path(__file__).resolve().parent
DATA=pathlib.Path(os.environ.get('LOCALRSI_DATA',str(ROOT/'data'))).resolve()
WORK=pathlib.Path(os.environ.get('LOCALRSI_WORKSPACE',str(ROOT/'workspace'))).resolve()
_embed=None
_embed_lock=threading.RLock()
_browser=None
_jobs={}

class Connection(sqlite3.Connection):
    def __exit__(self,*args):
        try:return super().__exit__(*args)
        finally:self.close()

def config():
    p=pathlib.Path(os.environ.get('LOCALRSI_CONFIG',str(ROOT/'config.json')))
    return json.loads((p if p.exists() else ROOT/'config.example.json').read_text(encoding='utf-8-sig'))

def database():
    c=sqlite3.connect(DATA/'knowledge.sqlite3',timeout=30,factory=Connection)
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY,path TEXT,page INTEGER,part INTEGER,text TEXT,vector TEXT,model TEXT,hash TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY,task TEXT,score INTEGER,correction TEXT,created REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS profiles(id TEXT PRIMARY KEY,prompt TEXT,created REAL,active INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS evaluations(id TEXT PRIMARY KEY,result TEXT,created REAL)')
    return c

def document(path,page=1):
    suffix=path.suffix.lower()
    if suffix=='.pdf':
        import pymupdf
        with pymupdf.open(path) as doc:
            if not 1<=page<=len(doc):raise ValueError('Page outside document')
            text=doc[page-1].get_text()
            return {'path':str(path.relative_to(WORK)),'page':page,'pages':len(doc),'text':text[:14000],'needs_ocr':not text.strip()}
    if suffix=='.docx':
        from docx import Document
        d=Document(path)
        text='\n'.join(p.text for p in d.paragraphs)
        text+='\n'+'\n'.join(' | '.join(c.text for c in r.cells) for t in d.tables for r in t.rows)
        return {'path':str(path.relative_to(WORK)),'page':1,'pages':1,'text':text[:14000]}
    if suffix in ('.txt','.md','.py','.json','.csv','.html','.js','.ts','.log'):
        return {'path':str(path.relative_to(WORK)),'page':1,'pages':1,'text':path.read_text(encoding='utf-8')[:14000]}
    raise ValueError('Supported: PDF, DOCX, UTF-8 text/code')

def all_pages(path):
    if path.suffix.lower()=='.pdf':
        import pymupdf
        with pymupdf.open(path) as doc:
            if len(doc)>500:raise ValueError('Limit 500 pages per indexing job')
            for i,page in enumerate(doc):yield i+1,page.get_text()
    else:yield 1,document(path)['text']

def embedding_model():
    global _embed
    with _embed_lock:
        if _embed is None:
            from fastembed import TextEmbedding
            cfg=config()['embedding']
            local=ROOT/cfg['cache_dir']/'bge-small-zh'
            kwargs={'specific_model_path':str(local),'local_files_only':True} if (local/'model_optimized.onnx').exists() and cfg['model']=='BAAI/bge-small-zh-v1.5' else {}
            _embed=TextEmbedding(model_name=cfg['model'],cache_dir=str(ROOT/cfg['cache_dir']),threads=2,providers=['CPUExecutionProvider'],**kwargs)
        return _embed

def vectors(texts,query=False):
    with _embed_lock:
        model=embedding_model()
        stream=model.query_embed(texts) if query else model.passage_embed(texts)
        return [v.tolist() for v in stream]

def index(path):
    if path.stat().st_size>80*1024*1024:raise ValueError('File exceeds 80MB')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    rel=str(path.relative_to(WORK));model=config()['embedding']['model']
    with database() as c:
        row=c.execute('SELECT count(*) FROM chunks WHERE path=? AND hash=? AND model=?',(rel,digest,model)).fetchone()
        if row[0]:return {'path':rel,'chunks':row[0],'cached':True}
    chunks=[]
    for page,text in all_pages(path):
        for part,start in enumerate(range(0,len(text),600)):
            piece=text[start:start+750].strip()
            if piece:chunks.append((page,part,piece))
    if not chunks:raise ValueError('No text found. Run OCR on scanned pages before indexing.')
    if len(chunks)>2000:raise ValueError('Too many chunks; split document')
    emb=[]
    for start in range(0,len(chunks),16):emb.extend(vectors([x[2] for x in chunks[start:start+16]]))
    with database() as c:
        c.execute('DELETE FROM chunks WHERE path=?',(rel,))
        c.executemany('INSERT INTO chunks(path,page,part,text,vector,model,hash) VALUES(?,?,?,?,?,?,?)',[(rel,p,n,t,json.dumps(v),model,digest) for (p,n,t),v in zip(chunks,emb)])
    return {'path':rel,'chunks':len(chunks),'model':model,'cached':False}

def terms(s):
    s=s.lower();return set(re.findall(r'[a-z0-9_]+',s)+[s[i:i+2] for i in range(len(s)-1) if '\u4e00'<=s[i]<='\u9fff'])

def search(query,limit=5):
    with database() as c:rows=c.execute('SELECT id,path,page,text,vector FROM chunks WHERE model=?',(config()['embedding']['model'],)).fetchall()
    if not rows:return []
    q=vectors([query],True)[0];qt=terms(query);rank=[]
    for id,path,page,text,v in rows:
        v=json.loads(v)
        cosine=sum(a*b for a,b in zip(q,v))/(math.sqrt(sum(x*x for x in q))*math.sqrt(sum(x*x for x in v)) or 1)
        lexical=len(qt & terms(text))/max(1,len(qt))
        rank.append({'id':id,'source':path,'page':page,'text':text,'score':round(.8*cosine+.2*lexical,4),'citation':f'[{path}, p.{page}, #{id}]'})
    return sorted(rank,key=lambda r:r['score'],reverse=True)[:min(limit,10)]

def background_index(path):
    id=uuid.uuid4().hex;_jobs[id]={'id':id,'status':'running','path':str(path.relative_to(WORK))}
    def worker():
        try:_jobs[id].update(status='done',result=index(path))
        except Exception as e:_jobs[id].update(status='error',error=str(e))
    threading.Thread(target=worker,daemon=True).start();return _jobs[id]

def make_docx(path,title,content):
    from docx import Document
    if path.suffix.lower()!='.docx':raise ValueError('Use .docx extension')
    d=Document();d.add_heading(title,0)
    for line in content.split('\n'):
        if line.startswith('## '):d.add_heading(line[3:],2)
        elif line.startswith('# '):d.add_heading(line[2:],1)
        else:d.add_paragraph(line)
    path.parent.mkdir(parents=True,exist_ok=True);d.save(path);return {'saved':str(path.relative_to(WORK))}

def edit_patch(path,old,new):
    content=path.read_text(encoding='utf-8')
    if not old or content.count(old)!=1:raise ValueError('Old text must match exactly once')
    updated=content.replace(old,new,1)
    diff=''.join(difflib.unified_diff(content.splitlines(True),updated.splitlines(True),fromfile=str(path),tofile=str(path)))
    return content,updated,diff

class Browser:
    def __init__(self):
        self.queue=queue.Queue();threading.Thread(target=self.worker,daemon=True).start()
    def worker(self):
        from playwright.sync_api import sync_playwright
        context=None;page=None
        with sync_playwright() as p:
            while True:
                action,args,future=self.queue.get()
                try:
                    if context is None:
                        cfg=config();context=p.chromium.launch_persistent_context(str(DATA/'browser-profile'),channel=cfg.get('browser_channel','msedge'),headless=cfg.get('browser_headless',False),viewport={'width':1200,'height':800},accept_downloads=False)
                        page=context.pages[0] if context.pages else context.new_page()
                    if action=='open':
                        url=urllib.parse.urlparse(args['url'])
                        if url.scheme not in ('http','https'):raise ValueError('Only http(s) URLs are allowed')
                        page.goto(args['url'],wait_until='domcontentloaded',timeout=30000)
                    elif action=='click':page.locator(args['selector']).click(timeout=10000)
                    elif action=='type':page.locator(args['selector']).fill(args['text'],timeout=10000)
                    elif action=='screenshot':page.screenshot(path=args['path'],full_page=False)
                    elif action=='close':context.close();context=None;future.set_result({'closed':True});continue
                    elif action!='read':raise ValueError('Unknown browser action')
                    result={'url':page.url,'title':page.title(),'text':page.locator('body').inner_text(timeout=10000)[:9000]}
                    result['controls']=page.locator('a,button,input,textarea,select').evaluate_all('(els)=>els.slice(0,60).map(e=>({tag:e.tagName,id:e.id,name:e.getAttribute("name"),type:e.getAttribute("type"),text:(e.innerText||e.getAttribute("placeholder")||"").slice(0,100)}))')
                    future.set_result(result)
                except Exception as e:future.set_exception(e)
    def call(self,action,args):
        future=concurrent.futures.Future();self.queue.put((action,args,future));return future.result(timeout=50)

def browser(action,args):
    global _browser
    if _browser is None:_browser=Browser()
    return _browser.call(action,args)

def screenshot(path):
    from PIL import ImageGrab
    path.parent.mkdir(parents=True,exist_ok=True);ImageGrab.grab().save(path)
    return {'saved':str(path.relative_to(WORK))}

def desktop(action,args):
    import ctypes
    u=ctypes.windll.user32
    if action=='click':
        x=int(args['x']);y=int(args['y'])
        if not 0<=x<u.GetSystemMetrics(0) or not 0<=y<u.GetSystemMetrics(1):raise ValueError('Coordinates outside primary display')
        u.SetCursorPos(x,y);u.mouse_event(2,0,0,0,0);u.mouse_event(4,0,0,0,0)
    elif action=='type':
        # Unicode SendInput; exact text is displayed before approval.
        ULONG_PTR=ctypes.c_size_t
        class KEYBDINPUT(ctypes.Structure):_fields_=[('wVk',ctypes.c_ushort),('wScan',ctypes.c_ushort),('dwFlags',ctypes.c_ulong),('time',ctypes.c_ulong),('dwExtraInfo',ULONG_PTR)]
        class MOUSEINPUT(ctypes.Structure):_fields_=[('dx',ctypes.c_long),('dy',ctypes.c_long),('mouseData',ctypes.c_ulong),('dwFlags',ctypes.c_ulong),('time',ctypes.c_ulong),('dwExtraInfo',ULONG_PTR)]
        class UNION(ctypes.Union):_fields_=[('ki',KEYBDINPUT),('mi',MOUSEINPUT)]
        class INPUT(ctypes.Structure):_fields_=[('type',ctypes.c_ulong),('u',UNION)]
        for b1,b2 in zip(args['text'].encode('utf-16-le')[::2],args['text'].encode('utf-16-le')[1::2]):
            code=b1+256*b2
            for flags in (4,6):
                item=INPUT(type=1,u=UNION(ki=KEYBDINPUT(0,code,flags,0,0)))
                if u.SendInput(1,ctypes.byref(item),ctypes.sizeof(INPUT))!=1:raise RuntimeError('Input blocked by Windows')
    else:raise ValueError('Unsupported desktop action')
    return {'executed':action}

def feedback(task,score,correction):
    if score not in (-1,0,1):raise ValueError('Score must be -1, 0 or 1')
    with database() as c:c.execute('INSERT INTO feedback(task,score,correction,created) VALUES(?,?,?,?)',(task,score,correction[:12000],time.time()))
    return {'saved':True}

def export_training(tasks):
    rows=[]
    with database() as c:feedbacks=c.execute('SELECT task,score,correction FROM feedback ORDER BY id').fetchall()
    seen=set()
    for id,score,correction in feedbacks:
        if id in seen or id not in tasks:continue
        if score<=0 and not correction:continue
        t=tasks[id];user=next((m['content'] for m in reversed(t['messages']) if m['role']=='user'),'')
        answer=correction or t.get('answer','')
        if not user or not answer:continue
        digest=hashlib.sha256((user+answer).encode()).hexdigest();seen.add(id)
        rows.append({'messages':[{'role':'user','content':user},{'role':'assistant','content':answer}],'source_task':id,'sha256':digest})
    # Stable hash partition; never shuffle test examples into training.
    folder=DATA/'training-export'/str(int(time.time()));folder.mkdir(parents=True)
    for split in ('train','test'):
        selected=[r for r in rows if ('test' if int(r['sha256'][:8],16)%5==0 else 'train')==split]
        (folder/(split+'.jsonl')).write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in selected),encoding='utf-8')
    return {'directory':str(folder),'samples':len(rows),'warning':'Review private data and correctness before training; tiny datasets are not sufficient.'}
