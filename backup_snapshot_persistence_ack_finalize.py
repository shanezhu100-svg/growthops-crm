from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'


def fail(message: str) -> None:
    raise SystemExit('BACKUP_SNAPSHOT_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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
    'let saveTimer=null;',
    'vm.createBackupSnapshot=',
    'vm.deleteBackupSnapshot=',
):
    if marker not in text:
        fail('required final adapter snapshot/save marker missing: ' + marker)

old_create = """  vm.createBackupSnapshot=(notifyUser=false)=>{
    const snap={id:vm.accountUid('backup'),name:`数据快照 ${vm.localDateKey()} ${new Date().toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}`,backupDate:vm.localDateKey(),createdAt:new Date().toISOString(),payload:sanitizedBackupPayload()};
    vm.backupSnapshots.unshift(snap);vm.backupSnapshots=vm.backupSnapshots.slice(0,5);vm.persist();vm.updateStorageUsage();
    if(notifyUser){vm.logAudit('创建数据快照',snap.name);vm.persist();vm.notify('已创建云端数据快照');}
    return snap;
  };"""
new_create = """  vm.createBackupSnapshot=(notifyUser=false)=>{
    const snap={id:vm.accountUid('backup'),name:`数据快照 ${vm.localDateKey()} ${new Date().toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}`,backupDate:vm.localDateKey(),createdAt:new Date().toISOString(),payload:sanitizedBackupPayload()};
    const beforeSnapshots=notifyUser&&Array.isArray(vm.backupSnapshots)?vm.backupSnapshots.slice():null;
    vm.backupSnapshots.unshift(snap);vm.backupSnapshots=vm.backupSnapshots.slice(0,5);vm.updateStorageUsage();
    if(!notifyUser){vm.persist();return snap;}
    const auditBefore=new Set(Array.isArray(vm.auditLogs)?vm.auditLogs:[]);
    vm.logAudit('创建数据快照',snap.name);
    const snapshotAuditRows=Array.isArray(vm.auditLogs)?vm.auditLogs.filter(row=>!auditBefore.has(row)):[];
    return (async()=>{
      try{await flushSave();vm.notify('已创建云端数据快照');return snap;}
      catch(e){
        clearTimeout(saveTimer);saveTimer=null;
        vm.backupSnapshots=beforeSnapshots||[];
        const rollbackRows=new Set(snapshotAuditRows);vm.auditLogs=Array.isArray(vm.auditLogs)?vm.auditLogs.filter(row=>!rollbackRows.has(row)):[];
        vm.updateStorageUsage();
        vm.notify(`快照创建失败，云端未变更：${e?.message||'保存失败'}`);
        return null;
      }
    })();
  };"""
text = replace_once(text, old_create, new_create, 'createBackupSnapshot acknowledged manual save')

old_delete = """  vm.deleteBackupSnapshot=(snap)=>{
    const resolve=()=>Array.isArray(vm.backupSnapshots)?vm.backupSnapshots.find(s=>String(s?.id)===String(snap?.id)):null;
    let target=resolve();
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以删除快照');return;}
    if(!target){vm.notify('快照状态已变化，请重新操作');return;}
    vm.askConfirm({title:'删除数据快照',message:`确定删除【${target.name}】吗？删除后无法通过该快照恢复历史数据。`,confirmText:'删除快照'},()=>{
      if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以删除快照');return;}
      target=resolve();
      if(!target){vm.notify('快照状态已变化，请重新操作');return;}
      vm.backupSnapshots=vm.backupSnapshots.filter(s=>String(s?.id)!==String(target.id));vm.logAudit('删除数据快照',target.name);vm.persist();vm.notify('云端快照已删除');
    });
  };"""
new_delete = """  vm.deleteBackupSnapshot=(snap)=>{
    const resolve=()=>Array.isArray(vm.backupSnapshots)?vm.backupSnapshots.find(s=>String(s?.id)===String(snap?.id)):null;
    let target=resolve();
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以删除快照');return;}
    if(!target){vm.notify('快照状态已变化，请重新操作');return;}
    vm.askConfirm({title:'删除数据快照',message:`确定删除【${target.name}】吗？删除后无法通过该快照恢复历史数据。`,confirmText:'删除快照'},async()=>{
      if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以删除快照');return;}
      target=resolve();
      if(!target){vm.notify('快照状态已变化，请重新操作');return;}
      const beforeSnapshots=Array.isArray(vm.backupSnapshots)?vm.backupSnapshots.slice():[];
      const auditBefore=new Set(Array.isArray(vm.auditLogs)?vm.auditLogs:[]);
      vm.backupSnapshots=vm.backupSnapshots.filter(s=>String(s?.id)!==String(target.id));
      vm.logAudit('删除数据快照',target.name);
      const snapshotAuditRows=Array.isArray(vm.auditLogs)?vm.auditLogs.filter(row=>!auditBefore.has(row)):[];
      try{await flushSave();vm.updateStorageUsage();vm.notify('云端快照已删除');}
      catch(e){
        clearTimeout(saveTimer);saveTimer=null;
        vm.backupSnapshots=beforeSnapshots;
        const rollbackRows=new Set(snapshotAuditRows);vm.auditLogs=Array.isArray(vm.auditLogs)?vm.auditLogs.filter(row=>!rollbackRows.has(row)):[];
        vm.updateStorageUsage();
        vm.notify(`快照删除失败，云端未变更：${e?.message||'保存失败'}`);
      }
    });
  };"""
text = replace_once(text, old_delete, new_delete, 'deleteBackupSnapshot acknowledged save')

ADAPTER.write_text(text, encoding='utf-8')
digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
print(
    'BACKUP_SNAPSHOT_PERSISTENCE_ACK_FINALIZE_OK: '
    'manual-create=single-flush+success-after-ack+snapshot+audit-rollback-on-failure; '
    'manual-delete=admin+live-id-recheck+single-flush+success-after-ack+snapshot+audit-rollback-on-failure; '
    'internal-protection-create=false-remains-debounced-for-restore-import-atomic-flush; '
    f'adapter={digest}'
)
