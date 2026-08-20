from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
security_path=root/'dist'/'cloud-security-hotfix.js'
html=index_path.read_text(encoding='utf-8')
security=security_path.read_text(encoding='utf-8')

V5_ATTR='data-growthops-credential-v5-state'

# Preboot observer starts in <head>, before the Vue body can paint credential fallback
# values. It blanks only credential value cells that live inside platform credential
# cards, and stops touching a cell once the v5 controller marks it ready/error.
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
# Earlier compatibility finalizers use this text as an internal marker. It must not
# survive into browser output.
html=html.replace('读取中…','')

# Add v5 state without changing the underlying v4 Vault/unlock primitives.
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

# Replace the legacy safe-summary renderer with the single v5 renderer. The old
# helpers remain available for account matching and the v4 per-field reveal control,
# but no other runtime path is allowed to own credential cell rendering.
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

# Error writer is also owned by v5.
err_start=security.find("  const markAccountSafeSummaryUnavailable=()=>{")
err_end=security.find("  const clearAccountSafeSummary=()=>{",err_start)
if err_start<0 or err_end<0:
    raise SystemExit('Unable to locate safe-summary error renderer')
security=security[:err_start]+"  const markAccountSafeSummaryUnavailable=credentialUiV5Error;\n"+security[err_end:]

# Replace safe-summary orchestration with an explicit state machine and request
# generation guard. A late response for client A can never overwrite client B.
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

# The plural legacy installer is retired. v5 alone calls the singular v4-protected
# installProtectedFieldControl after the safe summary has decided a password exists.
plural_start=security.find("  const installProtectedFieldControls=()=>{")
plural_end=security.find("  const applyCredentialLoadingToCards=()=>{",plural_start)
if plural_start<0 or plural_end<0:
    raise SystemExit('Unable to locate legacy protected-field installer')
security=security[:plural_start]+"  const installProtectedFieldControls=()=>{};\n\n"+security[plural_end:]

# Retire all old credential-status DOM paths and the boolean status network request.
def no_op_block(start_marker,end_marker,replacement,label):
    global security
    start=security.find(start_marker)
    end=security.find(end_marker,start)
    if start<0 or end<0:
        raise SystemExit(f'Unable to locate {label}')
    security=security[:start]+replacement+security[end:]

no_op_block(
    "  const applyCredentialLoadingToCards=()=>{",
    "  const applyCredentialStatusUnavailable=()=>{",
    "  const applyCredentialLoadingToCards=()=>{};\n",
    'legacy loading renderer',
)
no_op_block(
    "  const applyCredentialStatusUnavailable=()=>{",
    "  const applyCredentialStatusToCards=()=>{",
    "  const applyCredentialStatusUnavailable=()=>{};\n",
    'legacy status error renderer',
)
no_op_block(
    "  const applyCredentialStatusToCards=()=>{",
    "  const ensureCredentialStatus=()=>{",
    "  const applyCredentialStatusToCards=()=>{};\n",
    'legacy boolean status renderer',
)
no_op_block(
    "  const ensureCredentialStatus=()=>{",
    "  const prepareInlineCell=(cell,kind)=>{",
    "  const ensureCredentialStatus=()=>{};\n",
    'legacy boolean status requester',
)

# Periodic UI scan now only asks the v5 controller to ensure the final summary state.
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

# Expose only non-secret diagnostics so future debugging can confirm one controller
# owns rendering without inspecting credentials.
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

index_path.write_text(html,encoding='utf-8')
security_path.write_text(security,encoding='utf-8')
print(
    'CREDENTIAL_UI_V5_FINALIZE_OK: '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}; '
    f'security={hashlib.sha256(security_path.read_bytes()).hexdigest()}'
)
