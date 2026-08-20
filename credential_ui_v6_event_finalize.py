from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
security_path=root/'dist'/'cloud-security-hotfix.js'
html=index_path.read_text(encoding='utf-8')
security=security_path.read_text(encoding='utf-8')

# v6.1 runtime cleanup removed the obsolete 300ms reveal-button poll. That poll had
# also been the compatibility trigger that called ensureAccountSafeSummary(). Replace
# it with event-driven liveness only: initial load, route/client changes and actual DOM
# credential-card mutations. Do not restore any reveal button or persistent poll.
old_schedule="queueMicrotask(()=>{queued=false;scrub();});"
new_schedule="queueMicrotask(()=>{queued=false;scrub();document.dispatchEvent(new CustomEvent('growthops:credential-dom-change'));});"
if html.count(old_schedule)!=1:
    raise SystemExit(f'Unexpected credential preboot schedule count: {html.count(old_schedule)}')
html=html.replace(old_schedule,new_schedule,1)

export_marker="  window.__GROWTHOPS_CREDENTIAL_UI_V5__={\n"
if security.count(export_marker)!=1:
    raise SystemExit(f'Unexpected credential diagnostics export count: {security.count(export_marker)}')

runtime=r'''  let credentialUiV6EnsureFrame=0;
  const credentialUiV6ScheduleEnsure=()=>{
    if(credentialUiV6EnsureFrame)return;
    credentialUiV6EnsureFrame=requestAnimationFrame(()=>{
      credentialUiV6EnsureFrame=0;
      ensureAccountSafeSummary();
    });
  };
  document.addEventListener('click',credentialUiV6ScheduleEnsure,true);
  document.addEventListener('change',credentialUiV6ScheduleEnsure,true);
  document.addEventListener('growthops:credential-dom-change',credentialUiV6ScheduleEnsure);
  window.addEventListener('hashchange',credentialUiV6ScheduleEnsure);
  window.addEventListener('popstate',credentialUiV6ScheduleEnsure);
  window.addEventListener('focus',credentialUiV6ScheduleEnsure);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)credentialUiV6ScheduleEnsure();});
  credentialUiV6ScheduleEnsure();

'''
security=security.replace(export_marker,runtime+export_marker,1)

# Fail closed: the old polling/reveal machinery must stay removed, while the new
# event-driven trigger must reach the existing safe-summary controller.
for forbidden in (
    "setInterval(ensureRevealButton,300)",
    "function ensureRevealButton()",
    "async function revealSelectedClient()",
    "cloud.rpc('crm_reveal_client_secrets'",
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
):
    if forbidden in security:
        raise SystemExit(f'Legacy credential runtime unexpectedly restored: {forbidden}')
for required in (
    "const credentialUiV6ScheduleEnsure=()=>{",
    "requestAnimationFrame(()=>{",
    "ensureAccountSafeSummary();",
    "document.addEventListener('change',credentialUiV6ScheduleEnsure,true);",
    "document.addEventListener('growthops:credential-dom-change',credentialUiV6ScheduleEnsure);",
    "credentialUiV6ScheduleEnsure();",
    "crm_client_account_safe_summary",
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_field_v4",
):
    if required not in security:
        raise SystemExit(f'Credential v6 event liveness marker missing: {required}')

index_path.write_text(html,encoding='utf-8')
security_path.write_text(security,encoding='utf-8')
print(
    'CREDENTIAL_UI_V6_EVENT_FINALIZE_OK: '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}; '
    f'security={hashlib.sha256(security_path.read_bytes()).hexdigest()}'
)
