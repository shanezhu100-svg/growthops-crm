from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
dist=root/'dist'
adapter_path=dist/'cloud-adapter.js'
adapter=adapter_path.read_text(encoding='utf-8')

def require(condition,message):
    if not condition: raise SystemExit(message)

for marker in (
    'function enqueueSave(notifyFailure=false)',
    'async function flushSave()',
    'saveChain=task.catch(()=>{});',
    'clearTimeout(saveTimer);saveTimer=null;',
    'saveTimer=setTimeout(()=>{saveTimer=null;enqueueSave(true);},180)',
    'try{await flushSave();}catch{}',
    'window.__growthOpsCloud={rpc,saveNow:flushSave,flushSave,loadUsers};',
):
    require(marker in adapter,f'cloud save queue marker missing: {marker}')
require('saveChain=saveChain.then(saveNow)' not in adapter,'legacy concurrent save queue remains')
require(adapter.count('async function flushSave()')==1,'flushSave duplicated')
require(adapter.count('function enqueueSave(notifyFailure=false)')==1,'enqueueSave duplicated')
print('CLOUD_SAVE_QUEUE_OUTPUT_TESTS_OK: adapter='+hashlib.sha256(adapter_path.read_bytes()).hexdigest())
