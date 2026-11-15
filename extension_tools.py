import base64,json,pathlib,subprocess,uuid,shutil,os
import features as f

DEFS={
'read_file_lines':('Read a bounded range of UTF-8 source lines with line numbers',{'path':'string','start':'integer','end':'integer'},False,'coding'),
'search_files':('Search literal text in workspace source files; returns paths and line numbers',{'path':'string','query':'string'},False,'coding'),
'read_document':('Read one page of PDF/DOCX/text with source',{'path':'string','page':'integer'},False,'documents'),
'index_document':('Index document in local vector knowledge base',{'path':'string'},False,'knowledge'),
'search_knowledge':('Retrieve cited knowledge chunks',{'query':'string'},False,'knowledge'),
'create_docx':('Create Word document',{'path':'string','title':'string','content':'string'},True,'documents'),
'ocr_image':('Read text in an image using Windows OCR',{'path':'string'},False,'vision'),
'analyze_image':('Describe workspace image using vision model',{'path':'string'},False,'vision'),
'render_pdf_page':('Render PDF page to PNG for OCR or vision',{'path':'string','page':'integer','output':'string'},True,'documents'),
'apply_edit':('Replace exact text once; approval includes diff',{'path':'string','old':'string','new':'string'},True,'coding'),
'run_tests':('Run project tests with visible command',{'command':'string'},True,'coding'),
'browser_open':('Open URL in isolated local browser',{'url':'string'},True,'browser'),
'browser_read':('Read current browser page and controls',{},False,'browser'),
'browser_click':('Click exact CSS selector',{'selector':'string'},True,'browser'),
'browser_type':('Fill exact browser input',{'selector':'string','text':'string'},True,'browser'),
'browser_screenshot':('Save current browser screenshot',{'path':'string'},True,'browser'),
'desktop_screenshot':('Capture primary desktop to workspace',{'path':'string'},True,'desktop'),
'desktop_click':('Click approved screen coordinates',{'x':'integer','y':'integer'},True,'desktop'),
'desktop_type':('Type exact text in focused desktop window',{'text':'string'},True,'desktop'),
'speak':('Read text aloud using offline Windows voice',{'text':'string'},True,'audio'),
'transcribe_audio':('Transcribe local mono WAV using offline Vosk',{'path':'string'},False,'audio'),
}

def schemas(groups):
    return [{'type':'function','function':{'name':name,'description':desc,'parameters':{'type':'object','properties':{k:{'type':v} for k,v in args.items()},'required':list(args),'additionalProperties':False}}} for name,(desc,args,approval,group) in DEFS.items() if group in groups]

def groups_for(prompt):
    mapping={'documents':['pdf','docx','word','文档','论文'],'knowledge':['知识','检索','索引','rag'],'vision':['图片','截图','ocr','image'],'coding':['代码','测试','补丁','修改','code'],'browser':['浏览器','网页','网址','http','browser'],'desktop':['桌面','鼠标','屏幕','desktop'],'audio':['语音','音频','朗读','wav']}
    return [g for g,words in mapping.items() if any(w in prompt.lower() for w in words)]

def approval_preview(name,args,safe_path):
    preview=dict(args)
    if name=='apply_edit':preview['diff']=f.edit_patch(safe_path(args['path']),args['old'],args['new'])[2]
    elif name=='write_file':
        p=safe_path(args['path']);old=p.read_text(encoding='utf-8') if p.exists() else ''
        import difflib
        preview['diff']=''.join(difflib.unified_diff(old.splitlines(True),args['content'].splitlines(True),fromfile=args['path'],tofile=args['path']))
    return preview

def backup(path):
    if path.exists():shutil.copy2(path,f.DATA/('backup-'+uuid.uuid4().hex+path.suffix))

def execute(name,args,app):
    path=lambda key='path':app.safe_path(args[key])
    if name=='read_file_lines':
        start,end=args['start'],args['end']
        if type(start) is not int or type(end) is not int or not 1<=start<=end or end-start>=400:raise ValueError('Read 1–400 lines at a time')
        p=path()
        if p.stat().st_size>2*1024*1024:raise ValueError('Source file exceeds 2MB')
        lines=p.read_text(encoding='utf-8').splitlines()
        return {'path':args['path'],'total_lines':len(lines),'text':'\n'.join(str(i+1)+': '+line for i,line in enumerate(lines) if start<=i+1<=end)[:16000]}
    if name=='search_files':
        root=path();query=args['query'];matches=[];scanned=0
        if not isinstance(query,str) or not 1<=len(query)<=300:raise ValueError('Use a literal query of 1–300 characters')
        if not root.is_dir():raise ValueError('Search path must be a directory')
        for folder,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=[d for d in sorted(dirs) if d not in ('.git','node_modules','venv','.venv','__pycache__') and not (pathlib.Path(folder)/d).is_symlink() and not (hasattr(pathlib.Path(folder)/d,'is_junction') and (pathlib.Path(folder)/d).is_junction())]
            for filename in sorted(files):
                scanned+=1
                if scanned>1000:return {'matches':matches,'truncated':True,'scanned':1000}
                try:
                    p=app.safe_path(str((pathlib.Path(folder)/filename).relative_to(app.WORK)))
                    if not p.is_file() or p.stat().st_size>1024*1024:continue
                    text=p.read_text(encoding='utf-8')
                    if '\0' in text:continue
                    for number,line in enumerate(text.splitlines(),1):
                        if query.casefold() in line.casefold():matches.append({'path':str(p.relative_to(app.WORK)),'line':number,'text':line[:400]})
                        if len(matches)>=50:return {'matches':matches,'truncated':True,'scanned':scanned}
                except (OSError,UnicodeError,ValueError):continue
        return {'matches':matches,'truncated':False,'scanned':scanned}
    if name=='read_document':return f.document(path(),int(args['page']))
    if name=='index_document':return f.index(path())
    if name=='search_knowledge':return f.search(args['query'])
    if name=='create_docx':backup(path());return f.make_docx(path(),args['title'],args['content'])
    if name=='ocr_image':
        r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(f.ROOT/'ocr.ps1'),'-ImagePath',str(path())],capture_output=True,timeout=45,creationflags=app.NO_WINDOW)
        if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-2000:])
        return json.loads(r.stdout.decode('utf-8-sig'))
    if name=='analyze_image':
        from PIL import Image
        import io
        with Image.open(path()) as im:
            im=im.convert('RGB');im.thumbnail((1024,1024));out=io.BytesIO();im.save(out,format='JPEG',quality=85)
        return {'description':app.vision('data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode())}
    if name=='render_pdf_page':
        import pymupdf
        output=path('output')
        if output.suffix.lower()!='.png':raise ValueError('Output must be PNG')
        backup(output);output.parent.mkdir(parents=True,exist_ok=True)
        with pymupdf.open(path()) as d:d[int(args['page'])-1].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(output)
        return {'saved':args['output']}
    if name=='apply_edit':
        old,new,diff=f.edit_patch(path(),args['old'],args['new']);backup(path());path().write_text(new,encoding='utf-8');return {'diff':diff}
    if name=='run_tests':return app.tool('run_command',{'command':args['command']})
    if name.startswith('browser_'):
        action=name[8:];a=dict(args)
        if action=='screenshot':backup(path());path().parent.mkdir(parents=True,exist_ok=True);a['path']=str(path())
        return f.browser(action,a)
    if name=='desktop_screenshot':backup(path());return f.screenshot(path())
    if name.startswith('desktop_'):return f.desktop(name[8:],args)
    if name=='speak':
        import pyttsx3
        engine=pyttsx3.init();engine.say(args['text'][:3000]);engine.runAndWait();return {'spoken':True}
    if name=='transcribe_audio':
        import wave
        from vosk import Model,KaldiRecognizer
        model=f.DATA/'vosk-model-small-cn-0.22'
        if not model.exists():raise RuntimeError('Install offline Vosk model using Setup-Extras.ps1')
        with wave.open(str(path()),'rb') as wav:
            if wav.getnchannels()!=1 or wav.getsampwidth()!=2:raise ValueError('Use mono PCM16 WAV')
            rec=KaldiRecognizer(Model(str(model)),wav.getframerate());parts=[]
            while True:
                raw=wav.readframes(4000)
                if not raw:break
                if rec.AcceptWaveform(raw):parts.append(json.loads(rec.Result())['text'])
            parts.append(json.loads(rec.FinalResult())['text'])
        return {'text':' '.join(parts)}
    raise ValueError('Unknown extension tool')
