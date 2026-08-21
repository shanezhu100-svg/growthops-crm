from pathlib import Path

root = Path(__file__).resolve().parent
security_finalize = (root / 'security_finalize.py').read_text(encoding='utf-8')
security_gate = (root / 'test_security_hotfix_output.py').read_text(encoding='utf-8')
bootstrap = (root / 'supabase/migrations/20260816_retire_unused_bootstrap_and_v3_rpcs.sql').read_text(encoding='utf-8')
restore_v3 = (root / 'supabase/migrations/20260816_z_restore_v3_browser_exec_after_build_chain_audit.sql').read_text(encoding='utf-8')
legacy = (root / 'supabase/migrations/20260816_retire_direct_legacy_login_load_rpc.sql').read_text(encoding='utf-8')
authn = (root / 'supabase/migrations/20260816_revoke_unused_authenticated_rpc_exec.sql').read_text(encoding='utf-8')
defaults = (root / 'supabase/migrations/20260816_default_deny_public_schema_for_crm.sql').read_text(encoding='utf-8')
credential_surface = (root / 'supabase/migrations/20260821_credential_surface_session_hardening.sql').read_text(encoding='utf-8')

required = {
    'finalizer switches login to v3': 'security v3 login endpoint',
    'finalizer switches load to v3': 'security v3 load endpoint',
    'final gate requires v3 login': "rpc('crm_login_v3'",
    'final gate requires v3 load': "rpc('crm_load_state_v3'",
    'bootstrap browser access revoked': 'revoke execute on function public.crm_bootstrap_admin(text,text,text,text) from anon, authenticated, public;',
    'legacy login browser access revoked': 'revoke execute on function public.crm_login(text,text) from anon, authenticated, public;',
    'legacy load browser access revoked': 'revoke execute on function public.crm_load_state(text) from anon, authenticated, public;',
    'legacy login service only': 'grant execute on function public.crm_login(text,text) to service_role;',
    'legacy load service only': 'grant execute on function public.crm_load_state(text) to service_role;',
    'v3 login anon preserved': 'grant execute on function public.crm_login_v3(text,text) to anon, service_role;',
    'v3 load anon preserved': 'grant execute on function public.crm_load_state_v3(text) to anon, service_role;',
    'v3 restore explicitly removes authenticated login': 'revoke execute on function public.crm_login_v3(text,text) from authenticated;',
    'v3 restore explicitly removes authenticated load': 'revoke execute on function public.crm_load_state_v3(text) from authenticated;',
    'authenticated removed from v3 login': 'revoke execute on function public.crm_login_v3(text,text) from authenticated;',
    'authenticated removed from v3 load': 'revoke execute on function public.crm_load_state_v3(text) from authenticated;',
    'authenticated removed from v4 reveal': 'revoke execute on function public.crm_reveal_client_secret_field_v4(text,text,text,text,text) from authenticated;',
    'legacy full-client reveal browser access revoked': 'revoke execute on function public.crm_reveal_client_secrets(text,text) from anon, authenticated, public;',
    'legacy full-client reveal service only': 'grant execute on function public.crm_reveal_client_secrets(text,text) to service_role;',
    'future tables default deny': 'alter default privileges for role postgres in schema public revoke all on tables from anon, authenticated;',
    'future sequences default deny': 'alter default privileges for role postgres in schema public revoke all on sequences from anon, authenticated;',
    'future functions default deny': 'alter default privileges for role postgres in schema public revoke execute on functions from anon, authenticated;',
}

sources = {
    'finalizer switches login to v3': security_finalize,
    'finalizer switches load to v3': security_finalize,
    'final gate requires v3 login': security_gate,
    'final gate requires v3 load': security_gate,
    'bootstrap browser access revoked': bootstrap,
    'legacy login browser access revoked': legacy,
    'legacy load browser access revoked': legacy,
    'legacy login service only': legacy,
    'legacy load service only': legacy,
    'v3 login anon preserved': restore_v3,
    'v3 load anon preserved': restore_v3,
    'v3 restore explicitly removes authenticated login': restore_v3,
    'v3 restore explicitly removes authenticated load': restore_v3,
    'authenticated removed from v3 login': authn,
    'authenticated removed from v3 load': authn,
    'authenticated removed from v4 reveal': authn,
    'legacy full-client reveal browser access revoked': credential_surface,
    'legacy full-client reveal service only': credential_surface,
    'future tables default deny': defaults,
    'future sequences default deny': defaults,
    'future functions default deny': defaults,
}

missing = [name for name, marker in required.items() if marker not in sources[name]]
if missing:
    raise SystemExit('RPC_SURFACE_HARDENING_TESTS_FAILED missing: ' + ', '.join(missing))

for source_name, text in (('bootstrap', bootstrap), ('restore_v3', restore_v3)):
    if 'to anon, authenticated, service_role' in text:
        raise SystemExit(f'RPC_SURFACE_HARDENING_TESTS_FAILED authenticated grant can reappear via {source_name}')

if 'grant execute on function public.crm_reveal_client_secrets(text,text) to anon' in credential_surface:
    raise SystemExit('RPC_SURFACE_HARDENING_TESTS_FAILED legacy full-client reveal re-granted to anon')
if 'grant execute on function public.crm_reveal_client_secrets(text,text) to authenticated' in credential_surface:
    raise SystemExit('RPC_SURFACE_HARDENING_TESTS_FAILED legacy full-client reveal re-granted to authenticated')

# Final browser artifact must not regress to secret-bearing legacy RPC names.
if 'legacy crm_login endpoint remains in final adapter' not in security_gate:
    raise SystemExit('RPC_SURFACE_HARDENING_TESTS_FAILED missing legacy login artifact gate')
if 'legacy crm_load_state endpoint remains in final adapter' not in security_gate:
    raise SystemExit('RPC_SURFACE_HARDENING_TESTS_FAILED missing legacy load artifact gate')
if "cloud.rpc('crm_reveal_client_secrets'" not in (root / 'test_credential_ui_v6_output.py').read_text(encoding='utf-8'):
    raise SystemExit('RPC_SURFACE_HARDENING_TESTS_FAILED missing browser full-client reveal regression gate')

print('RPC_SURFACE_HARDENING_TESTS_OK')
