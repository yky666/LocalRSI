"""Download a pinned CPython WASI runtime into LocalRSI/runtime only."""
import hashlib,io,pathlib,urllib.request,zipfile
URL='https://github.com/brettcannon/cpython-wasi-build/releases/download/v3.15.2/python-3.15.2-wasi_sdk-33.zip'
SHA256='b8a63559c56760bbdc310dedb74fd69d10bcbafae26b705bea0ad353ad256888'
ROOT=pathlib.Path(__file__).resolve().parents[1]/'runtime/python-wasi'

if __name__=='__main__':
    import wasmtime
    with urllib.request.urlopen(URL,timeout=120) as response:raw=response.read(100*1024*1024)
    if hashlib.sha256(raw).hexdigest()!=SHA256:raise RuntimeError('Runtime archive checksum mismatch')
    ROOT.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for member in archive.infolist():
            if ROOT.resolve() not in (ROOT/member.filename).resolve().parents:raise ValueError('Invalid archive path')
        archive.extractall(ROOT)
    print('Installed pinned WASI runtime; no host drivers or global settings changed')
