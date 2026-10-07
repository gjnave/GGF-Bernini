"""Application-owned locations; optional local overrides are never released."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CORE=ROOT/'vendor'/'comfy_core'

def settings():
    value={'python':str(ROOT/'.venv'/'Scripts'/'python.exe'),'models':str(ROOT/'models'),'attention':'sdpa'}
    path=ROOT/'local_settings.json'
    if path.exists():
        value.update(json.loads(path.read_text(encoding='utf-8')))
    return value

def model_status():
    models=json.loads((ROOT/'model_manifest.json').read_text())['models']
    root=Path(settings()['models'])
    return '\n'.join(('Ready' if (root/m['dest']).is_file() and (root/m['dest']).stat().st_size==m['size'] else 'Missing/incomplete')+' · '+m['label'] for m in models)

def require_models():
    report=model_status()
    if 'Missing' in report:
        raise ValueError('Required models are missing or incomplete. Run INSTALL.bat to finish the model downloads.\n'+report)
