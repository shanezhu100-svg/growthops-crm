from pathlib import Path
import json

cfg = json.loads((Path(__file__).resolve().parent / 'vercel.json').read_text(encoding='utf-8'))
headers = {}
for rule in cfg.get('headers', []):
    if rule.get('source') == '/(.*)':
        headers.update({item.get('key'): item.get('value') for item in rule.get('headers', [])})

required = {
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
    'X-Frame-Options': 'DENY',
    'X-Permitted-Cross-Domain-Policies': 'none',
    'Cross-Origin-Opener-Policy': 'same-origin',
}
for key, value in required.items():
    if headers.get(key) != value:
        raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED {key}')

pp = headers.get('Permissions-Policy', '')
for directive in ('camera=()', 'microphone=()', 'geolocation=()', 'payment=()', 'usb=()'):
    if directive not in pp:
        raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED permissions {directive}')

csp = headers.get('Content-Security-Policy', '')
for directive in (
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "frame-src 'none'",
    "form-action 'self'",
    "connect-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com",
    "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com",
    "img-src 'self' data: blob:",
    "media-src 'self' data: blob:",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    'upgrade-insecure-requests',
):
    if directive not in csp:
        raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED csp {directive}')

# Transitional CSP: current Vue global runtime compiles templates in-browser and the
# Tailwind Play CDN injects styles, so unsafe-eval/unsafe-inline are temporarily
# required. Script/XHR/media destinations remain explicit to limit XSS exfiltration.
def directive_tokens(name):
    part=csp.split(name+' ',1)[1].split(';',1)[0]
    return [token for token in part.split() if token]

script_tokens=directive_tokens('script-src')
connect_tokens=directive_tokens('connect-src')
img_tokens=directive_tokens('img-src')
media_tokens=directive_tokens('media-src')
if '*' in script_tokens or '*' in connect_tokens or '*' in img_tokens or '*' in media_tokens:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED CSP wildcard source')
if 'https:' in script_tokens or 'http:' in script_tokens:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED script-src broad scheme source')
if connect_tokens != ["'self'"]:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED connect-src must remain same-origin only')
for name,tokens in (('img-src',img_tokens),('media-src',media_tokens)):
    if 'https:' in tokens or 'http:' in tokens:
        raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED {name} external scheme exfiltration path')
    if tokens != ["'self'",'data:','blob:']:
        raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED {name} must remain self/data/blob only')

print('VERCEL_SECURITY_HEADERS_TESTS_OK: csp=dependency-allowlist; connect=self-only; img-media=self-data-blob; runtime-inline-compat=true')
