"""One owned GPU job at a time; each completed stage releases its process/VRAM."""
import json
import subprocess
import threading
import uuid
import time
import workspace
from pathlib import Path
from config import ROOT, settings

LOCK = threading.Lock()
ACTIVE = None

def stop_process_tree(process):
    """Windows venv redirectors spawn a child Python: stop only this owned tree."""
    import psutil
    try:
        parent=psutil.Process(process.pid)
        owned=parent.children(recursive=True)+[parent]
    except psutil.NoSuchProcess:
        return
    for item in reversed(owned):
        try: item.terminate()
        except psutil.NoSuchProcess: pass
    _,alive=psutil.wait_procs(owned,timeout=8)
    for item in alive:
        try: item.kill()
        except psutil.NoSuchProcess: pass

def job_directory():
    path = ROOT / 'jobs' / uuid.uuid4().hex
    path.mkdir(parents=True)
    return path

def cancel(owner):
    active = ACTIVE
    if active and active['owner'] == owner:
        active['cancelled'] = True
        stop_process_tree(active['process'])
        return 'Stopping your current job. Existing outputs are kept.'
    return 'No running job in this session.'

def generate(request, owner, progress):
    global ACTIVE
    if not LOCK.acquire(blocking=False):
        raise ValueError('Another generation is already running. Wait for it to finish.')
    process = None
    started = time.time()
    mode = request.get('mode','video')
    activity = dict(running=True,started=started,mode=mode,stage='Starting generation')
    updates = {'activity':activity}
    if mode == 'video':
        updates['output'] = None
    failure = None
    try:
        workspace.save(owner,**updates)
        job = job_directory()
        request = {**settings(), **request, 'job': str(job)}
        request_file = job/'request.json'
        request_file.write_text(json.dumps(request, indent=2), encoding='utf-8')
        with (job/'worker.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen([settings()['python'], '-u', str(ROOT/'worker.py'), str(request_file)],
                                       cwd=str(ROOT), stdout=subprocess.PIPE, stderr=log, text=True,
                                       encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
            ACTIVE = {'owner':owner, 'process':process, 'cancelled':False}
            result = None
            for line in process.stdout:
                if line.startswith('__GGF__'):
                    item = json.loads(line[len('__GGF__'):])
                    if 'progress' in item:
                        activity['stage'] = item['progress']
                        workspace.save(owner,activity=activity)
                        try:
                            progress(item['progress'])
                        except Exception:
                            # Browser disconnects must not interrupt an owned job.
                            pass
                    else:
                        result = item
            process.wait()
            if ACTIVE['cancelled']:
                raise ValueError('Generation cancelled. Existing results were kept.')
            if not result:
                raise RuntimeError(f'Inference stopped unexpectedly. Details: {job / "worker.log"}')
            if not result['ok']:
                raise RuntimeError(result['error'])
            (job/'result.json').write_text(json.dumps(result, indent=2))
            return result
    except Exception as error:
        failure = str(error)
        raise
    finally:
        if process is not None and process.poll() is None:
            stop_process_tree(process)
            process.wait(timeout=15)
        if process is not None and process.stdout is not None:
            process.stdout.close()
        try:
            activity.update(running=False,finished=time.time(),stage=failure or 'Generation complete',error=bool(failure))
            workspace.save(owner,activity=activity)
        finally:
            ACTIVE = None
            LOCK.release()
