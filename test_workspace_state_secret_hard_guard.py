from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
sql=(root/'supabase/migrations/20260816_workspace_state_secret_hard_guard.sql').read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    'v_secret_updates := public.crm_extract_live_secrets',
    'v_secret_merged := public.crm_merge_secret_updates',
    'perform public.crm_write_workspace_secrets',
    'v_public := public.crm_redact_secrets',
    'create or replace function public.crm_save_state',
    'v_public_incoming := public.crm_redact_secrets',
    'v_public_saved := public.crm_redact_secrets(v_public_saved)',
    'set data=v_public_saved',
    'create or replace function public.crm_workspace_state_secret_guard()',
    "new.data := public.crm_redact_secrets",
    'create trigger crm_workspace_state_secret_guard_trg',
    'check (data = public.crm_redact_secrets(data)) not valid',
    'validate constraint crm_workspace_state_secret_free_chk',
):
    require(marker in sql,f'workspace secret hard-guard marker missing: {marker}')

require('v_compat_store' not in sql,'compatibility secret restore must never return to crm_save_state')
require('set data=v_compat_store' not in sql,'ordinary workspace state must never persist restored Vault secrets')
require(sql.find('perform public.crm_write_workspace_secrets') < sql.find('update public.crm_workspace_state'),
        'existing compatibility-era secrets must be merged into Vault before the public row is redacted')

print('WORKSPACE_STATE_SECRET_HARD_GUARD_TESTS_OK: sql='+hashlib.sha256(sql.encode()).hexdigest())
