"""Pinned, resumable, verified downloads. Existing complete files are retained."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
from pathlib import Path
from config import ROOT,settings

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(16*1024*1024),b''): h.update(block)
    return h.hexdigest()

def fetch(model,root,reuse):
    target=root/model['dest']
    target.parent.mkdir(parents=True,exist_ok=True)
    receipt=target.with_suffix('.verified.json')
    if target.exists() and target.stat().st_size==model['size']:
        if receipt.exists() and json.loads(receipt.read_text()).get('mtime_ns')==target.stat().st_mtime_ns:
            print('Ready: '+model['label'],flush=True)
            return
        if digest(target)!=model['sha256']:
            raise ValueError('Existing file has wrong hash; preserved for inspection: '+str(target))
    else:
        if target.exists():
            raise ValueError('Existing incomplete final file preserved: '+str(target))
        existing=next((p/Path(model['dest']) for p in reuse if (p/Path(model['dest'])).is_file() and (p/Path(model['dest'])).stat().st_size==model['size']),None)
        if existing and digest(existing)==model['sha256']:
            try: os.link(existing,target)
            except OSError:
                import shutil
                shutil.copy2(existing,target)
            print('Reused: '+model['label'],flush=True)
        else:
            partial=target.with_suffix('.safetensors.part')
            url=f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{model['file']}"
            print('Downloading: '+model['label'],flush=True)
            subprocess.run(['curl.exe','-fL','--retry','5','--retry-delay','3','--connect-timeout','30','-C','-','-o',str(partial),url],check=True)
            if partial.stat().st_size!=model['size'] or digest(partial)!=model['sha256']:
                raise ValueError('Download failed size/hash verification; partial retained: '+str(partial))
            partial.rename(target)
    receipt.write_text(json.dumps({'sha256':model['sha256'],'mtime_ns':target.stat().st_mtime_ns}))
    print('Verified: '+model['label'],flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',default=settings()['models'])
    parser.add_argument('--reuse',action='append',default=[])
    parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args()
    models=json.loads((ROOT/'model_manifest.json').read_text())['models']
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,args.workers)) as pool:
        jobs=[pool.submit(fetch,m,Path(args.root),[Path(p) for p in args.reuse]) for m in models]
        for job in jobs: job.result()
    print('All model files verified.',flush=True)
