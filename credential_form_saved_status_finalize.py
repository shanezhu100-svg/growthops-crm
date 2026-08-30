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
# This prevents a stale selectedAssetsClientId=0 from suppressing the actual client
# being edited while preserving the aggregate no-credential boundary on /assets.
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
replace_block(
    '  const resolveCredentialClientId=()=>{',
    '  function clearReveal(){',
    resolver_block,
    'credential client resolver',
)

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
replace_block(
    '  const platformForCard=card=>{',
    '  const cardIdentityTokens=card=>{',
    platform_block,
    'platform resolver',
)

card_block = r'''  const credentialLabelCount=(root,label)=>[...root.querySelectorAll('*')].filter(el=>el.children.length===0&&cleanText(el)===label).length;
  const credentialCardForLabel=label=>{
    let node=label?.parentElement||null;
    for(let i=0;node&&i<9;i+=1,node=node.parentElement){
      if(credentialLabelCount(node,'登录账号')===1&&credentialLabelCount(node,'密码 / 2FA')===1)return node;
    }
    return null;
  };
'''
replace_block(
    '  const credentialCardForLabel=label=>{',
    '  const valueCellForLabel=label=>{',
    card_block,
    'per-account card resolver',
)

value_block = r'''  const configureCredentialFormOverlay=(host,control,kind)=>{
    const parent=control?.parentElement;
    if(!host||!control||!parent)return host;
    const originalPlaceholderAttr='data-growthops-credential-original-placeholder';
    if(!control.hasAttribute(originalPlaceholderAttr)){
      control.setAttribute(originalPlaceholderAttr,control.getAttribute('placeholder')||'');
    }
    control.setAttribute('data-growthops-credential-form-input',kind);
    host.__growthOpsCredentialFormControl=control;
    if(getComputedStyle(parent).position==='static')parent.style.position='relative';
    host.className='growthops-credential-inline';
    Object.assign(host.style,{
      position:'absolute',zIndex:'3',display:'flex',alignItems:'center',gap:'8px',
      margin:'0',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis',
      cursor:'text',boxSizing:'border-box'
    });
    const place=()=>{
      if(!host.isConnected||!control.isConnected||!parent.isConnected)return;
      const parentRect=parent.getBoundingClientRect();
      const controlRect=control.getBoundingClientRect();
      host.style.left=`${Math.max(0,controlRect.left-parentRect.left+14)}px`;
      host.style.right=`${Math.max(0,parentRect.right-controlRect.right+14)}px`;
      host.style.top=`${Math.max(0,controlRect.top-parentRect.top)}px`;
      host.style.height=`${Math.max(1,controlRect.height)}px`;
      const controlStyle=getComputedStyle(control);
      host.style.font=controlStyle.font;
      host.style.letterSpacing=controlStyle.letterSpacing;
      host.style.color=controlStyle.color;
    };
    const sync=()=>{
      place();
      const hasSavedDisplay=String(host.textContent||'').trim()!=='';
      const editing=document.activeElement===control||String(control.value||'')!=='';
      const visible=hasSavedDisplay&&!editing;
      host.style.visibility=visible?'visible':'hidden';
      const original=control.getAttribute(originalPlaceholderAttr)||'';
      control.setAttribute('placeholder',visible?'':original);
    };
    host.__growthOpsCredentialFormSync=sync;
    if(host.getAttribute('data-growthops-credential-overlay-click-bound')!=='1'){
      host.addEventListener('mousedown',event=>{
        if(event.target?.closest?.('button'))return;
        event.preventDefault();
        host.__growthOpsCredentialFormControl?.focus?.();
      });
      host.setAttribute('data-growthops-credential-overlay-click-bound','1');
    }
    if(control.getAttribute('data-growthops-credential-overlay-bound')!==kind){
      control.addEventListener('focus',sync);
      control.addEventListener('input',sync);
      control.addEventListener('change',sync);
      control.addEventListener('blur',()=>queueMicrotask(sync));
      control.setAttribute('data-growthops-credential-overlay-bound',kind);
    }
    requestAnimationFrame(sync);
    return host;
  };
  const credentialFormStatusHost=(label,kind)=>{
    let node=label?.parentElement||null;
    for(let i=0;node&&i<5;i+=1,node=node.parentElement){
      const controls=[...node.querySelectorAll('input,textarea')];
      if(controls.length!==1)continue;
      const control=controls[0];
      const parent=control.parentElement;
      if(!parent)continue;
      const attr='data-growthops-credential-form-status';
      const next=control.nextElementSibling;
      if(next&&next.getAttribute(attr)===kind)return configureCredentialFormOverlay(next,control,kind);
      const existing=[...node.querySelectorAll(`[${attr}="${kind}"]`)].find(el=>el.parentElement===parent);
      if(existing)return configureCredentialFormOverlay(existing,control,kind);
      const host=document.createElement('div');
      host.setAttribute(attr,kind);
      host.setAttribute('aria-live','polite');
      control.insertAdjacentElement('afterend',host);
      return configureCredentialFormOverlay(host,control,kind);
    }
    return null;
  };
  const valueCellForLabel=label=>{
    const labelText=cleanText(label);
    const kind=labelText==='登录账号'?'account':labelText==='密码 / 2FA'?'secret':'';
    if(kind){
      const host=credentialFormStatusHost(label,kind);
      if(host)return host;
    }
    const row=label?.parentElement;
    if(!row)return null;
    const children=[...row.children].filter(el=>el!==label);
    return children.length?children[children.length-1]:null;
  };
'''
replace_block(
    '  const valueCellForLabel=label=>{',
    '  const locateCredentialRows=()=>{',
    value_block,
    'credential value/status resolver',
)

# Show safe login identifiers inside the matching input chrome while keeping the
# underlying mutation input value untouched. Read-only/detail cells retain their
# previous exact rendering.
old_login = "        row.accountCell.textContent=login||'未录入';\n"
new_login = (
    "        const formStatus=row.accountCell.getAttribute('data-growthops-credential-form-status')==='account';\n"
    "        row.accountCell.textContent=formStatus?(login||''):(login||'未录入');\n"
    "        row.accountCell.__growthOpsCredentialFormSync?.();\n"
)
if security.count(old_login) != 1:
    fail(f'unexpected login summary assignment count: {security.count(old_login)}')
security = security.replace(old_login, new_login, 1)

# Empty edit-form credential state stays visually blank so the original input
# placeholder remains visible. Read-only/detail credential cells retain `未录入`.
old_secret_empty = "        row.passwordCell.textContent='未录入';\n"
new_secret_empty = (
    "        const formSecretStatus=row.passwordCell.getAttribute('data-growthops-credential-form-status')==='secret';\n"
    "        row.passwordCell.textContent=formSecretStatus?'':'未录入';\n"
    "        row.passwordCell.__growthOpsCredentialFormSync?.();\n"
)
if security.count(old_secret_empty) != 1:
    fail(f'unexpected empty secret summary assignment count: {security.count(old_secret_empty)}')
security = security.replace(old_secret_empty, new_secret_empty, 1)

# Saved password / 2FA stays masked in the input overlay; ADMIN reveal continues to
# use the existing time-bounded scalar eye control inside the same overlay surface.
old_secret_recorded = "        row.passwordCell.textContent='••••••••';\n"
new_secret_recorded = (
    "        row.passwordCell.textContent='••••••••';\n"
    "        row.passwordCell.__growthOpsCredentialFormSync?.();\n"
)
if security.count(old_secret_recorded) != 1:
    fail(f'unexpected recorded secret summary assignment count: {security.count(old_secret_recorded)}')
security = security.replace(old_secret_recorded, new_secret_recorded, 1)

# Fail closed if any future change starts hydrating persisted credentials into form
# values/model state. The overlay is visual-only; typing focuses the real mutation
# input and temporarily hides the saved-value overlay.
for forbidden in (
    ".value=login",
    ".value=password",
    ".value=twofa",
    "loginPassword=value",
    "loginAccount=value",
):
    if forbidden in security:
        fail('plaintext form hydration marker found: ' + forbidden)

SECURITY.write_text(security, encoding='utf-8')
print(
    'CREDENTIAL_FORM_SAVED_STATUS_FINALIZE_OK: '
    'context=client-form+detail+assets; client-form-id=before-asset-sentinel; '
    'form-inputs=mutation-only; safe-summary=input-overlay; empty-form-status=placeholder; '
    'password=masked+scalar-eye-inside-input; per-account-card=nearest-pair; '
    'security=' + hashlib.sha256(SECURITY.read_bytes()).hexdigest()
)
