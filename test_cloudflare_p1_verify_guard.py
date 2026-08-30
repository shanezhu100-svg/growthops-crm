from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERIFY = (ROOT / 'cloudflare_p1_verify.py').read_text(encoding='utf-8')
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')

EXPECTED_PINS = {
    'index.html': '1ce7157cca79306d6dbef736e090e0c15d389f3031c15ac3db0b98f5285c13ac',
    'tailwind.css': '082358f4ff9c6d67ccb8e628ed27669967e15cfa7908f2e4c36a1e89c0a3f7b6',
    'app/app-inline-01.js': '52ade14219e58afb7b9f4535440479add87f8a59a0404e7fe504cfde5f06c53e',
    'app/app-inline-02.js': 'dfb07b154ec1ab7c540dbf044164a0ea7445dee996f859504d22f673d247f26b',
    'app/app-inline-03.js': '46d7a47b04004fe2470194e9a24cbed7df7eca62cff1fb2e5266305934504aa1',
    'app/app-style-01.css': '33a4a117d6b9e820b389e09d87a4ccb94242fb043e80ea087f72c17f46861a70',
    'app/app-style-02.css': '01ed16d03067a8879b877440574fbc6d98af53e0909685e1a23271169c149997',
    'app/app-style-03.css': '64bd5db676657f40c7962080ce62f3b74125865c3f084a67ce21d0fc77ed00b6',
    'app/app-style-04.css': '59de39d8388f561c5229cfa39f7d4c5299b34997c21e3c142d9ced067850a11e',
    'vendor/vue-3.5.41.runtime.global.js': '45c904194aaf24112c8f4fc4386b87e107a32eede80c410ce93be459ebdee088',
    'vendor/vue-3.5.41.renders.js': 'a958722d8a7ddbe16c0533f6f463c91f011f2595c3a59b267ff1ddbc39fcf2ee',
    'vendor/xlsx-0.18.5.full.min.js': 'c9506197caf809a075b6dee1da0d36fb19da7158ffe8a88e7b0c96c5d8623c99',
    'vendor/fontawesome/css/all.min.css': '5ceaaba22d75b58e04150311f596306562a3e595e27ed4b1dfa451b82dda9e50',
    'vendor/fontawesome/webfonts/fa-brands-400.ttf': 'e28096fa75a96ac77020155ea3a6dd7312983e84115366d4cf49a0c312ec6d51',
    'vendor/fontawesome/webfonts/fa-brands-400.woff2': '232c6f6a7678304f9efaa26f30b1610debc2ba9f4cd636b5e6751c8d73761b92',
    'vendor/fontawesome/webfonts/fa-regular-400.ttf': '9174757efc83e072436e873c22be1663d3c103b0a16d7fb73569af4918d4d351',
    'vendor/fontawesome/webfonts/fa-regular-400.woff2': 'c27da6f833431da5aa295c44540bfac0fd8270ba6a3c4346427006d8a7b34b76',
    'vendor/fontawesome/webfonts/fa-solid-900.ttf': 'b4990d0d0c5f5d38d62e936eea120674e584c7eea8dcee38a975c0cf9a37539b',
    'vendor/fontawesome/webfonts/fa-solid-900.woff2': 'ae17c16afbea216707b2203ea1cf9bdb45b9bfe47d0f4ae3258ddbc6294dd02f',
    'vendor/fontawesome/webfonts/fa-v4compatibility.ttf': 'ff8f525fb050c5d24519ccc8f5723d85b2e51edd3f9bc6548af55aebadd4f269',
    'vendor/fontawesome/webfonts/fa-v4compatibility.woff2': 'c7a869faca299d15be10a01f19d0765a7c4d46d8922d9b9317235c1e4a6f0982',
    'vendor/inter/inter.css': 'a9173515531a1bb9820b2adce8e7df7a3cb3b4d114894f836c74ed0fdcafc144',
    'vendor/inter/inter-latin.woff2': '3100e775e8616cd2611beecfa23a4263d7037586789b43f035236a2e6fbd4c62',
    'vendor/inter/inter-latin-ext.woff2': '34b9c504cab7a73e37b746343a449132e56cf7b5481af2cb81dc74dcff25c956',
    'cloud-adapter.js': '9713943a80008f625000d6fac2440fb9395f9e6e2c1fd09e820a399c5c34379f',
    'cloud-security-hotfix.js': 'befa849b6b631453aeb5090608665c3cebb72d2a9aa75ed0c1942d4f22809863',
    'cloud-p1-overrides.js': 'e50e05322a0d56e78bf112a52be08ff54263f4ce88cb0b9b91f6613722b8ccab',
    'cloud-ui-action-bridge.js': '017fe2b8c575353af5f01b6760d26598bf038eff95bd58d56c5901942b1be0fe',
}
for name, digest in EXPECTED_PINS.items():
    marker = repr(name) + ': ' + repr(digest)
    if marker not in VERIFY:
        raise SystemExit('CLOUDFLARE_P1_VERIFY_GUARD_TEST_FAILED production pin drift: ' + name)

# The runtime-only migration is a removal boundary. Guard the final verifier itself
# so an old compiler-inclusive Vue asset cannot silently return outside the pin map.
required_verify_markers = (
    "DIST / '404.html'", "DIST / '_headers'", "headers.startswith('/*\\n')",
    "DIST / 'vendor' / 'vue-3.5.41.global.js'",
    'compiler-inclusive Vue asset returned after runtime-only cutover',
    'Content-Security-Policy:', 'X-Frame-Options:', 'X-Content-Type-Options:',
    'Referrer-Policy:', 'Permissions-Policy:', 'Cross-Origin-Opener-Policy:',
    'Cross-Origin-Resource-Policy: same-origin',
    'X-Robots-Tag: noindex, nofollow, noarchive',
    'noindex,nofollow,noarchive', "'<script'", "'<form'", "'<iframe'", "'fetch('",
    "'xmlhttprequest'", '/api/crm', 'sb_secret_', 'growthops_supabase', 'document.cookie',
    'localstorage', 'sessionstorage', "re.search(r'\\b(?:src|href|action)\\s*='",
    'same-origin-app-js=hash-pinned', 'same-origin-app-css=hash-pinned',
    'same-origin-vendor-js=hash-pinned', 'vue-runtime-only+renders=hash-pinned',
    'vue-compiler=absent', 'same-origin-fontawesome=hash-pinned', 'same-origin-inter=hash-pinned',
    'corp=same-origin', 'robots=noindex+nofollow+noarchive', 'failopen_404=guarded', 'static_headers=guarded',
)
missing = [marker for marker in required_verify_markers if marker not in VERIFY]
if missing:
    raise SystemExit('CLOUDFLARE_P1_VERIFY_GUARD_TEST_FAILED verifier coverage missing: ' + ', '.join(missing))

if 'vendor/vue-3.5.41.global.js' in EXPECTED_PINS:
    raise SystemExit('CLOUDFLARE_P1_VERIFY_GUARD_TEST_FAILED compiler-inclusive Vue remains accepted')
if 'vendor/vue-3.5.41.runtime.global.js' not in EXPECTED_PINS or 'vendor/vue-3.5.41.renders.js' not in EXPECTED_PINS:
    raise SystemExit('CLOUDFLARE_P1_VERIFY_GUARD_TEST_FAILED runtime-only Vue artifacts not both pinned')

call = 'python3 test_cloudflare_p1_verify_guard.py'
if BUILD.count(call) != 1:
    raise SystemExit('CLOUDFLARE_P1_VERIFY_GUARD_TEST_FAILED static verifier gate not wired exactly once')
if BUILD.index(call) < BUILD.index('python3 test_cloudflare_failopen_404.py'):
    raise SystemExit('CLOUDFLARE_P1_VERIFY_GUARD_TEST_FAILED verifier gate runs before 404 build test')

print('CLOUDFLARE_P1_VERIFY_GUARD_TESTS_OK: production-pins=28-synchronized; static-tailwind+app-js+app-css+vendor-js+vue-runtime-only+renders+fontawesome+inter=hash-pinned; vue-compiler=forbidden; browser-mount-gate=required; final-404-check=required; wildcard-static-headers=8-required; corp=same-origin; robots=noindex+nofollow+noarchive; active-material-deny=required')
