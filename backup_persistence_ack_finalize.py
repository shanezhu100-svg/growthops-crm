from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'


def fail(message: str) -> None:
    raise SystemExit('BACKUP_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f'{label} reviewed anchor expected once, found {count}')
    return text.replace(old, new, 1)


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
text = ADAPTER.read_text(encoding='utf-8')
for marker in (
    'async function flushSave()',
    'function payload()',
    'function applyState(p)',
    'let hydrating=false;',
    'let saveTimer=null;',
):
    if marker not in text:
        fail('required final adapter save/rollback marker missing: ' + marker)

old_restore = """  vm.restoreBackupSnapshot=(snap)=>{
    const resolve=()=>Array.isArray(vm.backupSnapshots)?vm.backupSnapshots.find(s=>String(s?.id)===String(snap?.id)):null;
    let target=resolve();
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以恢复快照');return;}
    if(!target){vm.notify('快照状态已变化，请重新操作');return;}
    vm.askConfirm({title:'恢复数据快照',message:`确定恢复【${target.name}】吗？当前业务数据会先自动创建保护快照。`,confirmText:'确认恢复',tone:'warning'},()=>{
      if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以恢复快照');return;}
      target=resolve();
      if(!target){vm.notify('快照状态已变化，请重新操作');return;}
      try{vm.createBackupSnapshot(false);applyBusinessBackup(target.payload);vm.logAudit('恢复数据快照',target.name);vm.persist();vm.notify('数据快照已恢复并同步云端');}catch(e){vm.notify(e?.message||'快照恢复失败');}
    });
  };"""
new_restore = """  function rollbackFailedBusinessOverwrite(before){
    clearTimeout(saveTimer);saveTimer=null;
    hydrating=true;
    try{applyState(before);syncSelections();routeFromHash();vm.updateStorageUsage();}
    finally{hydrating=false;}
  }
  vm.restoreBackupSnapshot=(snap)=>{
    const resolve=()=>Array.isArray(vm.backupSnapshots)?vm.backupSnapshots.find(s=>String(s?.id)===String(snap?.id)):null;
    let target=resolve();
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以恢复快照');return;}
    if(!target){vm.notify('快照状态已变化，请重新操作');return;}
    vm.askConfirm({title:'恢复数据快照',message:`确定恢复【${target.name}】吗？当前业务数据会先自动创建保护快照。`,confirmText:'确认恢复',tone:'warning'},async()=>{
      if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以恢复快照');return;}
      target=resolve();
      if(!target){vm.notify('快照状态已变化，请重新操作');return;}
      const before=payload();
      try{
        vm.createBackupSnapshot(false);
        applyBusinessBackup(target.payload);
        vm.logAudit('恢复数据快照',target.name);
        await flushSave();
        vm.notify('数据快照已恢复并同步云端');
      }catch(e){
        rollbackFailedBusinessOverwrite(before);
        vm.notify(`快照恢复失败，云端未变更：${e?.message||'保存失败'}`);
      }
    });
  };"""
text = replace_once(text, old_restore, new_restore, 'restoreBackupSnapshot acknowledged save')

old_import = """    const reader=new FileReader();reader.onload=()=>{try{const raw=JSON.parse(String(reader.result||'')),p=redactBackupSecrets(raw);if(!Array.isArray(p.clients))throw new Error('无效备份文件');vm.askConfirm({title:'导入全量备份',message:'导入会覆盖当前业务数据；系统会先创建保护快照。备份中的登录账号、密码、2FA、恢复码等敏感字段会被忽略，不会覆盖 Vault 凭证。服务器登录账号与权限也不会被备份文件覆盖。',confirmText:'确认导入',tone:'warning'},()=>{if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以导入备份');return;}try{vm.createBackupSnapshot(false);applyBusinessBackup(p);vm.logAudit('导入脱敏全量备份',file.name);vm.persist();vm.notify('脱敏备份已导入并同步云端；Vault 凭证未由备份覆盖');}catch(e){vm.notify(e?.message||'备份导入失败');}});}catch(e){vm.notify(e?.message||'无法读取备份文件');}};reader.readAsText(file,'utf-8');"""
new_import = """    const reader=new FileReader();reader.onload=()=>{try{const raw=JSON.parse(String(reader.result||'')),p=redactBackupSecrets(raw);if(!Array.isArray(p.clients))throw new Error('无效备份文件');vm.askConfirm({title:'导入全量备份',message:'导入会覆盖当前业务数据；系统会先创建保护快照。备份中的登录账号、密码、2FA、恢复码等敏感字段会被忽略，不会覆盖 Vault 凭证。服务器登录账号与权限也不会被备份文件覆盖。',confirmText:'确认导入',tone:'warning'},async()=>{if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以导入备份');return;}const before=payload();try{vm.createBackupSnapshot(false);applyBusinessBackup(p);vm.logAudit('导入脱敏全量备份',file.name);await flushSave();vm.notify('脱敏备份已导入并同步云端；Vault 凭证未由备份覆盖');}catch(e){rollbackFailedBusinessOverwrite(before);vm.notify(`备份导入失败，云端未变更：${e?.message||'保存失败'}`);}});}catch(e){vm.notify(e?.message||'无法读取备份文件');}};reader.readAsText(file,'utf-8');"""
text = replace_once(text, old_import, new_import, 'importFullBackup acknowledged save')

ADAPTER.write_text(text, encoding='utf-8')
digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
print(
    'BACKUP_PERSISTENCE_ACK_FINALIZE_OK: '
    'restore=single-final-flush+success-after-ack+rollback-on-failure; '
    'import=single-final-flush+success-after-ack+rollback-on-failure; '
    'protection-snapshot=atomic-with-final-state; failed-overwrite=local-prestate-restored; '
    f'adapter={digest}'
)
