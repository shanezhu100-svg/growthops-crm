from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
VERCEL_CONFIG = ROOT / 'vercel.json'
OUTPUT = ROOT / 'dist' / '_headers'
CLOUDFLARE_FUNCTION = ROOT / 'functions' / 'api' / 'crm.js'

IMMUTABLE_CACHE = 'public, max-age=31536000, immutable'
EXPECTED_STATIC_RULES = {
    '/vendor/vue-3.5.41.global.js': IMMUTABLE_CACHE,
    '/vendor/xlsx-0.18.5.full.min.js': IMMUTABLE_CACHE,
}

cfg = json.loads(VERCEL_CONFIG.read_text(encoding='utf-8'))
all_rules = cfg.get('headers', [])
catch_all = [rule for rule in all_rules if rule.get('source') == '/(.*)']
if len(catch_all) != 1:
    raise SystemExit(f'CLOUDFLARE_SECURITY_HEADERS_FAILED expected one Vercel catch-all rule, found {len(catch_all)}')

items = catch_all[0].get('headers', [])
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

static_rules = [rule for rule in all_rules if rule.get('source') != '/(.*)']
actual_sources = {str(rule.get('source') or '') for rule in static_rules}
if actual_sources != set(EXPECTED_STATIC_RULES):
    raise SystemExit('CLOUDFLARE_SECURITY_HEADERS_FAILED unexpected static header rule inventory')
for source in sorted(EXPECTED_STATIC_RULES):
    matching = [rule for rule in static_rules if rule.get('source') == source]
    if len(matching) != 1:
        raise SystemExit(f'CLOUDFLARE_SECURITY_HEADERS_FAILED static rule count {source}')
    static_items = matching[0].get('headers', [])
    if static_items != [{'key': 'Cache-Control', 'value': EXPECTED_STATIC_RULES[source]}]:
        raise SystemExit(f'CLOUDFLARE_SECURITY_HEADERS_FAILED unsafe static cache policy {source}')
    lines.extend(['', source, f'  Cache-Control: {EXPECTED_STATIC_RULES[source]}'])

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
    'cross-origin-resource-policy',
    'permissions-policy',
    'x-robots-tag',
    'content-security-policy',
}
missing = sorted(required - seen)
if missing:
    raise SystemExit(f'CLOUDFLARE_SECURITY_HEADERS_FAILED missing {",".join(missing)}')
if 'cache-control' in seen:
    raise SystemExit('CLOUDFLARE_SECURITY_HEADERS_FAILED catch-all must not cache HTML/API immutably')

function_source = CLOUDFLARE_FUNCTION.read_text(encoding='utf-8')
if '...SECURITY_HEADERS' not in function_source:
    raise SystemExit('CLOUDFLARE_SECURITY_HEADERS_FAILED Function does not apply SECURITY_HEADERS')
start_marker = 'const SECURITY_HEADERS = Object.freeze({\n'
end_marker = '});\n\nconst PUBLIC_RPCS'
if function_source.count(start_marker) != 1 or function_source.count(end_marker) != 1:
    raise SystemExit('CLOUDFLARE_SECURITY_HEADERS_FAILED unexpected Function SECURITY_HEADERS structure')
start = function_source.index(start_marker)
end = function_source.index(end_marker, start)
rendered_lines = [f'  {json.dumps(key)}: {json.dumps(value)},' for key, value in normalized]
rendered_block = start_marker + '\n'.join(rendered_lines) + '\n'
function_source = function_source[:start] + rendered_block + function_source[end:]
CLOUDFLARE_FUNCTION.write_text(function_source, encoding='utf-8')

function_source = CLOUDFLARE_FUNCTION.read_text(encoding='utf-8')
block_start = function_source.index(start_marker)
block_end = function_source.index(end_marker, block_start)
security_block = function_source[block_start:block_end]
for key, value in normalized:
    expected = f'  {json.dumps(key)}: {json.dumps(value)},'
    if security_block.count(expected) != 1:
        raise SystemExit(f'CLOUDFLARE_SECURITY_HEADERS_FAILED Function parity mismatch {key}')
if security_block.count('\n  "') != len(normalized):
    raise SystemExit('CLOUDFLARE_SECURITY_HEADERS_FAILED unexpected Function security-header member count')
if 'Cache-Control' in security_block or 'immutable' in security_block:
    raise SystemExit('CLOUDFLARE_SECURITY_HEADERS_FAILED immutable cache leaked into Function security headers')

print(
    f'CLOUDFLARE_SECURITY_HEADERS_OK: source=vercel.json; static-rule=/*; headers={len(items)}; '
    f'immutable-static-rules={len(EXPECTED_STATIC_RULES)}; output=dist/_headers; '
    'function=/api/crm-generated; parity=exact; api-cache=unchanged'
)
