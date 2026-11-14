"""Download official CPU runtime and pinned model artifacts; never changes drivers."""
import hashlib,json,pathlib,shutil,urllib.request,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
AI=ROOT.parent/'local-ai'
ASSETS=[
 ('Qwen3-4B-Instruct-2507-Q4_K_M.gguf','unsloth/Qwen3-4B-Instruct-2507-GGUF','3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'),
 ('SmolVLM-500M-Instruct-Q8_0.gguf','ggml-org/SmolVLM-500M-Instruct-GGUF','9d4612de6a42214499e301494a3ecc2be0abdd9de44e663bda63f1152fad1bf4'),
 ('mmproj-SmolVLM-500M-Instruct-Q8_0.gguf','ggml-org/SmolVLM-500M-Instruct-GGUF','d1eb8b6b23979205fdf63703ed10f788131a3f812c7b1f72e0119d5d81295150')]
def download(url,dest,sha=None):
    if dest.exists() and (not sha or hashlib.file_digest(dest.open('rb'),'sha256').hexdigest()==sha):return
    temp=dest.with_suffix(dest.suffix+'.download');urllib.request.urlretrieve(url,temp)
    if sha and hashlib.file_digest(temp.open('rb'),'sha256').hexdigest()!=sha:raise ValueError('Hash mismatch: '+dest.name)
    temp.replace(dest)
def main():
    for folder in ('models','runtime','logs'):(AI/folder).mkdir(parents=True,exist_ok=True)
    runtime=AI/'runtime'/'llama.zip'
    download('https://github.com/ggml-org/llama.cpp/releases/download/b12359/llama-b12359-bin-win-cpu-x64.zip',runtime)
    with zipfile.ZipFile(runtime) as archive:archive.extractall(AI/'runtime')
    for name,repo,sha in ASSETS:download(f'https://huggingface.co/{repo}/resolve/main/{name}',AI/'models'/name,sha)
    for name in ('Start-LocalAI.ps1','Stop-LocalAI.ps1'):shutil.copy2(ROOT/'scripts'/name,AI/name)
    print('Models ready at',AI)
if __name__=='__main__':main()
