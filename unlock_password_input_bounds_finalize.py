from pathlib import Path

root = Path(__file__).resolve().parent


def patch_exact(path, helper_old, helper_new, guard_old, guard_new, platform):
    source = path.read_text(encoding='utf-8')
    if 'function unlockPasswordInputValid' in source:
        raise SystemExit(f'{platform}: unlock password helper already exists before finalizer')
    if source.count(helper_old) != 1:
        raise SystemExit(f'{platform}: unexpected upsert helper anchor count: {source.count(helper_old)}')
    if source.count(guard_old) != 1:
        raise SystemExit(f'{platform}: unexpected upsert guard anchor count: {source.count(guard_old)}')
    source = source.replace(helper_old, helper_new, 1)
    source = source.replace(guard_old, guard_new, 1)
    for marker in (
        'function unlockPasswordInputValid',
        'LOGIN_PASSWORD_MAX_BYTES',
        "crm_unlock_credentials_v1",
        "INVALID_REQUEST",
    ):
        if marker not in source:
            raise SystemExit(f'{platform}: final unlock password marker missing: {marker}')
    path.write_text(source, encoding='utf-8')


vercel_helper_old = """function upsertPasswordInputValid(args = {}) {
  if (!Object.prototype.hasOwnProperty.call(args, 'p_password') || args.p_password == null) return true;
  return typeof args.p_password === 'string'
    && Buffer.byteLength(args.p_password, 'utf8') <= LOGIN_PASSWORD_MAX_BYTES;
}
"""
vercel_helper_new = vercel_helper_old + """
function unlockPasswordInputValid(args = {}) {
  return typeof args.p_password === 'string'
    && Buffer.byteLength(args.p_password, 'utf8') <= LOGIN_PASSWORD_MAX_BYTES;
}
"""
vercel_guard_old = """    if (rpc === 'crm_upsert_user' && !upsertPasswordInputValid(args)) {
      return json(res, 400, { message: 'INVALID_REQUEST' });
    }
"""
vercel_guard_new = vercel_guard_old + """    if (rpc === 'crm_unlock_credentials_v1' && !unlockPasswordInputValid(args)) {
      return json(res, 400, { message: 'INVALID_REQUEST' });
    }
"""

cf_helper_old = """function upsertPasswordInputValid(args={}){
  if(!Object.prototype.hasOwnProperty.call(args,'p_password')||args.p_password==null)return true;
  return typeof args.p_password==='string'&&new TextEncoder().encode(args.p_password).byteLength<=LOGIN_PASSWORD_MAX_BYTES;
}
"""
cf_helper_new = cf_helper_old + """function unlockPasswordInputValid(args={}){
  return typeof args.p_password==='string'&&new TextEncoder().encode(args.p_password).byteLength<=LOGIN_PASSWORD_MAX_BYTES;
}
"""
cf_guard_old = "    if(rpc==='crm_upsert_user'&&!upsertPasswordInputValid(args))return respond(400,{message:'INVALID_REQUEST'});\n"
cf_guard_new = cf_guard_old + "    if(rpc==='crm_unlock_credentials_v1'&&!unlockPasswordInputValid(args))return respond(400,{message:'INVALID_REQUEST'});\n"

patch_exact(
    root / 'api' / 'crm.js',
    vercel_helper_old,
    vercel_helper_new,
    vercel_guard_old,
    vercel_guard_new,
    'vercel',
)
patch_exact(
    root / 'functions' / 'api' / 'crm.js',
    cf_helper_old,
    cf_helper_new,
    cf_guard_old,
    cf_guard_new,
    'cloudflare',
)

print('CRM_UNLOCK_PASSWORD_INPUT_BOUNDS_FINALIZE_OK: platforms=vercel+cloudflare; bcrypt-password<=72B; exact-anchor=fail-closed; source-runtime=patched-before-tests')
