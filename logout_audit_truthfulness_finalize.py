from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'


def fail(message: str) -> None:
    raise SystemExit('LOGOUT_AUDIT_TRUTHFULNESS_FINALIZE_FAILED: ' + message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f'{label} reviewed anchor expected once, found {count}')
    return text.replace(old, new, 1)


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
text = ADAPTER.read_text(encoding='utf-8')
old_logout = """  vm.logout=async()=>{const old=vm.currentUser;if(old){vm.logAudit('退出系统',old.name||'');try{await flushSave();}catch(e){vm.notify(`云端保存失败，已取消退出：${e?.message||'保存失败'}`);return;}}try{if(token)await rpc('crm_logout',{p_token:SESSION_MARKER});}catch{}token='';revision=0;emptyState();vm.currentUser=null;vm.loginForm={username:'',password:''};vm.currentPage='dashboard';};"""
new_logout = """  vm.logout=async()=>{const old=vm.currentUser;if(old){const auditBefore=new Set(Array.isArray(vm.auditLogs)?vm.auditLogs:[]);vm.logAudit('退出系统',old.name||'');const logoutAuditRows=Array.isArray(vm.auditLogs)?vm.auditLogs.filter(row=>!auditBefore.has(row)):[];try{await flushSave();}catch(e){if(logoutAuditRows.length&&Array.isArray(vm.auditLogs)){const rollbackRows=new Set(logoutAuditRows);vm.auditLogs=vm.auditLogs.filter(row=>!rollbackRows.has(row));}vm.notify(`云端保存失败，已取消退出：${e?.message||'保存失败'}`);return;}}try{if(token)await rpc('crm_logout',{p_token:SESSION_MARKER});}catch{}token='';revision=0;emptyState();vm.currentUser=null;vm.loginForm={username:'',password:''};vm.currentPage='dashboard';};"""
text = replace_once(text, old_logout, new_logout, 'cancelled logout audit rollback')
ADAPTER.write_text(text, encoding='utf-8')
digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
print(
    'LOGOUT_AUDIT_TRUTHFULNESS_FINALIZE_OK: '
    'exit-audit=attempt-scoped-object-identity; '
    'save-failure=only-attempt-exit-audit-rolled-back; unrelated-live-audits=preserved; '
    'retry-success=single-real-exit-audit; persistence-barrier=preserved; '
    f'adapter={digest}'
)
