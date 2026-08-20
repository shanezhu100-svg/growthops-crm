from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security_path=root/'dist'/'cloud-security-hotfix.js'
security=security_path.read_text(encoding='utf-8')

# v5.1 keeps prefetch data in memory only. It never persists safe-summary data and
# never prefetches actual password/2FA values.
state_marker="  let credentialUiV5LastErrorAt=0;\n"
if security.count(state_marker)!=1:
    raise SystemExit(f'Unexpected v5 state marker count: {security.count(state_marker)}')
state_add=(
    state_marker+
    "  const credentialUiV51PrefetchCache=new Map();\n"
    "  let credentialUiV51PrefetchPromise=null;\n"
    "  let credentialUiV51PrefetchClientId='';\n"
)
security=security.replace(state_marker,state_add,1)

ensure_marker="  const ensureAccountSafeSummary=()=>{\n"
if security.count(ensure_marker)!=1:
    raise SystemExit(f'Unexpected v5 ensure marker count: {security.count(ensure_marker)}')
helpers=r'''  const credentialUiV51CandidateClientId=()=>{
    const role=String(vm.currentUser?.role||'');
    if(!['ADMIN','OPS'].includes(role))return '';
    const assetsId=vm.selectedAssetsClientId;
    const assetsValue=assetsId==null?'':String(assetsId);
    if(assetsValue&&assetsValue!=='0'&&assetsValue.toUpperCase()!=='ALL')return assetsValue;
    if(vm.currentPage==='client-detail'){
      const detailId=vm.selectedClientId??vm.selectedClient?.id;
      const detailValue=detailId==null?'':String(detailId);
      if(detailValue&&detailValue!=='0'&&detailValue.toUpperCase()!=='ALL')return detailValue;
    }
    return '';
  };
  const credentialUiV51Cached=clientId=>{
    const key=String(clientId||'');
    if(!key)return null;
    const cached=credentialUiV51PrefetchCache.get(key)||null;
    if(!cached)return null;
    if(Date.now()-Number(cached.savedAt||0)>60000){
      credentialUiV51PrefetchCache.delete(key);
      return null;
    }
    return cached;
  };
  const credentialUiV51Remember=(clientId,data)=>{
    const key=String(clientId||'');
    if(!key||!data||typeof data!=='object')return;
    credentialUiV51PrefetchCache.set(key,{savedAt:Date.now(),data});
  };
  const credentialUiV51Prefetch=()=>{
    if(isCredentialSummaryContext())return;
    const clientId=credentialUiV51CandidateClientId();
    if(!clientId||credentialUiV51Cached(clientId))return;
    if(credentialUiV51PrefetchPromise&&credentialUiV51PrefetchClientId===clientId)return;
    const token=localStorage.getItem(TOKEN_KEY)||'';
    if(!token)return;
    credentialUiV51PrefetchClientId=clientId;
    const request=cloud.rpc('crm_client_account_safe_summary',{p_token:token,p_client_id:String(clientId)});
    credentialUiV51PrefetchPromise=request;
    request.then(data=>{
      if(data&&typeof data==='object')credentialUiV51Remember(clientId,data);
    }).catch(()=>{}).finally(()=>{
      if(credentialUiV51PrefetchPromise===request){
        credentialUiV51PrefetchPromise=null;
        credentialUiV51PrefetchClientId='';
      }
    });
  };
  const credentialUiV51ClearPrefetch=()=>{
    credentialUiV51PrefetchCache.clear();
    credentialUiV51PrefetchPromise=null;
    credentialUiV51PrefetchClientId='';
  };

'''
security=security.replace(ensure_marker,helpers+ensure_marker,1)

# Patch only the v5 ensure block.
ensure_start=security.find(ensure_marker)
ensure_end=security.find("  const assetClientForProtectedField=()=>",ensure_start)
if ensure_start<0 or ensure_end<0:
    raise SystemExit('Unable to bound v5 ensure block')
ensure_block=security[ensure_start:ensure_end]

non_context_old="""      }
      return;
    }
    const role=String(vm.currentUser?.role||'');
"""
non_context_new="""      }
      credentialUiV51Prefetch();
      return;
    }
    const role=String(vm.currentUser?.role||'');
"""
if ensure_block.count(non_context_old)!=1:
    raise SystemExit(f'Unexpected v5 non-context return count: {ensure_block.count(non_context_old)}')
ensure_block=ensure_block.replace(non_context_old,non_context_new,1)

client_marker="""    const clientId=resolveCredentialClientId();
    if(!['ADMIN','OPS'].includes(role)||!clientId){
"""
hydrate="""    const clientId=resolveCredentialClientId();
    const prefetched=credentialUiV51Cached(clientId);
    if(prefetched&&(!accountSafeSummaryData||accountSafeSummaryClientId!==clientId)){
      accountSafeSummaryClientId=clientId;
      accountSafeSummaryData=prefetched.data;
      accountSafeSummaryFetchedAt=Number(prefetched.savedAt||Date.now());
    }
    if(!['ADMIN','OPS'].includes(role)||!clientId){
"""
if ensure_block.count(client_marker)!=1:
    raise SystemExit(f'Unexpected v5 client marker count: {ensure_block.count(client_marker)}')
ensure_block=ensure_block.replace(client_marker,hydrate,1)

success_marker="""      accountSafeSummaryData=data&&typeof data==='object'?data:{};
      accountSafeSummaryFetchedAt=Date.now();
      credentialUiV5LastErrorAt=0;
"""
success_new="""      accountSafeSummaryData=data&&typeof data==='object'?data:{};
      accountSafeSummaryFetchedAt=Date.now();
      credentialUiV51Remember(clientId,accountSafeSummaryData);
      credentialUiV5LastErrorAt=0;
"""
if ensure_block.count(success_marker)!=1:
    raise SystemExit(f'Unexpected v5 success marker count: {ensure_block.count(success_marker)}')
ensure_block=ensure_block.replace(success_marker,success_new,1)
security=security[:ensure_start]+ensure_block+security[ensure_end:]

# Backgrounding or leaving the page clears the memory-only prefetch cache.
visibility_marker="  document.addEventListener('visibilitychange',()=>{\n"
if security.count(visibility_marker)!=1:
    raise SystemExit(f'Unexpected visibility marker count: {security.count(visibility_marker)}')
security=security.replace(
    visibility_marker,
    "  document.addEventListener('visibilitychange',()=>{\n    if(document.hidden)credentialUiV51ClearPrefetch();\n",
    1,
)
beforeunload_marker="  window.addEventListener('beforeunload',clearCredentialUnlock);\n"
if security.count(beforeunload_marker)!=1:
    raise SystemExit(f'Unexpected beforeunload unlock marker count: {security.count(beforeunload_marker)}')
security=security.replace(
    beforeunload_marker,
    beforeunload_marker+"  window.addEventListener('beforeunload',credentialUiV51ClearPrefetch);\n  window.addEventListener('pagehide',credentialUiV51ClearPrefetch);\n",
    1,
)

# Upgrade diagnostics only; do not expose cached data.
version_old="    version:'5.0',\n"
if security.count(version_old)!=1:
    raise SystemExit(f'Unexpected v5 diagnostic version count: {security.count(version_old)}')
security=security.replace(version_old,"    version:'5.1',\n",1)
refresh_old="    refresh:()=>{accountSafeSummaryFetchedAt=0;credentialUiV5LastErrorAt=0;ensureAccountSafeSummary();}\n"
refresh_new="    prefetch:()=>credentialUiV51Prefetch(),\n    refresh:()=>{accountSafeSummaryFetchedAt=0;credentialUiV5LastErrorAt=0;ensureAccountSafeSummary();}\n"
if security.count(refresh_old)!=1:
    raise SystemExit(f'Unexpected v5 refresh marker count: {security.count(refresh_old)}')
security=security.replace(refresh_old,refresh_new,1)

security_path.write_text(security,encoding='utf-8')
print('CREDENTIAL_UI_V51_PREFETCH_FINALIZE_OK: security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
