from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
VERCEL_CONFIG = ROOT / 'vercel.json'
OUTPUT = ROOT / 'dist' / '_headers'
CLOUDFLARE_FUNCTION = ROOT / 'functions' / 'api' / 'crm.js'

cfg = json.loads(VERCEL_CONFIG.read_text(encoding='utf-8'))
rules = [rule for rule in cfg.get('headers', []) if rule.get('source') == '/(.*)']
if len(rules) != 1:
    raise SystemExit(f'CLOUDFLARE_SECURITY_HEADERS_FAILED expected one Vercel catch-all rule, found {len(rules)}')

items = rules[0].get('headers', [])
if not isinstance(items, list) or not items:
    raise SystemExit('CLOUDFLARE_SECURITY_HEADERS_FAILED empty Vercel catch-all headers')

seen = set()
lines = ['/*']
normalized = []
for item in items:
    key = str(item.get('key') or '').strip()
    value = str(item.get('value') or '').strip()
    if not key or not value:
        raise SystemExit('CLOUDFLARE_SECURITY_HEADERS_FAILED blank header key/value')
    if key.lower() in seen:
        raise SystemExit(f'CLOUDFLARE_SECURITY_HEADERS_FAILED duplicate header {key}')
    if any(ch in key or ch in value for ch in ('\r', '\n')):
        raise SystemExit(f'CLOUDFLARE_SECURITY_HEADERS_FAILED newline in {key}')
    seen.add(key.lower())
    normalized.append((key, value))
    line = f'  {key}: {value}'
    if len(line) > 2000:
        raise SystemExit(f'CLOUDFLARE_SECURITY_HEADERS_FAILED Cloudflare line limit exceeded by {key}')
    lines.append(line)

# Keep the Cloudflare static surface locked to the same policy already validated
# for Vercel. Pages parses this file from the build output and does not serve it.
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
text = '\n'.join(lines) + '\n'
OUTPUT.write_text(text, encoding='utf-8')
if OUTPUT.read_text(encoding='utf-8') != text:
    raise SystemExit('CLOUDFLARE_SECURITY_HEADERS_FAILED output verification')

required = {
    'x-content-type-options',
    'referrer-policy',
    'x-frame-options',
    'x-permitted-cross-domain-policies',
    'cross-origin-opener-policy',
    'permissions-policy',
    'content-security-policy',
}
missing = sorted(required - seen)
if missing:
    raise SystemExit(f'CLOUDFLARE_SECURITY_HEADERS_FAILED missing {",".join(missing)}')

# `_headers` only applies to static Pages assets. Keep the Pages Function response
# policy exactly aligned with the same Vercel source-of-truth as well. The JS
# object intentionally uses JSON-compatible double-quoted key/value lines so this
# build gate can compare every value without maintaining a second expected policy.
function_source = CLOUDFLARE_FUNCTION.read_text(encoding='utf-8')
if '...SECURITY_HEADERS' not in function_source:
    raise SystemExit('CLOUDFLARE_SECURITY_HEADERS_FAILED Function does not apply SECURITY_HEADERS')
for key, value in normalized:
    expected = f'  {json.dumps(key)}: {json.dumps(value)},'
    if expected not in function_source:
        raise SystemExit(f'CLOUDFLARE_SECURITY_HEADERS_FAILED Function parity mismatch {key}')

print(f'CLOUDFLARE_SECURITY_HEADERS_OK: source=vercel.json; static-rule=/*; headers={len(items)}; output=dist/_headers; function=/api/crm; parity=exact')
