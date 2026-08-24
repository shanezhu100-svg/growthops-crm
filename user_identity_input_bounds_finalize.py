from pathlib import Path

root = Path(__file__).resolve().parent


def patch_exact(path, constant_old, constant_new, helper_old, helper_new, guard_old, guard_new, platform):
    source = path.read_text(encoding='utf-8')
    if 'function upsertIdentityInputValid' in source or 'USER_IDENTITY_MAX_BYTES' in source:
        raise SystemExit(f'{platform}: identity input guard already exists before finalizer')
    for old, label in ((constant_old, 'constant'), (helper_old, 'unlock helper'), (guard_old, 'unlock guard')):
        if source.count(old) != 1:
            raise SystemExit(f'{platform}: unexpected {label} anchor count: {source.count(old)}')
    source = source.replace(constant_old, constant_new, 1)
    source = source.replace(helper_old, helper_new, 1)
    source = source.replace(guard_old, guard_new, 1)
    for marker in (
        'USER_IDENTITY_MAX_BYTES',
        'function upsertIdentityInputValid',
        'p_name',
        'p_username',
        "crm_upsert_user",
        'INVALID_REQUEST',
    ):
        if marker not in source:
            raise SystemExit(f'{platform}: final identity marker missing: {marker}')
    path.write_text(source, encoding='utf-8')


vercel_constant_old = "const LOGIN_USERNAME_MAX_BYTES = 256;\nconst LOGIN_PASSWORD_MAX_BYTES = 72;\n"
vercel_constant_new = "const LOGIN_USERNAME_MAX_BYTES = 256;\nconst USER_IDENTITY_MAX_BYTES = 256;\nconst LOGIN_PASSWORD_MAX_BYTES = 72;\n"
vercel_helper_old = """function unlockPasswordInputValid(args = {}) {
  return typeof args.p_password === 'string'
    && Buffer.byteLength(args.p_password, 'utf8') <= LOGIN_PASSWORD_MAX_BYTES;
}
"""
vercel_helper_new = vercel_helper_old + """
function upsertIdentityInputValid(args = {}) {
  return typeof args.p_name === 'string'
    && typeof args.p_username === 'string'
    && Buffer.byteLength(args.p_name, 'utf8') <= USER_IDENTITY_MAX_BYTES
    && Buffer.byteLength(args.p_username, 'utf8') <= USER_IDENTITY_MAX_BYTES;
}
"""
vercel_guard_old = """    if (rpc === 'crm_unlock_credentials_v1' && !unlockPasswordInputValid(args)) {
      return json(res, 400, { message: 'INVALID_REQUEST' });
    }
"""
vercel_guard_new = vercel_guard_old + """    if (rpc === 'crm_upsert_user' && !upsertIdentityInputValid(args)) {
      return json(res, 400, { message: 'INVALID_REQUEST' });
    }
"""

cf_constant_old = "const LOGIN_USERNAME_MAX_BYTES = 256;\nconst LOGIN_PASSWORD_MAX_BYTES = 72;\n"
cf_constant_new = "const LOGIN_USERNAME_MAX_BYTES = 256;\nconst USER_IDENTITY_MAX_BYTES = 256;\nconst LOGIN_PASSWORD_MAX_BYTES = 72;\n"
cf_helper_old = """function unlockPasswordInputValid(args={}){
  return typeof args.p_password==='string'&&new TextEncoder().encode(args.p_password).byteLength<=LOGIN_PASSWORD_MAX_BYTES;
}
"""
cf_helper_new = cf_helper_old + """function upsertIdentityInputValid(args={}){
  if(typeof args.p_name!=='string'||typeof args.p_username!=='string')return false;
  const encoder=new TextEncoder();
  return encoder.encode(args.p_name).byteLength<=USER_IDENTITY_MAX_BYTES&&encoder.encode(args.p_username).byteLength<=USER_IDENTITY_MAX_BYTES;
}
"""
cf_guard_old = "    if(rpc==='crm_unlock_credentials_v1'&&!unlockPasswordInputValid(args))return respond(400,{message:'INVALID_REQUEST'});\n"
cf_guard_new = cf_guard_old + "    if(rpc==='crm_upsert_user'&&!upsertIdentityInputValid(args))return respond(400,{message:'INVALID_REQUEST'});\n"

patch_exact(root / 'api' / 'crm.js', vercel_constant_old, vercel_constant_new, vercel_helper_old, vercel_helper_new, vercel_guard_old, vercel_guard_new, 'vercel')
patch_exact(root / 'functions' / 'api' / 'crm.js', cf_constant_old, cf_constant_new, cf_helper_old, cf_helper_new, cf_guard_old, cf_guard_new, 'cloudflare')

print('CRM_USER_IDENTITY_INPUT_BOUNDS_FINALIZE_OK: platforms=vercel+cloudflare; name+username<=256B; exact-stage-anchor=fail-closed; source-runtime=patched-before-tests')
