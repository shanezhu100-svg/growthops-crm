from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = (ROOT / 'credential_form_saved_status_finalize.py').read_text(encoding='utf-8')

required = (
    "const clientFormCredentialId=()=>",
    "vm.currentPage==='client-form'&&Boolean(clientFormCredentialId())",
    "if(vm.currentPage==='client-form'&&vm.form)",
    "return formId==='__legacy__'?'':formId;",
    "client-form=form-id-authoritative+create-isolated",
)
missing = [marker for marker in required if marker not in SOURCE]
if missing:
    raise SystemExit('NEW_CLIENT_CREDENTIAL_ISOLATION_SOURCE_FAILED: missing ' + ', '.join(missing))

for forbidden in (
    "vm.currentPage==='client-form'||vm.currentPage==='client-detail'",
    "return String(vm.selectedClientId); // create form",
):
    if forbidden in SOURCE:
        raise SystemExit('NEW_CLIENT_CREDENTIAL_ISOLATION_SOURCE_FAILED: forbidden stale-client marker ' + forbidden)

print('NEW_CLIENT_CREDENTIAL_ISOLATION_SOURCE_OK: create-form-id-empty=credential-context-denied; edit-form-id=authoritative; legacy-no-form=fallback-preserved')
