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
expected_script_src = "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
expected_style_src = (
    "style-src 'self' 'unsafe-inline' "
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css '
    'https://fonts.googleapis.com/css2'
)
expected_font_src = (
    "font-src 'self' data: "
    'https://fonts.gstatic.com/s/inter/ '
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/webfonts/'
)
for directive in (
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "frame-src 'none'",
    "form-action 'self'",
    "connect-src 'self'",
    expected_script_src,
    expected_style_src,
    expected_font_src,
    "img-src 'self' data: blob:",
    "media-src 'self' data: blob:",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    'upgrade-insecure-requests',
):
    if directive not in csp:
        raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED csp {directive}')

# Transitional CSP: the current Vue global build still compiles templates in-browser
# and the application still ships an inline controller, so unsafe-eval/unsafe-inline
# remain temporarily required. Vue and XLSX are now verified build-time inputs served
# from same-origin paths, so script-src must have no external network sources at all.
def directive_tokens(name):
    part=csp.split(name+' ',1)[1].split(';',1)[0]
    return [token for token in part.split() if token]

script_tokens=directive_tokens('script-src')
style_tokens=directive_tokens('style-src')
font_tokens=directive_tokens('font-src')
connect_tokens=directive_tokens('connect-src')
img_tokens=directive_tokens('img-src')
media_tokens=directive_tokens('media-src')
if any('*' in tokens for tokens in (script_tokens, style_tokens, font_tokens, connect_tokens, img_tokens, media_tokens)):
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED CSP wildcard source')
if any(source in tokens for tokens in (script_tokens, style_tokens, font_tokens) for source in ('https:', 'http:')):
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED broad scheme source')
if script_tokens != ["'self'", "'unsafe-inline'", "'unsafe-eval'"]:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED script-src must be same-origin plus transitional inline/eval only')
if any(token.startswith('http://') or token.startswith('https://') for token in script_tokens):
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED external browser script source remains')
for forbidden_host in ('unpkg.com', 'cdn.jsdelivr.net', 'cdn.tailwindcss.com'):
    if forbidden_host in csp.split('script-src ',1)[1].split(';',1)[0]:
        raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED external script host remains: ' + forbidden_host)

expected_external_styles = {
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css',
    'https://fonts.googleapis.com/css2',
}
actual_external_styles = {token for token in style_tokens if token.startswith('https://')}
if actual_external_styles != expected_external_styles:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED exact third-party style path allowlist drift')
expected_external_fonts = {
    'https://fonts.gstatic.com/s/inter/',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/webfonts/',
}
actual_external_fonts = {token for token in font_tokens if token.startswith('https://')}
if actual_external_fonts != expected_external_fonts or "'self'" not in font_tokens or 'data:' not in font_tokens:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED third-party font path allowlist drift')
if connect_tokens != ["'self'"]:
    raise SystemExit('VERCEL_SECURITY_HEADERS_TESTS_FAILED connect-src must remain same-origin only')
for name,tokens in (('img-src',img_tokens),('media-src',media_tokens)):
    if 'https:' in tokens or 'http:' in tokens:
        raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED {name} external scheme exfiltration path')
    if tokens != ["'self'",'data:','blob:']:
        raise SystemExit(f'VERCEL_SECURITY_HEADERS_TESTS_FAILED {name} must remain self/data/blob only')

print('VERCEL_SECURITY_HEADERS_TESTS_OK: csp=same-origin-browser-js+exact-style+font-path-allowlist; connect=self-only; img-media=self-data-blob; vue-inline-compat=true')
