from pathlib import Path

root = Path(__file__).resolve().parent


def replace_once(source, old, new, label, platform):
    count = source.count(old)
    if count != 1:
        raise SystemExit(f'{platform}: unexpected {label} anchor count: {count}')
    return source.replace(old, new, 1)


def patch_vercel(path):
    source = path.read_text(encoding='utf-8')
    if 'SESSION_TOKEN_MAX_BYTES' in source or 'function sessionTokenInputValid' in source:
        raise SystemExit('vercel: session token byte guard already exists before finalizer')

    source = replace_once(
        source,
        "const LOGIN_PASSWORD_MAX_BYTES = 72;\nconst BODY_TOO_LARGE",
        "const LOGIN_PASSWORD_MAX_BYTES = 72;\nconst SESSION_TOKEN_MAX_BYTES = 64;\nconst BODY_TOO_LARGE",
        'session token constant',
        'vercel',
    )
    source = replace_once(
        source,
        "function safeLog(event, requestIdValue, rpc, status) {",
        """function sessionTokenInputValid(token) {
  return typeof token === 'string'
    && token.length > 0
    && Buffer.byteLength(token, 'utf8') <= SESSION_TOKEN_MAX_BYTES;
}

function safeLog(event, requestIdValue, rpc, status) {""",
        'safeLog helper insertion',
        'vercel',
    )
    source = replace_once(
        source,
        "if (!token) return json(res, 502, { message: 'LOGIN_SESSION_MISSING' });",
        "if (!sessionTokenInputValid(token)) return json(res, 502, { message: 'LOGIN_SESSION_MISSING' });",
        'login response token guard',
        'vercel',
    )
    source = replace_once(
        source,
        "    if (!sessionToken) {\n      res.setHeader('Set-Cookie', clearSessionCookie());",
        "    if (!sessionTokenInputValid(sessionToken)) {\n      res.setHeader('Set-Cookie', clearSessionCookie());",
        'authenticated cookie guard',
        'vercel',
    )

    for marker in (
        'SESSION_TOKEN_MAX_BYTES = 64',
        'function sessionTokenInputValid',
        "Buffer.byteLength(token, 'utf8') <= SESSION_TOKEN_MAX_BYTES",
        "if (!sessionTokenInputValid(token)) return json(res, 502",
        'if (!sessionTokenInputValid(sessionToken))',
    ):
        if marker not in source:
            raise SystemExit(f'vercel: final session token marker missing: {marker}')
    path.write_text(source, encoding='utf-8')


def patch_cloudflare(path):
    source = path.read_text(encoding='utf-8')
    if 'SESSION_TOKEN_MAX_BYTES' in source or 'function sessionTokenInputValid' in source:
        raise SystemExit('cloudflare: session token byte guard already exists before finalizer')

    source = replace_once(
        source,
        "const LOGIN_PASSWORD_MAX_BYTES = 72;\nconst BODY_TOO_LARGE",
        "const LOGIN_PASSWORD_MAX_BYTES = 72;\nconst SESSION_TOKEN_MAX_BYTES = 64;\nconst BODY_TOO_LARGE",
        'session token constant',
        'cloudflare',
    )
    source = replace_once(
        source,
        "function safeLog(event,requestIdValue,rpc,status){",
        """function sessionTokenInputValid(token){
  return typeof token==='string'&&token.length>0&&new TextEncoder().encode(token).byteLength<=SESSION_TOKEN_MAX_BYTES;
}
function safeLog(event,requestIdValue,rpc,status){""",
        'safeLog helper insertion',
        'cloudflare',
    )
    source = replace_once(
        source,
        "if(!token) return respond(502,{message:'LOGIN_SESSION_MISSING'});",
        "if(!sessionTokenInputValid(token)) return respond(502,{message:'LOGIN_SESSION_MISSING'});",
        'login response token guard',
        'cloudflare',
    )
    source = replace_once(
        source,
        "    if(!sessionToken) return respond(401,{message:'SESSION_REQUIRED'},{'Set-Cookie':clearSessionCookie()});",
        "    if(!sessionTokenInputValid(sessionToken)) return respond(401,{message:'SESSION_REQUIRED'},{'Set-Cookie':clearSessionCookie()});",
        'authenticated cookie guard',
        'cloudflare',
    )

    for marker in (
        'SESSION_TOKEN_MAX_BYTES = 64',
        'function sessionTokenInputValid',
        'new TextEncoder().encode(token).byteLength<=SESSION_TOKEN_MAX_BYTES',
        "if(!sessionTokenInputValid(token)) return respond(502",
        'if(!sessionTokenInputValid(sessionToken))',
    ):
        if marker not in source:
            raise SystemExit(f'cloudflare: final session token marker missing: {marker}')
    path.write_text(source, encoding='utf-8')


patch_vercel(root / 'api' / 'crm.js')
patch_cloudflare(root / 'functions' / 'api' / 'crm.js')

print('SESSION_TOKEN_INPUT_BOUNDS_FINALIZE_OK: platforms=vercel+cloudflare; cookie-token<=64B; login-response-token<=64B; oversize-cookie=401+clear-before-fetch; oversize-login-token=502+no-cookie')
