from pathlib import Path
import hashlib
import re

root = Path(__file__).resolve().parent
dist = root / 'dist'
adapter_path = dist / 'cloud-adapter.js'
security_path = dist / 'cloud-security-hotfix.js'
p1_path = dist / 'cloud-p1-overrides.js'


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Unexpected {label} count: {count}')
    return text.replace(old, new, 1)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


adapter = adapter_path.read_text(encoding='utf-8')
security = security_path.read_text(encoding='utf-8')
p1 = p1_path.read_text(encoding='utf-8')

# The browser keeps only a non-secret in-memory marker indicating that a cookie-backed
# session may exist. The real CRM bearer token is never readable by JavaScript.
adapter = replace_once(
    adapter,
    """  const SUPABASE_URL=window.__GROWTHOPS_SUPABASE_URL__||'';
  const API_KEY=window.__GROWTHOPS_SUPABASE_KEY__||'';
  const TOKEN_KEY='growthops_crm_token_v2';
  let token=localStorage.getItem(TOKEN_KEY)||'';""",
    """  const SESSION_MARKER='cookie';
  let token=SESSION_MARKER;""",
    'adapter browser token bootstrap',
)

old_rpc = """  async function rpc(name,body={}){
    const r=await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`,{method:'POST',headers:{apikey:API_KEY,'Content-Type':'application/json'},body:JSON.stringify(body)});
    let data=null;try{data=await r.json()}catch{}
    if(!r.ok)throw new Error(data?.message||data?.hint||`请求失败 ${r.status}`);
    return data;
  }"""
new_rpc = """  async function rpc(name,body={}){
    const r=await fetch('/api/crm',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({rpc:name,args:body})});
    let data=null;try{data=await r.json()}catch{}
    if(!r.ok)throw new Error(data?.message||`请求失败 ${r.status}`);
    return data;
  }"""
adapter = replace_once(adapter, old_rpc, new_rpc, 'same-origin CRM BFF rpc')

old_enter = """  async function enter(d){
    hydrating=true;
    try{
      token=d?.token||token;revision=Number(d?.revision||0);if(token)localStorage.setItem(TOKEN_KEY,token);
      applyState(d?.state||{});vm.currentUser=d?.user||null;await loadUsers();syncSelections();routeFromHash();
      vm.updateStorageUsage();
    }finally{
      hydrating=false;
    }
  }"""
new_enter = """  async function enter(d){
    hydrating=true;
    try{
      token=SESSION_MARKER;revision=Number(d?.revision||0);
      applyState(d?.state||{});vm.currentUser=d?.user||null;await loadUsers();syncSelections();routeFromHash();
      vm.updateStorageUsage();
    }finally{
      hydrating=false;
    }
  }"""
adapter = replace_once(adapter, old_enter, new_enter, 'cookie-backed cloud enter')

# cloud_save_queue_finalize.py runs earlier and upgrades logout to flushSave(). Keep
# that serialization intact while removing the browser bearer-token storage path.
old_logout = """  vm.logout=async()=>{const old=vm.currentUser;if(old){vm.logAudit('退出系统',old.name||'');try{await flushSave();}catch{}}try{if(token)await rpc('crm_logout',{p_token:token});}catch{}token='';revision=0;localStorage.removeItem(TOKEN_KEY);emptyState();vm.currentUser=null;vm.loginForm={username:'',password:''};vm.currentPage='dashboard';};"""
new_logout = """  vm.logout=async()=>{const old=vm.currentUser;if(old){vm.logAudit('退出系统',old.name||'');try{await flushSave();}catch{}}try{if(token)await rpc('crm_logout',{p_token:SESSION_MARKER});}catch{}token='';revision=0;emptyState();vm.currentUser=null;vm.loginForm={username:'',password:''};vm.currentPage='dashboard';};"""
adapter = replace_once(adapter, old_logout, new_logout, 'cookie-backed serialized logout')

old_boot = """    try{await rpc('crm_public_status');if(token){try{const d=await rpc('crm_load_state_v3',{p_token:token});await enter(d);return;}catch{token='';localStorage.removeItem(TOKEN_KEY);}}}
"""
new_boot = """    try{await rpc('crm_public_status');if(token){try{const d=await rpc('crm_load_state_v3',{p_token:SESSION_MARKER});await enter(d);return;}catch{token='';}}}
"""
adapter = replace_once(adapter, old_boot, new_boot, 'cookie-backed boot restore')

# Credential UI paths still need a truthy session guard, but the guard must no longer
# read the bearer token. The proxy replaces every p_token marker server-side.
security = replace_once(
    security,
    "  const TOKEN_KEY='growthops_crm_token_v2';\n",
    "  const SESSION_MARKER='cookie';\n",
    'credential session marker constant',
)
security, token_read_count = re.subn(
    r"localStorage\.getItem\(TOKEN_KEY\)\s*\|\|\s*''",
    "(vm.currentUser?SESSION_MARKER:'')",
    security,
)
if token_read_count < 3:
    raise SystemExit(f'Expected at least 3 credential token reads to migrate, got {token_read_count}')

# Conflict recovery also uses cloud.rpc. Convert any residual direct token lookup to
# the same non-secret marker while preserving its existing flow.
p1, p1_token_reads = re.subn(
    r"localStorage\.getItem\((?:'growthops_crm_token_v2'|\"growthops_crm_token_v2\")\)\s*\|\|\s*''",
    "(window.__growthOpsVm?.currentUser?'cookie':'')",
    p1,
)
p1 = re.sub(
    r"\n\s*const\s+TOKEN_KEY\s*=\s*['\"]growthops_crm_token_v2['\"];?",
    '',
    p1,
)

# Fail closed if the old bearer-token storage path survives in any of these shipped
# auth-bearing assets.
for name, text in (
    ('cloud-adapter.js', adapter),
    ('cloud-security-hotfix.js', security),
    ('cloud-p1-overrides.js', p1),
):
    for forbidden in (
        'growthops_crm_token_v2',
        'localStorage.getItem(TOKEN_KEY)',
        'localStorage.setItem(TOKEN_KEY',
        'localStorage.removeItem(TOKEN_KEY',
    ):
        if forbidden in text:
            raise SystemExit(f'HttpOnly session migration failed: {forbidden} survived in {name}')

if '/rest/v1/rpc/' in adapter or 'SUPABASE_URL' in adapter or 'API_KEY' in adapter:
    raise SystemExit('Direct Supabase RPC transport survived in final cloud adapter')
if "fetch('/api/crm'" not in adapter or "credentials:'same-origin'" not in adapter:
    raise SystemExit('Same-origin CRM BFF transport missing from final cloud adapter')
if "crm_reveal_client_secret_field_v4" not in security or "crm_unlock_credentials_v1" not in security:
    raise SystemExit('Credential v4 safety path was damaged by HttpOnly migration')

adapter_path.write_text(adapter, encoding='utf-8')
security_path.write_text(security, encoding='utf-8')
p1_path.write_text(p1, encoding='utf-8')

print(
    'HTTP_ONLY_SESSION_FINALIZE_OK: '
    f'adapter={sha(adapter_path)}; security={sha(security_path)}; p1={sha(p1_path)}; '
    f'credential_token_reads={token_read_count}; p1_token_reads={p1_token_reads}'
)
