from pathlib import Path

root = Path(__file__).resolve().parent
security_finalize = (root / 'security_finalize.py').read_text(encoding='utf-8')
security_gate = (root / 'test_security_hotfix_output.py').read_text(encoding='utf-8')
bootstrap = (root / 'supabase/migrations/20260816_retire_unused_bootstrap_and_v3_rpcs.sql').read_text(encoding='utf-8')
restore_v3 = (root / 'supabase/migrations/20260816_z_restore_v3_browser_exec_after_build_chain_audit.sql').read_text(encoding='utf-8')
legacy = (root / 'supabase/migrations/20260816_retire_direct_legacy_login_load_rpc.sql').read_text(encoding='utf-8')
authn = (root / 'supabase/migrations/20260816_revoke_unused_authenticated_rpc_exec.sql').read_text(encoding='utf-8')

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
    'v3 login anon preserved': 'grant execute on function public.crm_login_v3(text,text) to anon, authenticated, service_role;',
    'v3 load anon preserved': 'grant execute on function public.crm_load_state_v3(text) to anon, authenticated, service_role;',
    'authenticated removed from v3 login': 'revoke execute on function public.crm_login_v3(text,text) from authenticated;',
    'authenticated removed from v3 load': 'revoke execute on function public.crm_load_state_v3(text) from authenticated;',
    'authenticated removed from v4 reveal': 'revoke execute on function public.crm_reveal_client_secret_field_v4(text,text,text,text,text) from authenticated;',
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
    'authenticated removed from v3 login': authn,
    'authenticated removed from v3 load': authn,
    'authenticated removed from v4 reveal': authn,
}

missing = [name for name, marker in required.items() if marker not in sources[name]]
if missing:
    raise SystemExit('RPC_SURFACE_HARDENING_TESTS_FAILED missing: ' + ', '.join(missing))

# Final browser artifact must not regress to the secret-bearing base RPC names.
if 'legacy crm_login endpoint remains in final adapter' not in security_gate:
    raise SystemExit('RPC_SURFACE_HARDENING_TESTS_FAILED missing legacy login artifact gate')
if 'legacy crm_load_state endpoint remains in final adapter' not in security_gate:
    raise SystemExit('RPC_SURFACE_HARDENING_TESTS_FAILED missing legacy load artifact gate')

print('RPC_SURFACE_HARDENING_TESTS_OK')
