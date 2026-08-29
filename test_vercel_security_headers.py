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
    'Cross-Origin-Resource-Policy': 'same-origin',
    'X-Robots-Tag': 'noindex, nofollow, noarchive',
}
for key, value in required.items():
    if headers.get(key) != value:
        raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED {key}')

pp = headers.get('Permissions-Policy', '')
for directive in ('camera=()', 'microphone=()', 'geolocation=()', 'payment=()', 'usb=()'):
    if directive not in pp:
        raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED permissions {directive}')

csp = headers.get('Content-Security-Policy', '')
expected_script_src = "script-src 'self'"
expected_script_attr = "script-src-attr 'none'"
expected_style_src = "style-src 'self'"
expected_style_elem = "style-src-elem 'self'"
expected_style_attr = "style-src-attr 'none'"
expected_font_src = "font-src 'self' data:"
for directive in (
    "default-src 'self'", "base-uri 'self'", "object-src 'none'", "frame-ancestors 'none'",
    "frame-src 'none'", "form-action 'self'", "connect-src 'self'", expected_script_src,
    expected_script_attr, expected_style_src, expected_style_elem, expected_style_attr,
    expected_font_src, "img-src 'self' data: blob:", "media-src 'self' data: blob:",
    "worker-src 'none'", "manifest-src 'none'", 'upgrade-insecure-requests',
):
    if directive not in csp:
        raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED csp {directive}')

def directive_tokens(name):
    part=csp.split(name+' ',1)[1].split(';',1)[0]
    return [token for token in part.split() if token]

script_tokens=directive_tokens('script-src')
script_attr_tokens=directive_tokens('script-src-attr')
style_tokens=directive_tokens('style-src')
style_elem_tokens=directive_tokens('style-src-elem')
style_attr_tokens=directive_tokens('style-src-attr')
font_tokens=directive_tokens('font-src')
connect_tokens=directive_tokens('connect-src')
img_tokens=directive_tokens('img-src')
media_tokens=directive_tokens('media-src')
worker_tokens=directive_tokens('worker-src')
manifest_tokens=directive_tokens('manifest-src')
all_source_sets=(script_tokens,script_attr_tokens,style_tokens,style_elem_tokens,style_attr_tokens,font_tokens,connect_tokens,img_tokens,media_tokens,worker_tokens,manifest_tokens)
if any('*' in tokens for tokens in all_source_sets):
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED CSP wildcard source')
if any(source in tokens for tokens in (script_tokens, style_tokens, style_elem_tokens, font_tokens) for source in ('https:', 'http:')):
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED broad scheme source')
if script_tokens != ["'self'"]:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED script-src must be same-origin only')
if "'unsafe-inline'" in csp or "'unsafe-eval'" in csp:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED all unsafe script/style CSP capabilities must be absent')
if script_attr_tokens != ["'none'"]:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED script-src-attr must deny all HTML event handler attributes')
if style_tokens != ["'self'"] or style_elem_tokens != ["'self'"]:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED style sources must be same-origin only')
if style_attr_tokens != ["'none'"]:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED style-src-attr must deny all inline/dynamic style attributes')
if font_tokens != ["'self'", 'data:']:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED font-src must be same-origin/data only')
if worker_tokens != ["'none'"]:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED unused worker capability must remain denied')
if manifest_tokens != ["'none'"]:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED unused manifest capability must remain denied')
for forbidden in ('cdnjs.cloudflare.com','unpkg.com','cdn.jsdelivr.net','cdn.tailwindcss.com','fonts.googleapis.com','fonts.gstatic.com'):
    if forbidden in csp:
        raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED retired external dependency remains in CSP: ' + forbidden)
if any(token.startswith(('https://', 'http://')) for tokens in (script_tokens, style_tokens, style_elem_tokens, font_tokens) for token in tokens):
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED external script/style/font source remains')
if connect_tokens != ["'self'"]:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED connect-src must remain same-origin only')
for name,tokens in (('img-src',img_tokens),('media-src',media_tokens)):
    if tokens != ["'self'",'data:','blob:']:
        raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED {name} must remain self/data/blob only')

print("VERCEL_SECURITY_HEADERS_TESTS_OK: csp=same-origin-script+style; script-attr=none; style-attr=none; unsafe-inline=absent; unsafe-eval=absent; worker=none; manifest=none; connect=self-only; img-media=self-data-blob; coop+corp=same-origin; robots=noindex+nofollow+noarchive")
