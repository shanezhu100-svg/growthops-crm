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

# Upgrade the preboot scrubber into an atomic visibility gate. The original Vue
# fallback text may exist briefly in DOM, but the entire credential row is hidden
# before paint and layout space is preserved. v6 reveals all rows only after the
# safe-summary renderer finishes the whole pass.
old_scrub="""      if(cell.textContent)cell.textContent='';
      cell.setAttribute(ATTR,'preboot');
"""
new_scrub="""      const row=label.parentElement;
      if(row){
        row.style.visibility='hidden';
        row.style.pointerEvents='none';
        row.setAttribute('data-growthops-credential-v6-gate','pending');
      }
      cell.setAttribute(ATTR,'preboot');
"""
if html.count(old_scrub)!=1:
    raise SystemExit(f'Unexpected v5 preboot scrub count: {html.count(old_scrub)}')
html=html.replace(old_scrub,new_scrub,1)

old_export="  window.__GROWTHOPS_CREDENTIAL_V5_PREBOOT__={scrub};\n"
new_export=r'''  const gatedRows=()=>[...document.querySelectorAll('[data-growthops-credential-v6-gate]')];
  const hide=()=>{
    scrub();
    for(const row of gatedRows()){
      row.style.visibility='hidden';
      row.style.pointerEvents='none';
      row.setAttribute('data-growthops-credential-v6-gate','pending');
    }
  };
  const reveal=()=>{
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

# Hide synchronously before any client/context reset writes transitional values.
blank_marker="""  const credentialUiV5Blank=clientId=>{
    credentialUiV5State='loading';
    credentialUiV5ClientId=String(clientId||'');
"""
blank_new="""  const credentialUiV5Blank=clientId=>{
    window.__GROWTHOPS_CREDENTIAL_V6_GATE__?.hide?.();
    credentialUiV5State='loading';
    credentialUiV5ClientId=String(clientId||'');
"""
if security.count(blank_marker)!=1:
    raise SystemExit(f'Unexpected v5 blank marker count: {security.count(blank_marker)}')
security=security.replace(blank_marker,blank_new,1)

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

# Error is also a final state: reveal all rows together only after all error cells
# have been written, avoiding per-row stagger on network failures.
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

# Version the diagnostics without exposing any cached summary values.
version_marker="    version:'5.1',\n"
version_count=security.count(version_marker)
if version_count!=1:
    raise SystemExit(f'Unexpected v5.1 diagnostic version count: {version_count}')
security=security.replace(
    version_marker,
    "    version:'6.0',\n    renderMode:'atomic-visibility',\n",
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
):
    if forbidden in security:
        raise SystemExit(f'Forbidden legacy credential browser path survived v6: {forbidden}')
for required in (
    "crm_client_account_safe_summary",
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_field_v4",
    "setTimeout(hide,10000)",
    "if(document.hidden){clearReveal();clearCredentialUnlock();}",
):
    if required not in security:
        raise SystemExit(f'Required credential safety path missing after v6: {required}')

index_path.write_text(html,encoding='utf-8')
security_path.write_text(security,encoding='utf-8')
print(
    'CREDENTIAL_UI_V6_FINALIZE_OK: '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}; '
    f'security={hashlib.sha256(security_path.read_bytes()).hexdigest()}'
)
