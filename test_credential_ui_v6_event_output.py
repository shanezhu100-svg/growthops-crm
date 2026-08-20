from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
html=(root/'dist'/'index.html').read_text(encoding='utf-8')
security=(root/'dist'/'cloud-security-hotfix.js').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    "growthops:credential-dom-change",
    "const credentialUiV6ScheduleEnsure=()=>{",
    "requestAnimationFrame(()=>{",
    "ensureAccountSafeSummary();",
    "document.addEventListener('click',credentialUiV6ScheduleEnsure,true);",
    "document.addEventListener('change',credentialUiV6ScheduleEnsure,true);",
    "document.addEventListener('growthops:credential-dom-change',credentialUiV6ScheduleEnsure);",
    "window.addEventListener('hashchange',credentialUiV6ScheduleEnsure);",
    "window.addEventListener('popstate',credentialUiV6ScheduleEnsure);",
    "credentialUiV6ScheduleEnsure();",
):
    require(marker in html or marker in security,f'credential v6 event liveness marker missing: {marker}')

for forbidden in (
    "setInterval(ensureRevealButton,300)",
    "function ensureRevealButton()",
    "async function revealSelectedClient()",
    "cloud.rpc('crm_reveal_client_secrets'",
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
):
    require(forbidden not in security,f'legacy credential polling/reveal path restored: {forbidden}')

for required in (
    "crm_client_account_safe_summary",
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_field_v4",
    "row.accountCell.textContent=login||'未录入';",
    "row.passwordCell.textContent='••••••••';",
    "setTimeout(hide,10000)",
):
    require(required in security,f'credential safe-summary/v4 path missing: {required}')

print(
    'CREDENTIAL_UI_V6_EVENT_OUTPUT_TESTS_OK: '
    f'index={hashlib.sha256((root/"dist"/"index.html").read_bytes()).hexdigest()}; '
    f'security={hashlib.sha256((root/"dist"/"cloud-security-hotfix.js").read_bytes()).hexdigest()}'
)
