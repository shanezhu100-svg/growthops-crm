from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
security_path=root/'dist'/'cloud-security-hotfix.js'
html=index_path.read_text(encoding='utf-8')
security=security_path.read_text(encoding='utf-8')

# v6 is the final browser-runtime cleanup/gate. Earlier credential status/loading
# stages remain only as build-time compatibility scaffolding for the canonical app;
# none of their cache/RPC/rendering paths may survive in the shipped JS.
legacy_state="""  let credentialStatusClientId='';
  let credentialStatusData=null;
  let credentialStatusPromise=null;
  let credentialStatusFetchedAt=0;
"""
if legacy_state in security:
    security=security.replace(legacy_state,'',1)

legacy_cache_start=security.find("  const credentialStatusCacheKey=clientId=>{")
legacy_cache_end=security.find("  const matchCredentialValueTypography=cell=>{",legacy_cache_start)
if legacy_cache_start>=0:
    if legacy_cache_end<0:
        raise SystemExit('Unable to bound legacy credential status cache block')
    security=security[:legacy_cache_start]+security[legacy_cache_end:]

# Old status RPC/writers must already have been retired by v5. Fail closed if they
# are still present instead of trying to hide another active renderer.
for forbidden in (
    "crm_client_credential_status",
    "growthops_credential_status_v2",
    "row.accountCell.textContent='已录入'",
    "cell.textContent='读取中…'",
):
    if forbidden in security:
        raise SystemExit(f'Legacy credential runtime path survived before v6: {forbidden}')

# Replace the old blank/hidden preboot state with a stable first-paint placeholder.
# Password cells are masked immediately; account cells get a neutral skeleton. This
# prevents stale fallback values from flashing while also avoiding a several-second
# empty gap on refresh. No credential summary or secret is persisted in the browser.
placeholder_style=r'''<style id="growthops-credential-v6-placeholder-style">
[data-growthops-credential-v6-placeholder-kind="account"]{color:transparent!important;min-height:1.25em;position:relative}
[data-growthops-credential-v6-placeholder-kind="account"]::after{content:'';display:inline-block;width:64px;height:10px;border-radius:999px;background:#e8ecf3;vertical-align:middle}
[data-growthops-credential-v6-placeholder-kind="password"]{letter-spacing:.08em;color:#475569}
</style>'''
preboot_marker='<script id="growthops-credential-ui-v5-preboot">'
if html.count(preboot_marker)!=1:
    raise SystemExit(f'Unexpected v5 preboot marker count: {html.count(preboot_marker)}')
if 'growthops-credential-v6-placeholder-style' in html:
    raise SystemExit('Credential v6 placeholder style already present')
html=html.replace(preboot_marker,placeholder_style+preboot_marker,1)

old_scrub="""      if(cell.textContent)cell.textContent='';
      cell.setAttribute(ATTR,'preboot');
"""
new_scrub=r"""      const row=label.parentElement;
      const kind=clean(label)==='密码 / 2FA'?'password':'account';
      const placeholder=kind==='password'?'••••••••':'\u00a0';
      const alreadyPlaceholder=cell.getAttribute(ATTR)==='preboot'&&cell.getAttribute('data-growthops-credential-v6-placeholder-kind')===kind&&cell.textContent===placeholder;
      if(!alreadyPlaceholder){
        cell.textContent=placeholder;
        cell.setAttribute('data-growthops-credential-v6-placeholder-kind',kind);
        cell.setAttribute('aria-busy','true');
        cell.setAttribute(ATTR,'preboot');
      }
      if(row){
        row.style.visibility='visible';
        row.style.pointerEvents='none';
        row.setAttribute('data-growthops-credential-v6-gate','pending');
      }
"""
if html.count(old_scrub)!=1:
    raise SystemExit(f'Unexpected v5 preboot scrub count: {html.count(old_scrub)}')
html=html.replace(old_scrub,new_scrub,1)

old_export="  window.__GROWTHOPS_CREDENTIAL_V5_PREBOOT__={scrub};\n"
new_export=r'''  const gatedRows=()=>[...document.querySelectorAll('[data-growthops-credential-v6-gate]')];
  const clearPlaceholder=()=>{
    for(const cell of document.querySelectorAll('[data-growthops-credential-v6-placeholder-kind]')){
      cell.removeAttribute('data-growthops-credential-v6-placeholder-kind');
      cell.removeAttribute('aria-busy');
    }
  };
  const hide=()=>{
    scrub();
    for(const row of gatedRows()){
      row.style.visibility='visible';
      row.style.pointerEvents='none';
      row.setAttribute('data-growthops-credential-v6-gate','pending');
    }
  };
  const reveal=()=>{
    clearPlaceholder();
    for(const row of gatedRows()){
      row.style.visibility='visible';
      row.style.pointerEvents='';
      row.setAttribute('data-growthops-credential-v6-gate','ready');
    }
  };
  window.__GROWTHOPS_CREDENTIAL_V5_PREBOOT__={scrub,hide,reveal};
  window.__GROWTHOPS_CREDENTIAL_V6_GATE__={hide,reveal};
'''
if html.count(old_export)!=1:
    raise SystemExit(f'Unexpected v5 preboot export count: {html.count(old_export)}')
html=html.replace(old_export,new_export,1)

# Apply the placeholder after v5 resets the cells so the loading state survives the
# reset synchronously and is present before the next paint.
blank_start=security.find("  const credentialUiV5Blank=clientId=>{")
blank_end=security.find("  const credentialUiV5DomReady=()=>{",blank_start)
if blank_start<0 or blank_end<0:
    raise SystemExit('Unable to bound v5 blank block')
blank_block=security[blank_start:blank_end]
blank_tail=blank_block.rfind("  };\n")
if blank_tail<0:
    raise SystemExit('Unable to locate v5 blank tail')
if "__GROWTHOPS_CREDENTIAL_V6_GATE__" not in blank_block:
    blank_block=blank_block[:blank_tail]+"    window.__GROWTHOPS_CREDENTIAL_V6_GATE__?.hide?.();\n"+blank_block[blank_tail:]
security=security[:blank_start]+blank_block+security[blank_end:]

# Reveal only after the complete safe-summary render pass has finished.
render_start=security.find("  const credentialUiV5Render=()=>{")
render_end=security.find("  const credentialUiV5Error=()=>{",render_start)
if render_start<0 or render_end<0:
    raise SystemExit('Unable to bound v5 render block')
render_block=security[render_start:render_end]
render_tail=render_block.rfind("  };\n")
if render_tail<0:
    raise SystemExit('Unable to locate v5 render tail')
if "__GROWTHOPS_CREDENTIAL_V6_GATE__" not in render_block:
    render_block=render_block[:render_tail]+"    window.__GROWTHOPS_CREDENTIAL_V6_GATE__?.reveal?.();\n"+render_block[render_tail:]
security=security[:render_start]+render_block+security[render_end:]

# Error is also a final state: clear placeholders only after all error cells have
# been written, avoiding per-row stagger on network failures.
error_start=security.find("  const credentialUiV5Error=()=>{")
error_end=security.find("  const applyAccountSafeSummaryToCards=credentialUiV5Render;",error_start)
if error_start<0 or error_end<0:
    raise SystemExit('Unable to bound v5 error block')
error_block=security[error_start:error_end]
error_tail=error_block.rfind("  };\n")
if error_tail<0:
    raise SystemExit('Unable to locate v5 error tail')
if "__GROWTHOPS_CREDENTIAL_V6_GATE__" not in error_block:
    error_block=error_block[:error_tail]+"    window.__GROWTHOPS_CREDENTIAL_V6_GATE__?.reveal?.();\n"+error_block[error_tail:]
security=security[:error_start]+error_block+security[error_end:]

# -----------------------------------------------------------------------------
# Runtime cleanup: remove obsolete polling/button/full-client compatibility code.
# These paths are no longer reachable because the top-level reveal action was removed
# and v5/v6 render credentials from safe-summary + v4 per-field reveal only.
# -----------------------------------------------------------------------------

poll="  setInterval(ensureRevealButton,300);\n  ensureRevealButton();\n"
if security.count(poll)!=1:
    raise SystemExit(f'Unexpected legacy reveal polling count: {security.count(poll)}')
security=security.replace(poll,'',1)

# Remove obsolete account-asset/top-button lookup helpers while preserving the
# client resolver that follows them.
asset_buttons_start=security.find("  const accountAssetRevealButtons=()=>{")
secure_buttons_start=security.find("  const secureRevealButtons=()=>{",asset_buttons_start)
resolver_comment=security.find("  // Resolver coverage marker retained",secure_buttons_start)
if asset_buttons_start<0 or secure_buttons_start<0 or resolver_comment<0:
    raise SystemExit('Unable to bound legacy reveal-button helper blocks')
security=security[:asset_buttons_start]+security[resolver_comment:]

# setRevealButtonState is now dead. clearReveal still remains because v4 uses it to
# clear any visible per-field secret controls on background/page lifecycle events.
set_button_start=security.find("  function setRevealButtonState(visible){")
clear_reveal_start=security.find("  function clearReveal(){",set_button_start)
if set_button_start<0 or clear_reveal_start<0:
    raise SystemExit('Unable to bound legacy reveal-button state function')
security=security[:set_button_start]+security[clear_reveal_start:]
if security.count("    setRevealButtonState(false);\n")!=1:
    raise SystemExit('Unexpected clearReveal legacy button-state call count')
security=security.replace("    setRevealButtonState(false);\n",'',1)

# Remove obsolete full-client inline rendering helpers. Keep bestSecretValue,
# locateCredentialRows and prepareInlineCell because the v4 single-field eye path
# still relies on them.
full_inline_start=security.find("  const setInlineValue=(cell,value,kind)=>{")
reveal_selected_start=security.find("  async function revealSelectedClient(){",full_inline_start)
if full_inline_start<0 or reveal_selected_start<0:
    raise SystemExit('Unable to bound obsolete full-client inline reveal block')
security=security[:full_inline_start]+security[reveal_selected_start:]

# Remove the now-unreachable revealSelectedClient + ensureRevealButton functions.
reveal_selected_start=security.find("  async function revealSelectedClient(){")
visibility_start=security.find("  document.addEventListener('visibilitychange',()=>{",reveal_selected_start)
if reveal_selected_start<0 or visibility_start<0:
    raise SystemExit('Unable to bound obsolete reveal entry functions')
security=security[:reveal_selected_start]+security[visibility_start:]

# Remove compatibility no-op functions from the shipped JS. Build-time legacy
# finalizers can still create them earlier, but they must not execute or ship.
for noop in (
    "  const installProtectedFieldControls=()=>{};\n",
    "  const applyCredentialLoadingToCards=()=>{};\n",
    "  const applyCredentialStatusUnavailable=()=>{};\n",
    "  const applyCredentialStatusToCards=()=>{};\n",
    "  const ensureCredentialStatus=()=>{};\n",
):
    if noop in security:
        security=security.replace(noop,'',1)

# The removed top-level button id must not remain as live runtime machinery.
button_const="  const BUTTON_ID='growthops-secure-credential-button';\n"
if button_const in security:
    security=security.replace(button_const,'',1)

# Version the diagnostics without exposing any cached summary values.
version_marker="    version:'5.1',\n"
version_count=security.count(version_marker)
if version_count!=1:
    raise SystemExit(f'Unexpected v5.1 diagnostic version count: {version_count}')
security=security.replace(
    version_marker,
    "    version:'6.3',\n    renderMode:'atomic-placeholder-idempotent',\n    runtimeCleanup:true,\n",
    1,
)

# Final safety assertions: browser output may use the safe summary and v4 reveal only.
for forbidden in (
    "crm_client_credential_status",
    "growthops_credential_status_v2",
    "credentialStatusCacheKey",
    "readCredentialStatusCache",
    "writeCredentialStatusCache",
    "cloud.rpc('crm_reveal_client_secrets'",
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
    "setInterval(ensureRevealButton,300)",
    "function ensureRevealButton()",
    "async function revealSelectedClient()",
    "accountAssetRevealButtons",
    "secureRevealButtons",
    "setRevealButtonState",
    "setInlineValue=(cell,value,kind)",
    "setInlineSecretControl=(cell,value)",
    "applyInlineSecrets(secretTree)",
    "renderRevealModal(clientId,secretTree)",
    "const ensureCredentialStatus=()=>{}",
    "const installProtectedFieldControls=()=>{}",
):
    if forbidden in security:
        raise SystemExit(f'Forbidden legacy credential browser path survived v6 cleanup: {forbidden}')
for required in (
    "crm_client_account_safe_summary",
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_field_v4",
    "const bestSecretValue=",
    "const locateCredentialRows=()=>{",
    "const prepareInlineCell=(cell,kind)=>{",
    "setTimeout(hide,10000)",
    "if(document.hidden){clearReveal();clearCredentialUnlock();}",
):
    if required not in security:
        raise SystemExit(f'Required credential safety path missing after v6 cleanup: {required}')

index_path.write_text(html,encoding='utf-8')
security_path.write_text(security,encoding='utf-8')
print(
    'CREDENTIAL_UI_V6_FINALIZE_OK: '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}; '
    f'security={hashlib.sha256(security_path.read_bytes()).hexdigest()}'
)
