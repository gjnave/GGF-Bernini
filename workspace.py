"""Durable, browser-scoped workspaces stored alongside private job files."""
import json
import re
import shutil
import threading
import uuid
from pathlib import Path
from config import ROOT

LOCK = threading.RLock()
BASE = ROOT / 'jobs' / 'workspaces'

def browser_secret():
    with LOCK:
        BASE.mkdir(parents=True, exist_ok=True)
        path = BASE / 'browser-secret.txt'
        if not path.exists():
            path.write_text(uuid.uuid4().hex, encoding='utf-8')
        return path.read_text(encoding='utf-8')

def valid_owner(owner):
    return isinstance(owner, str) and re.fullmatch(r'[0-9a-f]{32}', owner) is not None

def load(owner):
    if not valid_owner(owner):
        return {}
    with LOCK:
        path = BASE / owner / 'workspace.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

def save(owner, **updates):
    if not valid_owner(owner):
        raise ValueError('Invalid workspace identifier.')
    with LOCK:
        data = load(owner)
        data.update(updates)
        folder = BASE / owner
        folder.mkdir(parents=True, exist_ok=True)
        pending = folder / ('save-' + uuid.uuid4().hex + '.partial')
        pending.write_text(json.dumps(data), encoding='utf-8')
        pending.replace(folder / 'workspace.json')
        return data

def keep_file(owner, source):
    if not source:
        return None
    source = Path(source).resolve()
    if source.is_relative_to((ROOT / 'jobs').resolve()):
        return str(source)
    folder = BASE / owner / 'uploads'
    folder.mkdir(parents=True, exist_ok=True)
    # A content-independent cache key avoids reading a large video on every UI save.
    import hashlib
    stat = source.stat()
    key = hashlib.sha256(f'{source}:{stat.st_size}:{stat.st_mtime_ns}'.encode()).hexdigest()
    target = folder / (key + source.suffix)
    with LOCK:
        if not target.exists():
            shutil.copy2(source, target)
    return str(target)
