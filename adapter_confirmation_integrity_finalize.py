from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'


def fail(message: str) -> None:
    raise SystemExit('ADAPTER_CONFIRMATION_INTEGRITY_FINALIZE_FAILED: ' + message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f'{label} reviewed anchor expected once, found {count}')
    return text.replace(old, new, 1)


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
text = ADAPTER.read_text(encoding='utf-8')

old_delete_user = """  vm.deleteAuthUser=(user)=>{
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以删除用户');return;}
    if(!vm.canDeleteAuthUser(user)){vm.notify(String(user?.id)===String(vm.currentUser?.id)?'当前正在登录的账号不能删除':'系统至少需要保留一个启用状态的管理员账号');return;}
    vm.askConfirm({title:'删除系统用户',message:`确定删除用户【${user.name}】吗？删除后该账号将无法登录。`,confirmText:'确认删除'},async()=>{
      try{await rpc('crm_delete_user',{p_token:token,p_user_id:user.id});await loadUsers();vm.logAudit('删除系统用户',`${user.name} · ${vm.roleLabel(user.role)}`);vm.persist();vm.notify('用户已从服务器删除');}
      catch(e){vm.notify(e?.message||'用户删除失败');}
    });
  };"""
new_delete_user = """  vm.deleteAuthUser=(user)=>{
    const resolve=()=>Array.isArray(vm.authUsers)?vm.authUsers.find(u=>String(u?.id)===String(user?.id)):null;
    let target=resolve();
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以删除用户');return;}
    if(!target){vm.notify('用户状态已变化，请刷新后重试');return;}
    if(!vm.canDeleteAuthUser(target)){vm.notify(String(target?.id)===String(vm.currentUser?.id)?'当前正在登录的账号不能删除':'系统至少需要保留一个启用状态的管理员账号');return;}
    vm.askConfirm({title:'删除系统用户',message:`确定删除用户【${target.name}】吗？删除后该账号将无法登录。`,confirmText:'确认删除'},async()=>{
      if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以删除用户');return;}
      target=resolve();
      if(!target){vm.notify('用户状态已变化，请刷新后重试');return;}
      if(!vm.canDeleteAuthUser(target)){vm.notify(String(target?.id)===String(vm.currentUser?.id)?'当前正在登录的账号不能删除':'系统至少需要保留一个启用状态的管理员账号');return;}
      try{await rpc('crm_delete_user',{p_token:token,p_user_id:target.id});await loadUsers();vm.logAudit('删除系统用户',`${target.name} · ${vm.roleLabel(target.role)}`);vm.persist();vm.notify('用户已从服务器删除');}
      catch(e){vm.notify(e?.message||'用户删除失败');}
    });
  };"""
text = replace_once(text, old_delete_user, new_delete_user, 'deleteAuthUser')

old_delete_backup = """  vm.deleteBackupSnapshot=(snap)=>{
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以删除快照');return;}
    vm.askConfirm({title:'删除数据快照',message:`确定删除【${snap.name}】吗？删除后无法通过该快照恢复历史数据。`,confirmText:'删除快照'},()=>{vm.backupSnapshots=vm.backupSnapshots.filter(s=>String(s.id)!==String(snap.id));vm.logAudit('删除数据快照',snap.name);vm.persist();vm.notify('云端快照已删除');});
  };"""
new_delete_backup = """  vm.deleteBackupSnapshot=(snap)=>{
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
text = replace_once(text, old_delete_backup, new_delete_backup, 'deleteBackupSnapshot')

old_restore_backup = """  vm.restoreBackupSnapshot=(snap)=>{
    if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以恢复快照');return;}
    vm.askConfirm({title:'恢复数据快照',message:`确定恢复【${snap.name}】吗？当前业务数据会先自动创建保护快照。`,confirmText:'确认恢复',tone:'warning'},()=>{try{vm.createBackupSnapshot(false);applyBusinessBackup(snap.payload);vm.logAudit('恢复数据快照',snap.name);vm.persist();vm.notify('数据快照已恢复并同步云端');}catch(e){vm.notify(e?.message||'快照恢复失败');}});
  };"""
new_restore_backup = """  vm.restoreBackupSnapshot=(snap)=>{
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
text = replace_once(text, old_restore_backup, new_restore_backup, 'restoreBackupSnapshot')

old_import = """    const reader=new FileReader();reader.onload=()=>{try{const raw=JSON.parse(String(reader.result||'')),p=redactBackupSecrets(raw);if(!Array.isArray(p.clients))throw new Error('无效备份文件');vm.askConfirm({title:'导入全量备份',message:'导入会覆盖当前业务数据；系统会先创建保护快照。备份中的登录账号、密码、2FA、恢复码等敏感字段会被忽略，不会覆盖 Vault 凭证。服务器登录账号与权限也不会被备份文件覆盖。',confirmText:'确认导入',tone:'warning'},()=>{try{vm.createBackupSnapshot(false);applyBusinessBackup(p);vm.logAudit('导入脱敏全量备份',file.name);vm.persist();vm.notify('脱敏备份已导入并同步云端；Vault 凭证未由备份覆盖');}catch(e){vm.notify(e?.message||'备份导入失败');}});}catch(e){vm.notify(e?.message||'无法读取备份文件');}};reader.readAsText(file,'utf-8');"""
new_import = """    const reader=new FileReader();reader.onload=()=>{try{const raw=JSON.parse(String(reader.result||'')),p=redactBackupSecrets(raw);if(!Array.isArray(p.clients))throw new Error('无效备份文件');vm.askConfirm({title:'导入全量备份',message:'导入会覆盖当前业务数据；系统会先创建保护快照。备份中的登录账号、密码、2FA、恢复码等敏感字段会被忽略，不会覆盖 Vault 凭证。服务器登录账号与权限也不会被备份文件覆盖。',confirmText:'确认导入',tone:'warning'},()=>{if(vm.currentUser?.role!=='ADMIN'){vm.notify('只有管理员可以导入备份');return;}try{vm.createBackupSnapshot(false);applyBusinessBackup(p);vm.logAudit('导入脱敏全量备份',file.name);vm.persist();vm.notify('脱敏备份已导入并同步云端；Vault 凭证未由备份覆盖');}catch(e){vm.notify(e?.message||'备份导入失败');}});}catch(e){vm.notify(e?.message||'无法读取备份文件');}};reader.readAsText(file,'utf-8');"""
text = replace_once(text, old_import, new_import, 'importFullBackup confirmation callback')

ADAPTER.write_text(text, encoding='utf-8')
digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
print(
    'ADAPTER_CONFIRMATION_INTEGRITY_FINALIZE_OK: '
    'user-delete=admin+live-user+can-delete-recheck; '
    'backup-delete=admin+live-snapshot-recheck; '
    'backup-restore=admin+live-snapshot+live-payload; '
    'backup-import=admin-recheck-before-overwrite; '
    f'adapter={digest}'
)
