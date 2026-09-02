from pathlib import Path

ROOT = Path(__file__).resolve().parent
FORM_SOURCE = (ROOT / 'credential_form_saved_status_finalize.py').read_text(encoding='utf-8')
FINAL_SOURCE = (ROOT / 'credential_clear_reveal_legacy_cleanup_finalize.py').read_text(encoding='utf-8')

form_required = (
    "const clientFormCredentialId=()=>",
    "if(vm.currentPage==='client-form'&&vm.form)",
    "return formId==='__legacy__'?'':formId;",
    "client-form=form-id-authoritative+create-isolated",
)
missing = [marker for marker in form_required if marker not in FORM_SOURCE]
if missing:
    raise SystemExit('NEW_CLIENT_CREDENTIAL_ISOLATION_SOURCE_FAILED: form authority missing ' + ', '.join(missing))

final_required = (
    "isCredentialSummaryContext=()=>vm.currentPage==='assets'||vm.currentPage==='client-detail'",
    "if(vm.currentPage==='client-form'){\n      const formId=clientFormCredentialId();",
    "if(!formId||formId==='__legacy__')return null;",
    "if(vm.currentPage==='assets'){\n      const assetsId=vm.selectedAssetsClientId;",
    "const formControl=(cell.matches?.('input,textarea,select')?cell:null)",
    "if(formControl)continue;",
    "new-client=context-denied+prefetch-denied+form-controls-interactive",
)
missing = [marker for marker in final_required if marker not in FINAL_SOURCE]
if missing:
    raise SystemExit('NEW_CLIENT_CREDENTIAL_ISOLATION_SOURCE_FAILED: final authority missing ' + ', '.join(missing))

for forbidden in (
    "return String(vm.selectedClientId); // create form",
):
    if forbidden in FORM_SOURCE or forbidden in FINAL_SOURCE:
        raise SystemExit('NEW_CLIENT_CREDENTIAL_ISOLATION_SOURCE_FAILED: forbidden stale-client marker ' + forbidden)

print(
    'NEW_CLIENT_CREDENTIAL_ISOLATION_SOURCE_OK: '
    'create-form-id-empty=context+prefetch-denied; edit-form-id=authoritative; '
    'preboot=mutation-controls-bypassed; stale-selected-client=non-authoritative'
)
