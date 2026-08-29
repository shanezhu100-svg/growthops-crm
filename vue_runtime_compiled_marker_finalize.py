from pathlib import Path
import hashlib
import os

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / 'dist' / 'vendor' / 'vue-3.5.41.renders.js'
EXPECTED_INPUT_SHA = 'd91a71ac97b904f27b0a4bf8527473e525ed311635eb1bdcd04ebf95c882658e'
EXPECTED_INPUT_BYTES = 1185796


def fail(message: str) -> None:
    raise SystemExit('VUE_RUNTIME_COMPILED_MARKER_FINALIZE_FAILED: ' + message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


if not REGISTRY.is_file():
    fail('render registry missing')
raw = REGISTRY.read_bytes()
if (digest(raw), len(raw)) != (EXPECTED_INPUT_SHA, EXPECTED_INPUT_BYTES):
    fail(
        'input registry drift; expected='
        f'{EXPECTED_INPUT_SHA}/{EXPECTED_INPUT_BYTES}B; actual={digest(raw)}/{len(raw)}B'
    )

text = raw.decode('utf-8')
needle = "  Object.defineProperty(globalThis, 'GrowthOpsVueRenders', {"
if text.count(needle) != 1:
    fail(f'global registry anchor count={text.count(needle)}')
if "'_rc'" in text or '"_rc"' in text:
    fail('runtime-compiled marker already present before compatibility finalize')

# Vue.compile() marks generated render functions with render._rc = true. Vue uses
# that marker to install RuntimeCompiledPublicInstanceProxyHandlers / withProxy.
# The deterministic registry extraction preserves the render source but loses that
# function-object metadata. Without it, missing template fields can escape the
# normal proxy as JavaScript free identifiers and throw ReferenceError during the
# first browser render. Restore the compiler-produced metadata, not app defaults.
marker = (
    "  for (const render of Object.values(renders)) {\n"
    "    Object.defineProperty(render, '_rc', { value: true, writable: false, configurable: false, enumerable: false });\n"
    "  }\n"
)
patched = text.replace(needle, marker + needle, 1)
if patched.count("Object.defineProperty(render, '_rc'") != 1:
    fail('compiled-render marker insertion drift')
for name in ('root', 'component01', 'component02', 'component03', 'component04'):
    if patched.count(name + ':') != 1:
        fail('render inventory drift: ' + name)
for forbidden in ('new Function(', 'eval('):
    if forbidden in patched:
        fail('dynamic code introduced: ' + forbidden)

out = patched.encode('utf-8')
tmp = REGISTRY.with_suffix(REGISTRY.suffix + '.tmp')
tmp.write_bytes(out)
os.replace(tmp, REGISTRY)

print(
    'VUE_RUNTIME_COMPILED_MARKER_FINALIZE_OK: '
    f'input={EXPECTED_INPUT_SHA}/{EXPECTED_INPUT_BYTES}B; '
    f'output={digest(out)}/{len(out)}B; renders=5; _rc=true; withProxy-semantics=restored'
)
