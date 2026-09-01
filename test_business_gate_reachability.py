from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
BUILD = (ROOT / 'build.sh').read_text(encoding='utf-8')

BUSINESS_FILES = {path.name: path for path in ROOT.glob('test_business_*.mjs')}
if not BUSINESS_FILES:
    raise SystemExit('BUSINESS_GATE_REACHABILITY_FAILED: no test_business_*.mjs files found')

root_re = re.compile(r'^node\s+(test_business_[^\s]+\.mjs)\s*$', re.MULTILINE)
roots = root_re.findall(BUILD)
if not roots:
    raise SystemExit('BUSINESS_GATE_REACHABILITY_FAILED: build.sh has no direct business-test roots')

missing_roots = sorted(set(roots) - set(BUSINESS_FILES))
if missing_roots:
    raise SystemExit('BUSINESS_GATE_REACHABILITY_FAILED: build roots missing from repository: ' + ', '.join(missing_roots))

# Business regressions use both dynamic chaining (`await import('./...')`) and
# standard ESM side-effect imports (`import './...'`). Treat both as executable
# reachability edges. Restrict parsing to same-directory test_business_*.mjs paths
# so unrelated package imports cannot accidentally satisfy this gate.
dynamic_import_re = re.compile(
    r"(?:await\s+)?import\(\s*['\"]\./(test_business_[^'\"]+\.mjs)['\"]\s*\)"
)
static_import_re = re.compile(
    r"(?:^|\n)\s*import(?:\s+[^'\"\n]+?\s+from\s+)?\s*['\"]\./(test_business_[^'\"]+\.mjs)['\"]\s*;?",
    re.MULTILINE,
)

edges = {}
unknown_imports = set()
for name, path in BUSINESS_FILES.items():
    text = path.read_text(encoding='utf-8')
    imports = dynamic_import_re.findall(text) + static_import_re.findall(text)
    # Preserve deterministic graph behavior while avoiding duplicate edges when a
    # file happens to reference the same child through more than one syntax form.
    imports = list(dict.fromkeys(imports))
    edges[name] = imports
    unknown_imports.update(item for item in imports if item not in BUSINESS_FILES)

if unknown_imports:
    raise SystemExit(
        'BUSINESS_GATE_REACHABILITY_FAILED: business-test imports missing files: '
        + ', '.join(sorted(unknown_imports))
    )

reachable = set()
stack = list(roots)
while stack:
    name = stack.pop()
    if name in reachable:
        continue
    reachable.add(name)
    stack.extend(edges.get(name, ()))

unreachable = sorted(set(BUSINESS_FILES) - reachable)
if unreachable:
    raise SystemExit(
        'BUSINESS_GATE_REACHABILITY_FAILED: business tests not reachable from required build roots: '
        + ', '.join(unreachable)
    )

print(
    'BUSINESS_GATE_REACHABILITY_OK: '
    f'roots={len(roots)}; business-tests={len(BUSINESS_FILES)}; reachable={len(reachable)}; '
    'imports=static+dynamic; unreachable=0'
)
