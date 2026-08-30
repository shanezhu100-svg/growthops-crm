from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
VERCEL = json.loads((ROOT / 'vercel.json').read_text(encoding='utf-8'))
HEADERS = (ROOT / 'dist' / '_headers').read_text(encoding='utf-8')
VENDOR = (ROOT / 'frontend_vendor_static_finalize.py').read_text(encoding='utf-8')
RUNTIME = (ROOT / 'vue_runtime_only_finalize.py').read_text(encoding='utf-8')

IMMUTABLE = 'public, max-age=31536000, immutable'
EXPECTED = {
    '/vendor/vue-3.5.41.runtime.global.js': (
        '45c904194aaf24112c8f4fc4386b87e107a32eede80c410ce93be459ebdee088',
        'vue-3.5.41.runtime.global.js',
        RUNTIME,
    ),
    '/vendor/xlsx-0.18.5.full.min.js': (
        'c9506197caf809a075b6dee1da0d36fb19da7158ffe8a88e7b0c96c5d8623c99',
        'xlsx-0.18.5.full.min.js',
        VENDOR,
    ),
}

rules = VERCEL.get('headers', [])
catch_all = [r for r in rules if r.get('source') == '/(.*)']
if len(catch_all) != 1:
    raise SystemExit('STATIC_ASSET_CACHE_POLICY_FAILED catch-all rule drift')
catch_headers = {str(i.get('key') or '').lower(): str(i.get('value') or '') for i in catch_all[0].get('headers', [])}
if 'cache-control' in catch_headers:
    raise SystemExit('STATIC_ASSET_CACHE_POLICY_FAILED catch-all must not cache HTML/API')

static = [r for r in rules if r.get('source') != '/(.*)']
if {r.get('source') for r in static} != set(EXPECTED):
    raise SystemExit('STATIC_ASSET_CACHE_POLICY_FAILED immutable route inventory drift')

for source, (digest, filename, authority) in EXPECTED.items():
    if source.count(filename) != 1 or not source.startswith('/vendor/'):
        raise SystemExit('STATIC_ASSET_CACHE_POLICY_FAILED versioned vendor path drift: ' + source)
    if filename not in authority or digest not in authority:
        raise SystemExit('STATIC_ASSET_CACHE_POLICY_FAILED cache target is not tied to pinned build authority: ' + source)
    rule = next(r for r in static if r.get('source') == source)
    if rule.get('headers') != [{'key': 'Cache-Control', 'value': IMMUTABLE}]:
        raise SystemExit('STATIC_ASSET_CACHE_POLICY_FAILED cache value drift: ' + source)
    block = source + '\n  Cache-Control: ' + IMMUTABLE
    if HEADERS.count(block) != 1:
        raise SystemExit('STATIC_ASSET_CACHE_POLICY_FAILED Cloudflare cache parity drift: ' + source)

for forbidden in ('/api/', '/index.html', '/tailwind.css', '/app/', '/vendor/inter/', '/vendor/fontawesome/', 'vue-3.5.41.global.js', 'vue-3.5.41.renders.js'):
    if any(forbidden in str(r.get('source') or '') for r in static):
        raise SystemExit('STATIC_ASSET_CACHE_POLICY_FAILED mutable/retired surface cached immutably: ' + forbidden)

if not HEADERS.startswith('/*\n'):
    raise SystemExit('STATIC_ASSET_CACHE_POLICY_FAILED Cloudflare catch-all security rule not first')
if HEADERS.count('Cache-Control: ' + IMMUTABLE) != len(EXPECTED):
    raise SystemExit('STATIC_ASSET_CACHE_POLICY_FAILED unexpected immutable Cache-Control count')

print(
    'STATIC_ASSET_CACHE_POLICY_OK: immutable=vue-runtime-3.5.41+xlsx-0.18.5; '
    'render-registry+html+api+tailwind+app+fonts=not-immutable; vercel-cloudflare=parity'
)
