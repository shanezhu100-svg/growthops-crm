from pathlib import Path

ROOT = Path(__file__).resolve().parent
FINALIZER = (ROOT / 'fontawesome_static_finalize.py').read_text(encoding='utf-8')
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')

required = (
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css',
    '5ceaaba22d75b58e04150311f596306562a3e595e27ed4b1dfa451b82dda9e50',
    "'fa-brands-400.ttf': ('e28096fa75a96ac77020155ea3a6dd7312983e84115366d4cf49a0c312ec6d51', 209128)",
    "'fa-brands-400.woff2': ('232c6f6a7678304f9efaa26f30b1610debc2ba9f4cd636b5e6751c8d73761b92', 117852)",
    "'fa-regular-400.ttf': ('9174757efc83e072436e873c22be1663d3c103b0a16d7fb73569af4918d4d351', 67860)",
    "'fa-regular-400.woff2': ('c27da6f833431da5aa295c44540bfac0fd8270ba6a3c4346427006d8a7b34b76', 25392)",
    "'fa-solid-900.ttf': ('b4990d0d0c5f5d38d62e936eea120674e584c7eea8dcee38a975c0cf9a37539b', 420332)",
    "'fa-solid-900.woff2': ('ae17c16afbea216707b2203ea1cf9bdb45b9bfe47d0f4ae3258ddbc6294dd02f', 156400)",
    "'fa-v4compatibility.ttf': ('ff8f525fb050c5d24519ccc8f5723d85b2e51edd3f9bc6548af55aebadd4f269', 10832)",
    "'fa-v4compatibility.woff2': ('c7a869faca299d15be10a01f19d0765a7c4d46d8922d9b9317235c1e4a6f0982', 4792)",
    'from build_http_redirect_guard import NO_REDIRECT_OPENER, RedirectDenied',
    'with NO_REDIRECT_OPENER.open(request, timeout=90) as response:',
    'except RedirectDenied as exc:',
    'unexpected redirect denied before follow',
    'CSS webfont inventory drift',
    'Only after every network input has passed the complete digest inventory',
    'browser-cdnjs-fontawesome=removed',
    'redirects=pre-follow-denied',
    'DOWNLOAD_ATTEMPTS = 3',
    'for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):',
    'time.sleep(attempt)',
    'download failed after {DOWNLOAD_ATTEMPTS} attempts',
    'download-attempts<={DOWNLOAD_ATTEMPTS}',
)
missing = [marker for marker in required if marker not in FINALIZER]
if missing:
    raise SystemExit('FONTAWESOME_STATIC_POLICY_FAILED missing: ' + ', '.join(missing))
for forbidden in ('__PROBE__', 'latest', 'http://', 'urllib.request.urlopen('):
    if forbidden in FINALIZER:
        raise SystemExit('FONTAWESOME_STATIC_POLICY_FAILED forbidden marker: ' + forbidden)

retry_start = FINALIZER.index('for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):')
redirect_except = FINALIZER.index('except RedirectDenied as exc:', retry_start)
generic_except = FINALIZER.index('except Exception as exc:', redirect_except)
retry_return = FINALIZER.index('return response.read()', retry_start)
digest_check = FINALIZER.index('css_actual = sha256(css_bytes)', generic_except)
if not (retry_start < retry_return < redirect_except < generic_except < digest_check):
    raise SystemExit('FONTAWESOME_STATIC_POLICY_FAILED retry/redirect/validation order drift')
if FINALIZER.count('time.sleep(attempt)') != 1:
    raise SystemExit('FONTAWESOME_STATIC_POLICY_FAILED retry backoff count drift')

policy_call = 'python3 test_fontawesome_static_policy.py'
finalizer_call = 'python3 fontawesome_static_finalize.py'
output_call = 'python3 test_frontend_dependency_pin_output.py'
redirect_gate = 'python3 test_build_http_redirect_guard.py'
for call in (policy_call, finalizer_call, output_call, redirect_gate):
    if BUILD.count(call) != 1:
        raise SystemExit('FONTAWESOME_STATIC_POLICY_FAILED build call count: ' + call)
if not (BUILD.index(redirect_gate) < BUILD.index(policy_call) < BUILD.index(finalizer_call) < BUILD.index(output_call)):
    raise SystemExit('FONTAWESOME_STATIC_POLICY_FAILED build order drift')

print('FONTAWESOME_STATIC_POLICY_OK: version=6.5.2; css+8-webfonts=sha256+size-pinned; redirects=pre-follow-denied; transport-retries<=3; full-inventory-before-write; output=same-origin')
