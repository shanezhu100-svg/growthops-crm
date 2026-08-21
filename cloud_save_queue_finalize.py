from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
dist=root/'dist'
adapter_path=dist/'cloud-adapter.js'
if not adapter_path.exists(): raise SystemExit('dist/cloud-adapter.js missing')
adapter=adapter_path.read_text(encoding='utf-8')

def replace_once(text,old,new,label):
    count=text.count(old)
    if count!=1: raise SystemExit(f'Unexpected {label} count: {count}')
    return text.replace(old,new,1)

old_persist="""  vm.persist=()=>{if(hydrating||suppressPersist)return true;clearTimeout(saveTimer);saveTimer=setTimeout(()=>{saveChain=saveChain.then(saveNow).catch(e=>{console.error(e);vm.notify(`云端保存失败：${e.message}`);});},180);return true;};"""
new_persist="""  function enqueueSave(notifyFailure=false){
    const task=saveChain.then(()=>saveNow());
    saveChain=task.catch(()=>{});
    if(notifyFailure)task.catch(e=>{console.error(e);vm.notify(`云端保存失败：${e.message}`);});
    return task;
  }
  async function flushSave(){
    if(hydrating||suppressPersist)return true;
    clearTimeout(saveTimer);saveTimer=null;
    return enqueueSave(false);
  }
  vm.persist=()=>{if(hydrating||suppressPersist)return true;clearTimeout(saveTimer);saveTimer=setTimeout(()=>{saveTimer=null;enqueueSave(true);},180);return true;};"""
adapter=replace_once(adapter,old_persist,new_persist,'serialized persist replacement')
adapter=replace_once(adapter,"try{await saveNow();}catch{}","try{await flushSave();}catch{}",'logout serialized flush')
adapter=replace_once(adapter,"window.__growthOpsCloud={rpc,saveNow,loadUsers};","window.__growthOpsCloud={rpc,saveNow:flushSave,flushSave,loadUsers};",'public serialized save API')
adapter_path.write_text(adapter,encoding='utf-8')
print('CLOUD_SAVE_QUEUE_FINALIZE_OK: adapter='+hashlib.sha256(adapter_path.read_bytes()).hexdigest())
