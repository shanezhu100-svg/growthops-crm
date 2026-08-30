from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
SECURITY = ROOT / 'dist' / 'cloud-security-hotfix.js'

html = INDEX.read_text(encoding='utf-8')
security = SECURITY.read_text(encoding='utf-8')


def fail(message: str) -> None:
    raise SystemExit('CREDENTIAL_FORM_SAVED_STATUS_FINALIZE_FAILED: ' + message)


# This finalizer intentionally does not hydrate Vault plaintext into the Vue edit
# model. The real input remains a mutation field; safe-summary/reveal state is
# rendered in a sibling status host instead.
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

value_block = r'''  const credentialFormStatusHost=(label,kind)=>{
    let node=label?.parentElement||null;
    for(let i=0;node&&i<5;i+=1,node=node.parentElement){
      const controls=[...node.querySelectorAll('input,textarea')];
      if(controls.length!==1)continue;
      const control=controls[0];
      const attr='data-growthops-credential-form-status';
      const next=control.nextElementSibling;
      if(next&&next.getAttribute(attr)===kind)return next;
      const existing=[...node.querySelectorAll(`[${attr}="${kind}"]`)].find(el=>el.parentElement===control.parentElement);
      if(existing)return existing;
      const host=document.createElement('div');
      host.setAttribute(attr,kind);
      host.setAttribute('aria-live','polite');
      host.className='growthops-credential-inline text-[11px] text-slate-500 mt-1';
      control.insertAdjacentElement('afterend',host);
      return host;
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

# Make the edit-form safe-summary state explicit without changing the actual form
# value. Read-only/detail cells retain their previous exact rendering.
old_login = "        row.accountCell.textContent=login||'未录入';\n"
new_login = (
    "        const formStatus=row.accountCell.getAttribute('data-growthops-credential-form-status')==='account';\n"
    "        row.accountCell.textContent=formStatus?(login?`已保存：${login}`:'未录入'):(login||'未录入');\n"
)
if security.count(old_login) != 1:
    fail(f'unexpected login summary assignment count: {security.count(old_login)}')
security = security.replace(old_login, new_login, 1)

# A mutation observer already re-runs the credential scanner. This status host is
# disposable Vue-adjacent DOM: if Vue re-renders the form, it will be recreated
# from the safe summary rather than persisted into the client model.
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
    'context=client-form+detail+assets; form-inputs=mutation-only; '
    'safe-summary=sibling-status; per-account-card=nearest-pair; '
    'security=' + hashlib.sha256(SECURITY.read_bytes()).hexdigest()
)
