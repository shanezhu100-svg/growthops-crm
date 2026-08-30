from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / 'dist' / 'vendor' / 'vue-3.5.41.renders.js'
RUNTIME = ROOT / 'dist' / 'vendor' / 'vue-3.5.41.runtime.global.js'
COMPILER = ROOT / 'dist' / 'vendor' / 'vue-3.5.41.global.js'

if not REGISTRY.is_file() or not RUNTIME.is_file():
    raise SystemExit('VUE_RUNTIME_CUTOVER_PIN_PROBE_FAILED: runtime/registry artifact missing')
if COMPILER.exists():
    raise SystemExit('VUE_RUNTIME_CUTOVER_PIN_PROBE_FAILED: compiler-inclusive browser asset remains')
raw = REGISTRY.read_bytes()
sha = hashlib.sha256(raw).hexdigest()
if b"Object.defineProperty(render, '_rc'" not in raw:
    raise SystemExit('VUE_RUNTIME_CUTOVER_PIN_PROBE_FAILED: compiled render _rc marker missing')
raise SystemExit(f'VUE_RUNTIME_CUTOVER_PIN_REQUIRED: registry={sha}/{len(raw)}B')
