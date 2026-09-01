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
if len(roots) != len(set(roots)):
    raise SystemExit('BUSINESS_GATE_REACHABILITY_FAILED: duplicate direct business-test root')

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

texts = {}
edges = {}
unknown_imports = set()
for name, path in BUSINESS_FILES.items():
    text = path.read_text(encoding='utf-8')
    texts[name] = text
    imports = dynamic_import_re.findall(text) + static_import_re.findall(text)
    imports = list(dict.fromkeys(imports))
    edges[name] = imports
    unknown_imports.update(item for item in imports if item not in BUSINESS_FILES)

if unknown_imports:
    raise SystemExit(
        'BUSINESS_GATE_REACHABILITY_FAILED: business-test imports missing files: '
        + ', '.join(sorted(unknown_imports))
    )


def descendants(start):
    seen = set()
    stack = list(edges.get(start, ()))
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        stack.extend(edges.get(name, ()))
    return seen

# Direct roots should be an antichain: if root B is already reachable through root A,
# invoking B separately only repeats assertions and lengthens the protected build.
redundant_roots = []
for root in roots:
    covered_by = [other for other in roots if other != root and root in descendants(other)]
    if covered_by:
        redundant_roots.append(f"{root}<-{','.join(sorted(covered_by))}")
if redundant_roots:
    raise SystemExit(
        'BUSINESS_GATE_REACHABILITY_FAILED: redundant direct business-test roots: '
        + '; '.join(sorted(redundant_roots))
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

# Provenance gate: a permanent business regression must either execute shipped JS
# from dist/ or be a pure import shim/aggregator whose children do. This prevents a
# self-contained reimplementation of product logic from going green while the actual
# deployed CRM code has drifted.
block_comment_re = re.compile(r'/\*.*?\*/', re.DOTALL)
line_comment_re = re.compile(r'//[^\n]*')
static_import_stmt_re = re.compile(
    r"(?:^|\n)\s*import(?:\s+[^'\"\n]+?\s+from\s+)?\s*['\"]\./test_business_[^'\"]+\.mjs['\"]\s*;?",
    re.MULTILINE,
)
dynamic_import_stmt_re = re.compile(
    r"(?:await\s+)?import\(\s*['\"]\./test_business_[^'\"]+\.mjs['\"]\s*\)\s*;?"
)

runtime_backed = []
pure_shims = []
invalid_provenance = []
for name, text in texts.items():
    # Most tests enumerate final app-inline-* JS under dist/app. A small number
    # execute another deployed JS artifact (for example cloud-security-hotfix.js).
    # Accept the latter only when the file is read from dist and then executed in a
    # VM, not merely mentioned or inspected as text.
    has_dist_app = bool(re.search(r"['\"]dist['\"]\s*,\s*['\"]app['\"]|dist/app", text))
    has_app_inline = 'app-inline-' in text
    app_bundle_backed = has_dist_app and has_app_inline

    has_dist_path = bool(re.search(r"path\.join\(\s*process\.cwd\(\)\s*,\s*['\"]dist['\"]", text))
    reads_dist_js = has_dist_path and 'fs.readFileSync' in text
    executes_dist_js = reads_dist_js and ('vm.runInNewContext' in text or 'vm.runInContext' in text)

    if app_bundle_backed or executes_dist_js:
        runtime_backed.append(name)
        continue

    # A shim may contain comments plus local business-test import statements only.
    # It must actually import at least one child so an empty file cannot count as a
    # protected test. Strip comments/imports and require no executable residue.
    if not edges.get(name):
        invalid_provenance.append(name)
        continue
    residue = block_comment_re.sub('', text)
    residue = line_comment_re.sub('', residue)
    residue = static_import_stmt_re.sub('\n', residue)
    residue = dynamic_import_stmt_re.sub('', residue)
    residue = re.sub(r'[;\s]+', '', residue)
    if residue:
        invalid_provenance.append(name)
    else:
        pure_shims.append(name)

if invalid_provenance:
    raise SystemExit(
        'BUSINESS_GATE_REACHABILITY_FAILED: business tests are neither executed-shipped-runtime-backed nor pure import shims: '
        + ', '.join(sorted(invalid_provenance))
    )
if len(runtime_backed) + len(pure_shims) != len(BUSINESS_FILES):
    raise SystemExit('BUSINESS_GATE_REACHABILITY_FAILED: provenance accounting mismatch')

print(
    'BUSINESS_GATE_REACHABILITY_OK: '
    f'roots={len(roots)}; business-tests={len(BUSINESS_FILES)}; reachable={len(reachable)}; '
    'imports=static+dynamic; redundant-roots=0; unreachable=0; '
    f'runtime-backed={len(runtime_backed)}; pure-shims={len(pure_shims)}; provenance=guarded'
)
