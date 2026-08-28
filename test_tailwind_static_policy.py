from pathlib import Path

ROOT = Path(__file__).resolve().parent
FINALIZER = (ROOT / 'tailwind_static_finalize.py').read_text(encoding='utf-8')
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')
INPUT = (ROOT / 'tailwind.input.css').read_text(encoding='utf-8')

required_finalizer_markers = (
    "VERSION = '3.4.17'",
    "tailwindcss-linux-x64",
    "7d24f7fa191d2193b78cd5f5a42a6093e14409521908529f42d80b11fde1f1d4",
    "tailwindcss-linux-arm64",
    "69b1378b8133192d7d2feb12a116fa12d035594f58db3eff215879e4ad8cf39b",
    "https://github.com/tailwindlabs/tailwindcss/releases/download/v{VERSION}/{asset_name}",
    "urllib.request.urlopen(request, timeout=90)",
    "if actual_sha != expected_sha:",
    "if sha256(tool) != expected_sha:",
    "--content",
    "--minify",
    "PLAY_TAG",
    "STATIC_TAG",
    "https://cdn.tailwindcss.com",
    "/tailwind.css",
)
missing = [marker for marker in required_finalizer_markers if marker not in FINALIZER]
if missing:
    raise SystemExit('TAILWIND_STATIC_POLICY_FAILED: finalizer policy marker missing: ' + ', '.join(missing))

for forbidden in ('releases/latest/', 'tailwindcss@latest', 'npx tailwindcss', 'npm install tailwindcss'):
    if forbidden in FINALIZER:
        raise SystemExit('TAILWIND_STATIC_POLICY_FAILED: floating/unlocked Tailwind install path: ' + forbidden)

expected_input = '@tailwind base;\n@tailwind components;\n@tailwind utilities;\n'
if INPUT != expected_input:
    raise SystemExit('TAILWIND_STATIC_POLICY_FAILED: tailwind.input.css drift')

policy_call = 'python3 test_tailwind_static_policy.py'
finalizer_call = 'python3 tailwind_static_finalize.py'
output_gate_call = 'python3 test_frontend_dependency_pin_output.py'
pin_call = 'python3 frontend_dependency_pin_finalize.py'
for call in (policy_call, finalizer_call, output_gate_call, pin_call):
    if BUILD.count(call) != 1:
        raise SystemExit('TAILWIND_STATIC_POLICY_FAILED: build call must appear exactly once: ' + call)
if not (BUILD.index(pin_call) < BUILD.index(policy_call) < BUILD.index(finalizer_call) < BUILD.index(output_gate_call)):
    raise SystemExit('TAILWIND_STATIC_POLICY_FAILED: static Tailwind build order drift')

print('TAILWIND_STATIC_POLICY_OK: version=3.4.17; linux=x64+arm64-sha256-pinned; npm-tree=absent; build-order=pin>policy>compile>output-gate')
