from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / 'dist' / 'vendor' / 'vue-3.5.41.renders.js'
EXPECTED_INPUT_SHA = 'e50a51bb875e00f90a17c2e01cbf3dfa696472e367cfc017060195e59f69360e'
EXPECTED_INPUT_BYTES = 1196227
EXPECTED_OUTPUT_SHA = '896bc00c2e838461732874d04c713907b3bf5c04f60d85257b50d83b288f66ea'
EXPECTED_OUTPUT_BYTES = 1198056

# Vue 3.5.41 packages/shared/src/globalsAllowList.ts. Runtime-compiled templates
# deliberately do not capture these JavaScript globals through the component proxy.
GLOBALS_ALLOWED = (
    'Infinity', 'undefined', 'NaN', 'isFinite', 'isNaN', 'parseFloat', 'parseInt',
    'decodeURI', 'decodeURIComponent', 'encodeURI', 'encodeURIComponent', 'Math',
    'Number', 'Date', 'Array', 'Object', 'Boolean', 'String', 'RegExp', 'Map', 'Set',
    'JSON', 'Intl', 'BigInt', 'console', 'Error', 'Symbol',
)
RENDER_NAMES = ('root', 'component01', 'component02', 'component03', 'component04')


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
open_anchor = '  const renders = Object.freeze({'
tail_anchor = "  });\n  Object.defineProperty(globalThis, 'GrowthOpsVueRenders', {"
if text.count(open_anchor) != 1:
    fail(f'raw registry opening anchor count={text.count(open_anchor)}')
if text.count(tail_anchor) != 1:
    fail(f'raw registry tail anchor count={text.count(tail_anchor)}')
if 'RuntimeCompiledProxy' in text or "'_rc'" in text or '"_rc"' in text:
    fail('runtime-compiled compatibility layer already present before finalize')

globals_json = json.dumps(list(GLOBALS_ALLOWED), separators=(',', ':'))
compat_lines = [
    '  });',
    f'  const __GrowthOpsVueRuntimeGlobals = new Set({globals_json});',
    '  const __GrowthOpsVueWithProxyCache = new WeakMap();',
    '  const __GrowthOpsVueRuntimeCompiledProxyHandlers = Object.freeze({',
    '    has(target, key) {',
    "      if (typeof key !== 'string') return Reflect.has(target, key);",
    "      return key[0] !== '_' && !__GrowthOpsVueRuntimeGlobals.has(key);",
    '    },',
    '    get(target, key) {',
    '      if (key === Symbol.unscopables) return undefined;',
    '      return Reflect.get(target, key, target);',
    '    }',
    '  });',
    '  function __GrowthOpsVueWrapRuntimeCompiled(render) {',
    '    const wrapped = function (...args) {',
    '      const ctx = args[0];',
    "      if ((typeof ctx === 'object' && ctx !== null) || typeof ctx === 'function') {",
    '        let withProxy = __GrowthOpsVueWithProxyCache.get(ctx);',
    '        if (!withProxy) {',
    '          withProxy = new Proxy(ctx, __GrowthOpsVueRuntimeCompiledProxyHandlers);',
    '          __GrowthOpsVueWithProxyCache.set(ctx, withProxy);',
    '        }',
    '        args[0] = withProxy;',
    '      }',
    '      return render.apply(this, args);',
    '    };',
    "    Object.defineProperty(wrapped, '_rc', { value: true, writable: false, configurable: false, enumerable: false });",
    '    return wrapped;',
    '  }',
    '  const renders = Object.freeze({',
]
for idx, name in enumerate(RENDER_NAMES):
    comma = ',' if idx + 1 < len(RENDER_NAMES) else ''
    compat_lines.append(f'    {name}: __GrowthOpsVueWrapRuntimeCompiled(rawRenders.{name}){comma}')
compat_lines.extend([
    '  });',
    "  Object.defineProperty(globalThis, 'GrowthOpsVueRenders', {",
])

patched = text.replace(open_anchor, '  const rawRenders = Object.freeze({', 1)
patched = patched.replace(tail_anchor, '\n'.join(compat_lines), 1)
if patched.count('__GrowthOpsVueWrapRuntimeCompiled') != len(RENDER_NAMES) + 1:
    fail('runtime-compiled wrapper inventory drift')
if patched.count("Object.defineProperty(wrapped, '_rc'") != 1:
    fail('compiled-render _rc compatibility marker drift')
for name in RENDER_NAMES:
    if patched.count(name + ':') < 2:
        fail('raw/wrapped render inventory drift: ' + name)
for forbidden in ('new Function(', 'eval('):
    if forbidden in patched:
        fail('dynamic code introduced: ' + forbidden)

out = patched.encode('utf-8')
out_sha = digest(out)
if (out_sha, len(out)) != (EXPECTED_OUTPUT_SHA, EXPECTED_OUTPUT_BYTES):
    fail(
        'compatibility registry drift; expected='
        f'{EXPECTED_OUTPUT_SHA}/{EXPECTED_OUTPUT_BYTES}B; actual={out_sha}/{len(out)}B'
    )

tmp = REGISTRY.with_suffix(REGISTRY.suffix + '.tmp')
tmp.write_bytes(out)
os.replace(tmp, REGISTRY)

print(
    'VUE_RUNTIME_COMPILED_MARKER_FINALIZE_OK: '
    f'input={EXPECTED_INPUT_SHA}/{EXPECTED_INPUT_BYTES}B; '
    f'output={out_sha}/{len(out)}B; renders=5; _rc=true; '
    'runtime-compiled-proxy=vue-3.5.41-compatible; withProxy-cache=weakmap; dynamic-code=0'
)

import finance_company_cost_summary_finalize  # noqa: E402,F401
