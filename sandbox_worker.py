"""Trusted WASI host. Guest Python receives no host environment or writable mounts."""
import json,pathlib,sys
import wasmtime

ROOT=pathlib.Path(__file__).resolve().parent
RUNTIME=ROOT/'runtime/python-wasi'

def engine():
    config=wasmtime.Config();config.consume_fuel=True
    return wasmtime.Engine(config)

def execute(body):
    runtime=engine()
    module=wasmtime.Module.from_file(runtime,str(RUNTIME/'python.wasm'))
    store=wasmtime.Store(runtime);store.set_fuel(2_000_000_000)
    store.set_limits(memory_size=256*1024*1024,table_elements=100000,instances=4,memories=2)
    wasi=wasmtime.WasiConfig();wasi.argv=['python','-I','-B','-c',body['code']]
    wasi.env=[]
    wasi.preopen_dir(str(RUNTIME),'/usr/local',fs_mutable=False)
    if body.get('inputs'):wasi.preopen_dir(body['inputs'],'/inputs',fs_mutable=False)
    chunks={'stdout':bytearray(),'stderr':bytearray()};truncated=False
    def capture(name):
        def write(data):
            nonlocal truncated
            remaining=max(0,65536-len(chunks[name]));chunks[name].extend(data[:remaining])
            if len(data)>remaining:truncated=True
            return len(data)
        return write
    wasi.stdout_custom=capture('stdout');wasi.stderr_custom=capture('stderr')
    store.set_wasi(wasi);linker=wasmtime.Linker(runtime);linker.define_wasi()
    code=0;failure=None
    try:linker.instantiate(store,module).exports(store)['_start'](store)
    except wasmtime.ExitTrap as error:code=error.code
    except wasmtime.Trap as error:code=1;failure=str(error).splitlines()[-1]
    return {'exit_code':code,**{k:v.decode('utf-8',errors='replace') for k,v in chunks.items()},'truncated':truncated,'runtime_error':failure,'isolation':'WASI','network':False,'filesystem':'read-only runtime and explicitly supplied input','memory_limit_mib':256}

if __name__=='__main__':
    try:print(json.dumps(execute(json.load(sys.stdin)),ensure_ascii=True))
    except Exception as error:print(json.dumps({'exit_code':1,'error':str(error),'isolation':'WASI'}))
