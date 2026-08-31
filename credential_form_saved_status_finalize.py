from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
SECURITY = ROOT / 'dist' / 'cloud-security-hotfix.js'

html = INDEX.read_text(encoding='utf-8')
security = SECURITY.read_text(encoding='utf-8')


def fail(message: str) -> None:
    raise SystemExit('CREDENTIAL_FORM_SAVED_STATUS_FINALIZE_FAILED: ' + message)


# Client edit credential inputs remain mutation-only. Persisted safe-summary / reveal
# state is rendered as an overlay inside the matching input chrome; Vault plaintext is
# never assigned to the input value or Vue account model automatically.
if "account.loginAccount" not in html or "account.loginPassword" not in html:
    fail('client form credential inputs are no longer present in final HTML')
if "client-form" not in html:
    fail('client-form route marker missing from final HTML')

old_context = "  const isCredentialSummaryContext=()=>isAccountAssetPage()||vm.currentPage==='client-detail';\n"
new_context = "  const isCredentialSummaryContext=()=>isAccountAssetPage()||vm.currentPage==='client-detail'||vm.currentPage==='client-form';\n"
if security.count(old_context) != 1:
    fail(f'unexpected credential summary context count: {security.count(old_context)}')
security = security.replace(old_context, new_context, 1)


def replace_block(start_marker: str, end_marker: str, replacement: str, label: str) -> None:
    global security
    start = security.find(start_marker)
    end = security.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0 or end <= start:
        fail('unable to locate ' + label)
    security = security[:start] + replacement + security[end:]


# client-form contains the same Facebook/TikTok labels as the account-assets page,
# so the historical body-text detector can classify it as an asset page. Resolve
# explicit detail/edit context before applying the account-assets ALL/0 sentinel.
resolver_block = r'''  const resolveCredentialClientId=()=>{
    if(vm.currentPage==='client-detail'||vm.currentPage==='client-form'){
      const directCandidates=[vm.selectedClientId,vm.selectedClient?.id,vm.currentClient?.id];
      for(const value of directCandidates){
        const text=String(value??'');
        if(text&&text!=='0'&&text.toUpperCase()!=='ALL')return text;
      }
    }
    if(isAccountAssetPage()){
      const explicitAssetsClientId=vm.selectedAssetsClientId;
      const explicitAssetsClientText=String(explicitAssetsClientId??'');
      if(explicitAssetsClientText==='0'||explicitAssetsClientText.toUpperCase()==='ALL')return '';
      if(explicitAssetsClientId!==undefined&&explicitAssetsClientId!==null&&explicitAssetsClientText!=='')return explicitAssetsClientText;
      const visibleClientId=resolveVisibleClientId();
      if(visibleClientId)return visibleClientId;
      for(const key of ['selectedAssetClientId','assetClientId','clientAssetClientId']){
        const value=vm[key];
        if(value!==undefined&&value!==null&&String(value)!=='')return String(value);
      }
      for(const key of ['assetClient','currentClient','selectedClient']){
        const value=vm[key];
        if(value&&value.id!==undefined&&value.id!==null&&String(value.id)!=='')return String(value.id);
      }
    }
    for(const key of ['selectedAssetClientId','assetClientId','clientAssetClientId']){
      const value=vm[key];
      if(value!==undefined&&value!==null&&String(value)!=='')return String(value);
    }
    for(const key of ['selectedClient','currentClient','assetClient']){
      const value=vm[key];
      if(value&&value.id!==undefined&&value.id!==null&&String(value.id)!=='')return String(value.id);
    }
    const visibleClientId=resolveVisibleClientId();
    if(visibleClientId)return visibleClientId;
    if(vm.selectedClientId!==undefined&&vm.selectedClientId!==null&&String(vm.selectedClientId)!=='')return String(vm.selectedClientId);
    return '';
  };
'''
replace_block('  const resolveCredentialClientId=()=>{','  function clearReveal(){',resolver_block,'credential client resolver')

# Keep the historical FB/TK base classifier in this presentation finalizer. The
# later client-account correspondence finalizer owns the reviewed four-platform
# expansion, so build ordering remains explicit and fail-closed.
platform_block = r'''  const platformForCard=card=>{
    let node=card||null;
    for(let i=0;node&&i<9;i+=1,node=node.parentElement){
      const value=String(node.textContent||'').toLowerCase();
      if(value.includes('facebook'))return 'facebook';
      if(value.includes('tiktok'))return 'tiktok';
    }
    return '';
  };
'''
replace_block('  const platformForCard=card=>{','  const cardIdentityTokens=card=>{',platform_block,'platform resolver')

# Credential login labels are presentation aliases rather than platform identity.
# Current edit forms use 登录账号 while older/detail views may use login-email labels.
card_block = r'''  const credentialAccountLabelTexts=['登录账号','登录邮箱','登录邮箱 / 手机号'];
  const credentialLabelCount=(root,label)=>[...root.querySelectorAll('*')].filter(el=>el.children.length===0&&cleanText(el)===label).length;
  const credentialAccountLabelCount=root=>credentialAccountLabelTexts.reduce((count,label)=>count+credentialLabelCount(root,label),0);
  const credentialCardForLabel=label=>{
    let node=label?.parentElement||null;
    for(let i=0;node&&i<9;i+=1,node=node.parentElement){
      if(credentialAccountLabelCount(node)===1&&credentialLabelCount(node,'密码 / 2FA')===1)return node;
    }
    return null;
  };
'''
replace_block('  const credentialCardForLabel=label=>{','  const valueCellForLabel=label=>{',card_block,'per-account card resolver')

value_block = r'''  const configureCredentialFormOverlay=(host,control,kind)=>{
    const parent=control?.parentElement;
    if(!host||!control||!parent)return host;
    const originalPlaceholderAttr='data-growthops-credential-original-placeholder';
    if(!control.hasAttribute(originalPlaceholderAttr))control.setAttribute(originalPlaceholderAttr,control.getAttribute('placeholder')||'');
    control.setAttribute('data-growthops-credential-form-input',kind);
    host.__growthOpsCredentialFormControl=control;
    if(getComputedStyle(parent).position==='static')parent.style.position='relative';
    host.className='growthops-credential-inline';
    Object.assign(host.style,{position:'absolute',zIndex:'3',display:'flex',alignItems:'center',gap:'8px',margin:'0',whiteSpace:'nowrap',overflow:kind==='secret'?'visible':'hidden',textOverflow:'ellipsis',cursor:'text',boxSizing:'border-box'});
    const place=()=>{
      if(!host.isConnected||!control.isConnected||!parent.isConnected)return;
      const parentRect=parent.getBoundingClientRect(),controlRect=control.getBoundingClientRect();
      host.style.left=`${Math.max(0,controlRect.left-parentRect.left+14)}px`;
      host.style.right=`${Math.max(0,parentRect.right-controlRect.right+14)}px`;
      host.style.top=`${Math.max(0,controlRect.top-parentRect.top)}px`;
      host.style.height=`${Math.max(1,controlRect.height)}px`;
      const controlStyle=getComputedStyle(control);
      host.style.font=controlStyle.font;host.style.letterSpacing=controlStyle.letterSpacing;
      host.style.color=kind==='account'?'#0f172a':controlStyle.color;
    };
    const sync=()=>{
      place();
      const hasSavedDisplay=String(host.textContent||'').trim()!=='';
      const editing=String(control.value||'')!=='';
      const visible=hasSavedDisplay&&!editing;
      host.style.visibility=visible?'visible':'hidden';
      const original=control.getAttribute(originalPlaceholderAttr)||'';
      control.setAttribute('placeholder',visible?'':original);
      if(kind==='secret'){
        const eye=host.querySelector('button[aria-label="显示密码和 2FA"],button[aria-label="隐藏密码和 2FA"]');
        if(eye)Object.assign(eye.style,{display:'inline-flex',alignItems:'center',justifyContent:'center',flex:'0 0 auto',minWidth:'26px',minHeight:'26px',position:'relative',zIndex:'4'});
      }
    };
    host.__growthOpsCredentialFormSync=sync;
    if(host.getAttribute('data-growthops-credential-overlay-click-bound')!=='1'){
      host.addEventListener('mousedown',event=>{if(event.target?.closest?.('button'))return;event.preventDefault();host.__growthOpsCredentialFormControl?.focus?.();});
      host.setAttribute('data-growthops-credential-overlay-click-bound','1');
    }
    if(control.getAttribute('data-growthops-credential-overlay-bound')!==kind){
      control.addEventListener('focus',sync);control.addEventListener('input',sync);control.addEventListener('change',sync);control.addEventListener('blur',()=>queueMicrotask(sync));
      control.setAttribute('data-growthops-credential-overlay-bound',kind);
    }
    requestAnimationFrame(sync);return host;
  };
  const credentialFormStatusHost=(label,kind)=>{
    let node=label?.parentElement||null;
    for(let i=0;node&&i<5;i+=1,node=node.parentElement){
      const controls=[...node.querySelectorAll('input,textarea')];
      if(controls.length!==1)continue;
      const control=controls[0],parent=control.parentElement;if(!parent)continue;
      const attr='data-growthops-credential-form-status';
      const next=control.nextElementSibling;
      if(next&&next.getAttribute(attr)===kind)return configureCredentialFormOverlay(next,control,kind);
      const existing=[...node.querySelectorAll(`[${attr}="${kind}"]`)].find(el=>el.parentElement===parent);
      if(existing)return configureCredentialFormOverlay(existing,control,kind);
      const host=document.createElement('div');host.setAttribute(attr,kind);host.setAttribute('aria-live','polite');control.insertAdjacentElement('afterend',host);return configureCredentialFormOverlay(host,control,kind);
    }
    return null;
  };
  const valueCellForLabel=label=>{
    const labelText=cleanText(label);
    const kind=credentialAccountLabelTexts.includes(labelText)?'account':labelText==='密码 / 2FA'?'secret':'';
    if(kind){const host=credentialFormStatusHost(label,kind);if(host)return host;}
    const row=label?.parentElement;if(!row)return null;
    const children=[...row.children].filter(el=>el!==label);return children.length?children[children.length-1]:null;
  };
'''
replace_block('  const valueCellForLabel=label=>{','  const locateCredentialRows=()=>{',value_block,'credential value/status resolver')

# Preserve the inherited platform-specific label choice as the explicit input to the
# later correspondence finalizer. That later stage replaces this block with the
# alias-based resolver once four-platform platform classification is installed.
locate_block = r'''  const locateCredentialRows=()=>{
    const rows=[];
    const accountLabels=new Set(['登录账号','登录邮箱','登录邮箱 / 手机号']);
    const labels=[...document.querySelectorAll('*')].filter(el=>el.children.length===0&&(accountLabels.has(cleanText(el))||cleanText(el)==='密码 / 2FA'));
    const seen=new Set();
    for(const label of labels){
      const card=credentialCardForLabel(label);
      if(!card||seen.has(card))continue;
      const platform=platformForCard(card);
      if(!platform)continue;
      seen.add(card);
      const accountLabelText=platform==='google'?'登录邮箱':platform==='instagram'?'登录邮箱 / 手机号':'登录账号';
      const accountLabel=exactLeaf(card,accountLabelText);
      const passwordLabel=exactLeaf(card,'密码 / 2FA');
      rows.push({card,platform,accountCell:valueCellForLabel(accountLabel),passwordCell:valueCellForLabel(passwordLabel)});
    }
    return rows.filter(row=>row.platform&&(row.accountCell||row.passwordCell));
  };
'''
replace_block('  const locateCredentialRows=()=>{','  const prepareInlineCell=(cell,kind)=>{',locate_block,'credential row resolver handoff')

old_login = "        row.accountCell.textContent=login||'未录入';\n"
new_login = "        const formStatus=row.accountCell.getAttribute('data-growthops-credential-form-status')==='account';\n        row.accountCell.textContent=formStatus?(login||''):(login||'未录入');\n        row.accountCell.__growthOpsCredentialFormSync?.();\n"
if security.count(old_login) != 1: fail(f'unexpected login summary assignment count: {security.count(old_login)}')
security = security.replace(old_login, new_login, 1)
old_secret_empty = "        row.passwordCell.textContent='未录入';\n"
new_secret_empty = "        const formSecretStatus=row.passwordCell.getAttribute('data-growthops-credential-form-status')==='secret';\n        row.passwordCell.textContent=formSecretStatus?'':'未录入';\n        row.passwordCell.__growthOpsCredentialFormSync?.();\n"
if security.count(old_secret_empty) != 1: fail(f'unexpected empty secret summary assignment count: {security.count(old_secret_empty)}')
security = security.replace(old_secret_empty, new_secret_empty, 1)
old_secret_recorded = "        row.passwordCell.textContent='••••••••';\n"
new_secret_recorded = "        row.passwordCell.textContent='••••••••';\n        row.passwordCell.__growthOpsCredentialFormSync?.();\n"
if security.count(old_secret_recorded) != 1: fail(f'unexpected recorded secret summary assignment count: {security.count(old_secret_recorded)}')
security = security.replace(old_secret_recorded, new_secret_recorded, 1)

for forbidden in ('.value=login','.value=password','.value=twofa','loginPassword=value','loginAccount=value'):
    if forbidden in security: fail('plaintext form hydration marker found: ' + forbidden)

SECURITY.write_text(security, encoding='utf-8')
print('CREDENTIAL_FORM_SAVED_STATUS_FINALIZE_OK: context=client-form+detail+assets; client-form-id=before-asset-sentinel; form-inputs=mutation-only; safe-summary=input-overlay; focus=preserves-saved-state; typing=mutation-handoff; empty-form-status=placeholder; login=value-color; password=masked+visible-hit-target-eye-inside-input; per-account-card=nearest-pair; login-labels=alias-ready; security=' + hashlib.sha256(SECURITY.read_bytes()).hexdigest())
