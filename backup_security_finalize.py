from pathlib import Path
import hashlib

root = Path(__file__).resolve().parent
adapter_path = root / 'dist' / 'cloud-adapter.js'


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Unexpected {label} count: {count}')
    return text.replace(old, new, 1)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

adapter = adapter_path.read_text(encoding='utf-8')

old_backup = """  function sanitizedBackupPayload(){
    const p=vm.collectBackupPayload();
    delete p.authUsers;
    delete p.backupSnapshots;
    p.version='growth-ops-cloud-backup-v2';
    return JSON.parse(JSON.stringify(p));
  }"""

new_backup = """  const BACKUP_SECRET_KEYS=new Set([
    'password','loginpassword','login_password','passwd','pwd',
    'loginaccount','login_account',
    'fbloginaccount','fbloginpassword','tkloginaccount','tkloginpassword',
    'twofactor','two_factor','twofactorsecret','two_factor_secret','twofakey','two_fa_key',
    '2fa','2fakey','2fa_key','backupcodes','backup_codes','recoverycodes','recovery_codes',
    'totpsecret','totp_secret','secretkey','secret_key'
  ]);
  const isBackupSecretKey=key=>BACKUP_SECRET_KEYS.has(String(key||'').toLowerCase());
  function redactBackupSecrets(value){
    if(Array.isArray(value))return value.map(redactBackupSecrets);
    if(value&&typeof value==='object'){
      const out={};
      for(const [key,val] of Object.entries(value)){
        if(isBackupSecretKey(key))continue;
        out[key]=redactBackupSecrets(val);
      }
      return out;
    }
    return value;
  }
  function sanitizedBackupPayload(){
    const raw=vm.collectBackupPayload();
    const cloned=JSON.parse(JSON.stringify(raw&&typeof raw==='object'?raw:{}));
    const p=redactBackupSecrets(cloned);
    delete p.authUsers;
    delete p.backupSnapshots;
    p.version='growth-ops-cloud-backup-v4-redacted';
    p.redacted=true;
    p.redaction={version:'crm-secret-keys-v2',behavior:'credential keys removed recursively before backup export'};
    return p;
  }"""

adapter = replace_once(adapter, old_backup, new_backup, 'backup payload redaction helper')

old_import = """    const reader=new FileReader();reader.onload=()=>{try{const p=JSON.parse(String(reader.result||''));if(!Array.isArray(p.clients))throw new Error('无效备份文件');vm.askConfirm({title:'导入全量备份',message:'导入会覆盖当前业务数据；系统会先创建保护快照。服务器登录账号与权限不会被备份文件覆盖。',confirmText:'确认导入',tone:'warning'},()=>{try{vm.createBackupSnapshot(false);applyBusinessBackup(p);vm.logAudit('导入全量备份',file.name);vm.persist();vm.notify('备份已导入并同步云端');}catch(e){vm.notify(e?.message||'备份导入失败');}});}catch(e){vm.notify(e?.message||'无法读取备份文件');}};reader.readAsText(file,'utf-8');"""

new_import = """    const reader=new FileReader();reader.onload=()=>{try{const raw=JSON.parse(String(reader.result||'')),p=redactBackupSecrets(raw);if(!Array.isArray(p.clients))throw new Error('无效备份文件');vm.askConfirm({title:'导入全量备份',message:'导入会覆盖当前业务数据；系统会先创建保护快照。备份中的登录账号、密码、2FA、恢复码等敏感字段会被忽略，不会覆盖 Vault 凭证。服务器登录账号与权限也不会被备份文件覆盖。',confirmText:'确认导入',tone:'warning'},()=>{try{vm.createBackupSnapshot(false);applyBusinessBackup(p);vm.logAudit('导入脱敏全量备份',file.name);vm.persist();vm.notify('脱敏备份已导入并同步云端；Vault 凭证未由备份覆盖');}catch(e){vm.notify(e?.message||'备份导入失败');}});}catch(e){vm.notify(e?.message||'无法读取备份文件');}};reader.readAsText(file,'utf-8');"""

adapter = replace_once(adapter, old_import, new_import, 'backup import secret stripping')

old_download = """    a.href=url;a.download=`growth-ops-backup-${vm.localDateKey()}.json`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);vm.logAudit('导出全量备份',a.download);vm.persist();vm.notify('业务数据备份已导出');"""
new_download = """    a.href=url;a.download=`growth-ops-backup-redacted-${vm.localDateKey()}.json`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);vm.logAudit('导出脱敏全量备份',a.download);vm.persist();vm.notify('脱敏业务备份已导出；不包含登录账号、密码、2FA 或恢复码');"""
adapter = replace_once(adapter, old_download, new_download, 'redacted backup download labeling')

adapter_path.write_text(adapter, encoding='utf-8')
print(f'BACKUP_SECURITY_FINALIZE_OK: adapter={sha(adapter_path)}')
