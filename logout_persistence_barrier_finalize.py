from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'


def fail(message: str) -> None:
    raise SystemExit('LOGOUT_PERSISTENCE_BARRIER_FINALIZE_FAILED: ' + message)


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
    "rpc('crm_logout'",
    'function emptyState()',
    'let revision=0;',
):
    if marker not in text:
        fail('required final adapter logout/save marker missing: ' + marker)

old_logout = """  vm.logout=async()=>{const old=vm.currentUser;if(old){vm.logAudit('退出系统',old.name||'');try{await flushSave();}catch{}}try{if(token)await rpc('crm_logout',{p_token:SESSION_MARKER});}catch{}token='';revision=0;emptyState();vm.currentUser=null;vm.loginForm={username:'',password:''};vm.currentPage='dashboard';};"""
new_logout = """  vm.logout=async()=>{const old=vm.currentUser;if(old){vm.logAudit('退出系统',old.name||'');try{await flushSave();}catch(e){vm.notify(`云端保存失败，已取消退出：${e?.message||'保存失败'}`);return;}}try{if(token)await rpc('crm_logout',{p_token:SESSION_MARKER});}catch{}token='';revision=0;emptyState();vm.currentUser=null;vm.loginForm={username:'',password:''};vm.currentPage='dashboard';};"""
text = replace_once(text, old_logout, new_logout, 'logout acknowledged persistence barrier')

ADAPTER.write_text(text, encoding='utf-8')
digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
print(
    'LOGOUT_PERSISTENCE_BARRIER_FINALIZE_OK: '
    'active-session=exit-audit+flush-before-server-logout; '
    'save-failure=logout-cancelled+session-preserved+business-state-preserved+user-notified; '
    'save-success=server-logout+local-clear-preserved; '
    f'adapter={digest}'
)
