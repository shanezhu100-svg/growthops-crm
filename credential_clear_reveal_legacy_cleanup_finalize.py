from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
SECURITY = ROOT / 'dist' / 'cloud-security-hotfix.js'

html = INDEX.read_text(encoding='utf-8')
security = SECURITY.read_text(encoding='utf-8')
legacy_call = "    applyCredentialStatusToCards();\n"
current_call = "    applyAccountSafeSummaryToCards();\n"
legacy_definition = "const applyCredentialStatusToCards"

# credential_ui_v5 temporarily retains the old boolean-status renderer as a no-op
# compatibility marker. credential_ui_v6 intentionally removes that definition,
# but the historical clearReveal() call survived. That leaves a latent ReferenceError
# on visibility/page lifecycle paths. Final output must contain only the current
# account-safe-summary renderer.
if security.count(legacy_call) != 1:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        f'expected exactly one retired call, found {security.count(legacy_call)}'
    )
if legacy_definition in security:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        'retired renderer definition unexpectedly survived v6 cleanup'
    )
if security.count(current_call) < 1:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        'current account-safe-summary renderer call missing'
    )

security = security.replace(legacy_call, '', 1)
if 'applyCredentialStatusToCards' in security:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        'retired renderer reference remains after cleanup'
    )

# A create-client form contains the same Facebook/TikTok credential labels as the
# read-only asset/detail surfaces. The historical body-text detector therefore made
# the v6 credential gate treat real form controls as read-only credential cells,
# rendering a fake masked password and disabling pointer events. Keep credential
# summary rendering route-scoped: assets/detail are read surfaces, while client-form
# participates only when form.id proves that this is an existing-client edit.
old_context = (
    "  const isCredentialSummaryContext=()=>isAccountAssetPage()||vm.currentPage==='client-detail'||"
    "(vm.currentPage==='client-form'&&Boolean(clientFormCredentialId()));\n"
)
new_context = (
    "  const isCredentialSummaryContext=()=>vm.currentPage==='assets'||vm.currentPage==='client-detail'||"
    "(vm.currentPage==='client-form'&&Boolean(clientFormCredentialId()));\n"
)
if security.count(old_context) != 1:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        f'unexpected credential context authority count: {security.count(old_context)}'
    )
security = security.replace(old_context, new_context, 1)

# On a real client-form, vm.form/form.id is the sole account correspondence authority.
# Empty form.id is create mode and fails closed. A small number of isolated historical
# test/compatibility contexts do not expose vm.form at all; keep their existing
# selected-client fallback without weakening the real create-mode boundary.
old_client_context = r'''  const credentialClientForContext=()=>{
    const directId=String(vm.selectedClientId??'');
    if(vm.currentPage==='client-detail'||vm.currentPage==='client-form'){
      if(vm.selectedClient&&String(vm.selectedClient?.id??'')===directId)return vm.selectedClient;
      const match=(Array.isArray(vm.clients)?vm.clients:[]).find(item=>String(item?.id??'')===directId);
      return match||vm.selectedClient||vm.currentClient||null;
    }
    if(isAccountAssetPage()){
      const assetId=String(vm.selectedAssetsClientId??'');
      if(assetId==='0'||assetId.toUpperCase()==='ALL')return null;
      if(vm.selectedAssetsClient&&String(vm.selectedAssetsClient?.id??'')===assetId)return vm.selectedAssetsClient;
      return (Array.isArray(vm.clients)?vm.clients:[]).find(item=>String(item?.id??'')===assetId)||vm.selectedAssetsClient||null;
    }
    return vm.selectedClient||vm.selectedAssetsClient||vm.currentClient||null;
  };
'''
new_client_context = r'''  const credentialClientForContext=()=>{
    if(vm.currentPage==='client-form'){
      const formId=clientFormCredentialId();
      if(formId==='__legacy__'){
        const directId=String(vm.selectedClientId??'');
        if(vm.selectedClient&&String(vm.selectedClient?.id??'')===directId)return vm.selectedClient;
        const match=(Array.isArray(vm.clients)?vm.clients:[]).find(item=>String(item?.id??'')===directId);
        return match||vm.selectedClient||vm.currentClient||null;
      }
      if(!formId)return null;
      return vm.form||null;
    }
    const directId=String(vm.selectedClientId??'');
    if(vm.currentPage==='client-detail'){
      if(vm.selectedClient&&String(vm.selectedClient?.id??'')===directId)return vm.selectedClient;
      const match=(Array.isArray(vm.clients)?vm.clients:[]).find(item=>String(item?.id??'')===directId);
      return match||vm.selectedClient||vm.currentClient||null;
    }
    if(vm.currentPage==='assets'){
      const assetId=String(vm.selectedAssetsClientId??'');
      if(assetId==='0'||assetId.toUpperCase()==='ALL')return null;
      if(vm.selectedAssetsClient&&String(vm.selectedAssetsClient?.id??'')===assetId)return vm.selectedAssetsClient;
      return (Array.isArray(vm.clients)?vm.clients:[]).find(item=>String(item?.id??'')===assetId)||vm.selectedAssetsClient||null;
    }
    return null;
  };
'''
if security.count(old_client_context) != 1:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        f'unexpected credential client-context count: {security.count(old_client_context)}'
    )
security = security.replace(old_client_context, new_client_context, 1)

# Memory-only prefetch must also be route-scoped. Stale selectedAssetsClientId from a
# previous asset page is not permission to request credential metadata while creating
# a new client.
old_prefetch = r'''  const credentialUiV51CandidateClientId=()=>{
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
'''
new_prefetch = r'''  const credentialUiV51CandidateClientId=()=>{
    const role=String(vm.currentUser?.role||'');
    if(!['ADMIN','OPS'].includes(role))return '';
    if(vm.currentPage==='assets'){
      const assetsId=vm.selectedAssetsClientId;
      const assetsValue=assetsId==null?'':String(assetsId);
      if(assetsValue&&assetsValue!=='0'&&assetsValue.toUpperCase()!=='ALL')return assetsValue;
    }
    if(vm.currentPage==='client-detail'){
      const detailId=vm.selectedClientId??vm.selectedClient?.id;
      const detailValue=detailId==null?'':String(detailId);
      if(detailValue&&detailValue!=='0'&&detailValue.toUpperCase()!=='ALL')return detailValue;
    }
    return '';
  };
'''
if security.count(old_prefetch) != 1:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        f'unexpected credential prefetch resolver count: {security.count(old_prefetch)}'
    )
security = security.replace(old_prefetch, new_prefetch, 1)

# The v6 preboot scrub runs before Vue mounts. It must never gate a mutation input.
# Skip any credential label whose value cell/row contains a real input control; this
# prevents both the fake •••••••• placeholder and pointer-events:none on create/edit
# form controls while preserving the atomic placeholder gate on read-only surfaces.
old_preboot = """      const cell=valueCell(label);\n      if(!cell)continue;\n      const state=cell.getAttribute(ATTR)||'';\n"""
new_preboot = """      const cell=valueCell(label);\n      if(!cell)continue;\n      const formControl=(cell.matches?.('input,textarea,select')?cell:null)||cell.querySelector?.('input,textarea,select')||label.parentElement?.querySelector?.('input,textarea,select');\n      if(formControl)continue;\n      const state=cell.getAttribute(ATTR)||'';\n"""
if html.count(old_preboot) != 1:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        f'unexpected credential preboot scrub anchor count: {html.count(old_preboot)}'
    )
html = html.replace(old_preboot, new_preboot, 1)

if "isCredentialSummaryContext=()=>isAccountAssetPage()" in security:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        'body-text credential context survived final route scoping'
    )
for required in (
    "vm.currentPage==='assets'||vm.currentPage==='client-detail'",
    "if(vm.currentPage==='client-form'){\n      const formId=clientFormCredentialId();",
    "if(formId==='__legacy__'){",
    "if(!formId)return null;",
    "if(vm.currentPage==='assets'){\n      const assetsId=vm.selectedAssetsClientId;",
):
    if required not in security:
        raise SystemExit(
            'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
            'new-client credential interaction authority missing: ' + required
        )
if "const formControl=(cell.matches?.('input,textarea,select')?cell:null)" not in html:
    raise SystemExit(
        'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_FAILED: '
        'preboot mutation-control bypass missing'
    )

INDEX.write_text(html, encoding='utf-8')
SECURITY.write_text(security, encoding='utf-8')
print(
    'CREDENTIAL_CLEAR_REVEAL_LEGACY_CLEANUP_OK: '
    'retired-status-call=removed; current-safe-summary=preserved; '
    'new-client=context-denied+prefetch-denied+form-controls-interactive; '
    'edit-client=form-id-authoritative+legacy-no-form-compatible; index=' + hashlib.sha256(INDEX.read_bytes()).hexdigest() +
    '; security=' + hashlib.sha256(SECURITY.read_bytes()).hexdigest()
)
