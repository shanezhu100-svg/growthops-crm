from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
security_path=root/'dist'/'cloud-security-hotfix.js'
html=index_path.read_text(encoding='utf-8')
security=security_path.read_text(encoding='utf-8')

# Consolidated controller stage: historical v5 renderer + v5.1 memory-only prefetch.
preboot=r'''<script id="growthops-credential-ui-v5-preboot">(()=>{
  'use strict';
  const ATTR='data-growthops-credential-v5-state';
  const LABELS=new Set(['登录账号','登录邮箱','登录邮箱 / 手机号','密码 / 2FA']);
  const clean=value=>String(value?.textContent||'').replace(/\s+/g,' ').trim();
  const inCredentialCard=label=>{
    let node=label?.parentElement||null;
    for(let i=0;node&&i<9;i++,node=node.parentElement){
      const value=clean(node).toLowerCase();
      const platform=value.includes('facebook')||value.includes('tiktok')||value.includes('google')||value.includes('instagram');
      if(platform&&value.includes('密码 / 2fa'))return true;
    }
    return false;
  };
  const valueCell=label=>{
    const row=label?.parentElement;
    if(!row)return null;
    const cells=[...row.children].filter(el=>el!==label);
    return cells.length?cells[cells.length-1]:null;
  };
  const scrub=()=>{
    const body=document.body;
    if(!body)return;
    for(const label of body.querySelectorAll('*')){
      if(label.children.length!==0||!LABELS.has(clean(label))||!inCredentialCard(label))continue;
      const cell=valueCell(label);
      if(!cell)continue;
      const state=cell.getAttribute(ATTR)||'';
      if(state==='ready'||state==='error'||state==='revealed')continue;
      if(cell.textContent)cell.textContent='';
      cell.setAttribute(ATTR,'preboot');
    }
  };
  let queued=false;
  const schedule=()=>{
    if(queued)return;
    queued=true;
    queueMicrotask(()=>{queued=false;scrub();});
  };
  const observer=new MutationObserver(schedule);
  observer.observe(document.documentElement,{childList:true,subtree:true,characterData:true});
  schedule();
  window.__GROWTHOPS_CREDENTIAL_V5_PREBOOT__={scrub};
})();</script>'''
if 'growthops-credential-ui-v5-preboot' in html:
    raise SystemExit('Credential UI v5 preboot already present before finalizer')
if html.count('</head>')!=1:
    raise SystemExit('Unexpected HTML head ending')
html=html.replace('</head>',preboot+'</head>',1)
html=html.replace('读取中…','')

state_marker="  let accountSafeSummaryFetchedAt=0;\n"
if security.count(state_marker)!=1:
    raise SystemExit(f'Unexpected safe-summary state marker count: {security.count(state_marker)}')
security=security.replace(
    state_marker,
    state_marker+
    "  let credentialUiV5RequestSeq=0;\n"
    "  let credentialUiV5ClientId='';\n"
    "  let credentialUiV5State='idle';\n"
    "  let credentialUiV5LastErrorAt=0;\n",
    1,
)

apply_start=security.find("  const applyAccountSafeSummaryToCards=()=>{")
apply_end=security.find("  const markAccountSafeSummaryUnavailable=()=>{",apply_start)
if apply_start<0 or apply_end<0:
    raise SystemExit('Unable to locate safe-summary renderer block')
v5_renderer=r'''  const credentialUiV5ResetCell=cell=>{
    if(!cell)return;
    try{if(typeof cell.__growthOpsVaultFieldClear==='function')cell.__growthOpsVaultFieldClear();}catch{}
    delete cell.__growthOpsVaultFieldClear;
    if(cell.dataset)delete cell.dataset.growthopsVaultPrevious;
    cell.removeAttribute(INLINE_ATTR);
    cell.removeAttribute(FIELD_REVEAL_ATTR);
    cell.removeAttribute(LOGIN_IDENTIFIER_ATTR);
    cell.removeAttribute(STATUS_ATTR);
    cell.removeAttribute('data-growthops-vault-kind');
    cell.removeAttribute('title');
    cell.textContent='';
  };
  const credentialUiV5Blank=clientId=>{
    credentialUiV5State='loading';
    credentialUiV5ClientId=String(clientId||'');
    for(const row of locateCredentialRows()){
      for(const cell of [row.accountCell,row.passwordCell]){
        if(!cell)continue;
        credentialUiV5ResetCell(cell);
        matchCredentialValueTypography(cell);
        cell.setAttribute('data-growthops-credential-v5-state','loading');
      }
    }
  };
  const credentialUiV5DomReady=()=>{
    const rows=locateCredentialRows();
    if(!rows.length)return false;
    return rows.every(row=>[row.accountCell,row.passwordCell].filter(Boolean).every(cell=>{
      const state=cell.getAttribute('data-growthops-credential-v5-state');
      return state==='ready'||state==='error'||state==='revealed';
    }));
  };
  const credentialUiV5Render=()=>{
    if(!isCredentialSummaryContext()||!accountSafeSummaryData)return;
    const clientId=resolveCredentialClientId();
    if(!clientId||clientId!==accountSafeSummaryClientId)return;
    credentialUiV5State='ready';
    credentialUiV5ClientId=clientId;
    normalizeOtherAccountAssetTypography();
    for(const row of locateCredentialRows()){
      const summary=summaryForCredentialRow(row)||{};
      if(row.accountCell){
        credentialUiV5ResetCell(row.accountCell);
        matchCredentialValueTypography(row.accountCell);
        const login=String(summary.loginAccount||'').trim();
        row.accountCell.textContent=login||'未录入';
        row.accountCell.setAttribute(LOGIN_IDENTIFIER_ATTR,'summary');
        row.accountCell.setAttribute(STATUS_ATTR,'summary');
        row.accountCell.setAttribute('data-growthops-credential-v5-state','ready');
        row.accountCell.title=login?'登录账号由受控 Vault 摘要接口读取；不包含密码':'Vault 中未检测到登录账号';
      }
      if(row.passwordCell){
        const recorded=Boolean(summary.hasPassword||summary.has2FA);
        if(recorded&&vm.currentUser?.role==='ADMIN'&&row.passwordCell.getAttribute(FIELD_REVEAL_ATTR)==='1'){
          row.passwordCell.setAttribute('data-growthops-credential-v5-state','ready');
          continue;
        }
        credentialUiV5ResetCell(row.passwordCell);
        matchCredentialValueTypography(row.passwordCell);
        if(!recorded){
          row.passwordCell.textContent='未录入';
          row.passwordCell.setAttribute(STATUS_ATTR,'0');
          row.passwordCell.setAttribute('data-growthops-credential-v5-state','ready');
          row.passwordCell.title='Vault 中未检测到密码或 2FA';
          continue;
        }
        row.passwordCell.textContent='••••••••';
        row.passwordCell.setAttribute(STATUS_ATTR,'1');
        row.passwordCell.setAttribute('data-growthops-credential-v5-state','ready');
        if(vm.currentUser?.role==='ADMIN'){
          row.passwordCell.title='密码 / 2FA 已安全保存在 Vault；点击眼睛短暂查看';
          installProtectedFieldControl(row,summary);
          row.passwordCell.setAttribute('data-growthops-credential-v5-state','ready');
        }else{
          row.passwordCell.title='密码 / 2FA 已安全保存在 Vault；仅管理员可查看';
        }
      }
    }
  };
  const credentialUiV5Error=()=>{
    credentialUiV5State='error';
    credentialUiV5LastErrorAt=Date.now();
    for(const row of locateCredentialRows()){
      for(const cell of [row.accountCell,row.passwordCell]){
        if(!cell)continue;
        credentialUiV5ResetCell(cell);
        matchCredentialValueTypography(cell);
        cell.textContent='状态暂不可用';
        cell.setAttribute('data-growthops-credential-v5-state','error');
        cell.title='凭证摘要读取失败；系统会自动重试';
      }
    }
  };
  const applyAccountSafeSummaryToCards=credentialUiV5Render;
'''
security=security[:apply_start]+v5_renderer+security[apply_end:]

err_start=security.find("  const markAccountSafeSummaryUnavailable=()=>{")
err_end=security.find("  const clearAccountSafeSummary=()=>{",err_start)
if err_start<0 or err_end<0:
    raise SystemExit('Unable to locate safe-summary error renderer')
security=security[:err_start]+"  const markAccountSafeSummaryUnavailable=credentialUiV5Error;\n"+security[err_end:]

ensure_start=security.find("  const ensureAccountSafeSummary=()=>{")
ensure_end=security.find("  const assetClientForProtectedField=()=>",ensure_start)
if ensure_start<0 or ensure_end<0:
    raise SystemExit('Unable to locate safe-summary orchestration block')
v5_ensure=r'''  const ensureAccountSafeSummary=()=>{
    if(!isCredentialSummaryContext()){
      if(credentialUiV5ClientId||accountSafeSummaryClientId||accountSafeSummaryData){
        credentialUiV5RequestSeq+=1;
        credentialUiV5ClientId='';
        credentialUiV5State='idle';
        clearAccountSafeSummary();
      }
      return;
    }
    const role=String(vm.currentUser?.role||'');
    const clientId=resolveCredentialClientId();
    if(!['ADMIN','OPS'].includes(role)||!clientId){
      credentialUiV5RequestSeq+=1;
      accountSafeSummaryClientId='';
      accountSafeSummaryData=null;
      accountSafeSummaryFetchedAt=0;
      credentialUiV5Blank('');
      credentialUiV5State='idle';
      return;
    }
    const now=Date.now();
    const fresh=accountSafeSummaryData&&accountSafeSummaryClientId===clientId&&now-accountSafeSummaryFetchedAt<60000;
    if(fresh){
      if(!credentialUiV5DomReady())credentialUiV5Render();
      return;
    }
    if(credentialUiV5State==='error'&&credentialUiV5ClientId===clientId&&now-credentialUiV5LastErrorAt<10000)return;
    if(accountSafeSummaryPromise&&accountSafeSummaryClientId===clientId)return;
    const token=localStorage.getItem(TOKEN_KEY)||'';
    if(!token){
      accountSafeSummaryData=null;
      accountSafeSummaryFetchedAt=0;
      credentialUiV5Blank(clientId);
      credentialUiV5State='error';
      return;
    }
    const changed=accountSafeSummaryClientId!==clientId;
    if(changed){
      accountSafeSummaryData=null;
      accountSafeSummaryFetchedAt=0;
      accountSafeSummaryClientId=clientId;
      credentialUiV5Blank(clientId);
    }
    credentialUiV5ClientId=clientId;
    credentialUiV5State='loading';
    const requestId=++credentialUiV5RequestSeq;
    const request=cloud.rpc('crm_client_account_safe_summary',{p_token:token,p_client_id:String(clientId)});
    accountSafeSummaryPromise=request;
    request.then(data=>{
      if(requestId!==credentialUiV5RequestSeq||resolveCredentialClientId()!==clientId)return;
      accountSafeSummaryData=data&&typeof data==='object'?data:{};
      accountSafeSummaryFetchedAt=Date.now();
      credentialUiV5LastErrorAt=0;
      credentialUiV5Render();
    }).catch(()=>{
      if(requestId!==credentialUiV5RequestSeq||resolveCredentialClientId()!==clientId)return;
      accountSafeSummaryData=null;
      accountSafeSummaryFetchedAt=0;
      credentialUiV5Error();
    }).finally(()=>{
      if(requestId===credentialUiV5RequestSeq)accountSafeSummaryPromise=null;
    });
  };
'''
security=security[:ensure_start]+v5_ensure+security[ensure_end:]

plural_start=security.find("  const installProtectedFieldControls=()=>{")
plural_end=security.find("  const applyCredentialLoadingToCards=()=>{",plural_start)
if plural_start<0 or plural_end<0:
    raise SystemExit('Unable to locate legacy protected-field installer')
security=security[:plural_start]+"  const installProtectedFieldControls=()=>{};\n\n"+security[plural_end:]

def no_op_block(start_marker,end_marker,replacement,label):
    global security
    start=security.find(start_marker)
    end=security.find(end_marker,start)
    if start<0 or end<0:
        raise SystemExit(f'Unable to locate {label}')
    security=security[:start]+replacement+security[end:]

no_op_block("  const applyCredentialLoadingToCards=()=>{","  const applyCredentialStatusUnavailable=()=>{","  const applyCredentialLoadingToCards=()=>{};\n",'legacy loading renderer')
no_op_block("  const applyCredentialStatusUnavailable=()=>{","  const applyCredentialStatusToCards=()=>{","  const applyCredentialStatusUnavailable=()=>{};\n",'legacy status error renderer')
no_op_block("  const applyCredentialStatusToCards=()=>{","  const ensureCredentialStatus=()=>{","  const applyCredentialStatusToCards=()=>{};\n",'legacy boolean status renderer')
no_op_block("  const ensureCredentialStatus=()=>{","  const prepareInlineCell=(cell,kind)=>{","  const ensureCredentialStatus=()=>{};\n",'legacy boolean status requester')

periodic_variants=(
    "    if(isAccountAssetPage()){ensureCredentialStatus();ensureAccountSafeSummary();installProtectedFieldControls();}\n    else ensureAccountSafeSummary();\n",
    "    if(isAccountAssetPage()){ensureCredentialStatus();ensureAccountSafeSummary();}\n    else ensureAccountSafeSummary();\n",
)
periodic_count=0
for old in periodic_variants:
    if old in security:
        security=security.replace(old,"    ensureAccountSafeSummary();\n",1)
        periodic_count+=1
if periodic_count!=1:
    raise SystemExit(f'Unexpected periodic credential scan replacement count: {periodic_count}')

export_marker="  window.__GROWTHOPS_SECURITY_HOTFIX__={\n"
if security.count(export_marker)!=1:
    raise SystemExit(f'Unexpected security export marker count: {security.count(export_marker)}')
export=r'''  window.__GROWTHOPS_CREDENTIAL_UI_V5__={
    installed:true,
    version:'5.0',
    state:()=>credentialUiV5State,
    clientId:()=>credentialUiV5ClientId,
    refresh:()=>{accountSafeSummaryFetchedAt=0;credentialUiV5LastErrorAt=0;ensureAccountSafeSummary();}
  };
'''
security=security.replace(export_marker,export+export_marker,1)

# Fold the former v5.1 prefetch stage into the controller before writing dist.
state_marker="  let credentialUiV5LastErrorAt=0;\n"
if security.count(state_marker)!=1:
    raise SystemExit(f'Unexpected v5 state marker count: {security.count(state_marker)}')
security=security.replace(
    state_marker,
    state_marker+
    "  const credentialUiV51PrefetchCache=new Map();\n"
    "  let credentialUiV51PrefetchPromise=null;\n"
    "  let credentialUiV51PrefetchClientId='';\n",
    1,
)

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

visibility_marker="  document.addEventListener('visibilitychange',()=>{\n"
if security.count(visibility_marker)!=1:
    raise SystemExit(f'Unexpected visibility marker count: {security.count(visibility_marker)}')
security=security.replace(visibility_marker,"  document.addEventListener('visibilitychange',()=>{\n    if(document.hidden)credentialUiV51ClearPrefetch();\n",1)

beforeunload_marker="  window.addEventListener('beforeunload',clearCredentialUnlock);\n"
if security.count(beforeunload_marker)!=1:
    raise SystemExit(f'Unexpected beforeunload unlock marker count: {security.count(beforeunload_marker)}')
security=security.replace(beforeunload_marker,beforeunload_marker+"  window.addEventListener('beforeunload',credentialUiV51ClearPrefetch);\n  window.addEventListener('pagehide',credentialUiV51ClearPrefetch);\n",1)

version_old="    version:'5.0',\n"
if security.count(version_old)!=1:
    raise SystemExit(f'Unexpected v5 diagnostic version count: {security.count(version_old)}')
security=security.replace(version_old,"    version:'5.1',\n",1)
refresh_old="    refresh:()=>{accountSafeSummaryFetchedAt=0;credentialUiV5LastErrorAt=0;ensureAccountSafeSummary();}\n"
refresh_new="    prefetch:()=>credentialUiV51Prefetch(),\n    refresh:()=>{accountSafeSummaryFetchedAt=0;credentialUiV5LastErrorAt=0;ensureAccountSafeSummary();}\n"
if security.count(refresh_old)!=1:
    raise SystemExit(f'Unexpected v5 refresh marker count: {security.count(refresh_old)}')
security=security.replace(refresh_old,refresh_new,1)

index_path.write_text(html,encoding='utf-8')
security_path.write_text(security,encoding='utf-8')
index_hash=hashlib.sha256(index_path.read_bytes()).hexdigest()
security_hash=hashlib.sha256(security_path.read_bytes()).hexdigest()
if index_hash!='3fb5874a43264d74e55222be7c19fa2a0abaa516a0b3fe480e6bcf327cdbe11e':
    raise SystemExit('Consolidated credential controller changed the v5.1 index baseline: '+index_hash)
if security_hash!='c47e0ebc7c5c09fdee1f542974ec4e560e5d46987f523d1995f2a4d34d51976c':
    raise SystemExit('Consolidated credential controller changed the v5.1 security baseline: '+security_hash)
print('CREDENTIAL_UI_CONTROLLER_FINALIZE_OK: reveal_transport=v5-single-value; index='+index_hash+'; security='+security_hash)
