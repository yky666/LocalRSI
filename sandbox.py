"""Run Python standard-library calculations in WASI, never native eval/exec."""
import json,os,pathlib,subprocess,sys,tempfile,threading

ROOT=pathlib.Path(__file__).resolve().parent
GATE=threading.BoundedSemaphore(1)

def available():
    return (ROOT/'runtime/python-wasi/python.wasm').is_file()

def run(code,input_path=None):
    if not isinstance(code,str) or not 1<=len(code)<=24000:raise ValueError('Python code must contain 1–24000 characters')
    if not available():raise RuntimeError('WASI runtime is not installed; native fallback is disabled')
    if not GATE.acquire(blocking=False):raise RuntimeError('Sandbox busy; retry after the current execution')
    try:
        with tempfile.TemporaryDirectory(prefix='localrsi-wasi-') as directory:
            folder=pathlib.Path(directory)
            if input_path:
                source=pathlib.Path(input_path)
                if not source.is_file() or source.stat().st_size>5*1024*1024:raise ValueError('Input must be a file under 5MB')
                (folder/'input').write_bytes(source.read_bytes())
            env={k:os.environ[k] for k in ('SYSTEMROOT','WINDIR','TEMP','TMP') if k in os.environ}
            result=subprocess.run([sys.executable,'-I',str(ROOT/'sandbox_worker.py')],input=json.dumps({'code':code,'inputs':directory if input_path else None}),capture_output=True,text=True,encoding='utf-8',env=env,cwd=ROOT,timeout=45,creationflags=0x08000000 if os.name=='nt' else 0)
            if result.returncode:raise RuntimeError('WASI host exited unexpectedly; no native fallback')
            return json.loads(result.stdout)
    except subprocess.TimeoutExpired:return {'exit_code':124,'error':'Sandbox exceeded 45 second wall-clock budget; worker terminated','isolation':'WASI'}
    finally:GATE.release()
