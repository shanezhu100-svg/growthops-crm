from pathlib import Path
import hashlib
import html as html_module
import os
import re

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
APP_DIR = DIST / 'app'

SCRIPT_RE = re.compile(r'<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>', re.IGNORECASE | re.DOTALL)
SRC_RE = re.compile(r'\bsrc\s*=', re.IGNORECASE)
TYPE_RE = re.compile(r'\btype\s*=\s*(["\'])(.*?)\1', re.IGNORECASE | re.DOTALL)
ID_RE = re.compile(r'\bid\s*=\s*(["\'])(.*?)\1', re.IGNORECASE | re.DOTALL)
ATTR_NAME_RE = re.compile(r'([:@A-Za-z_][:\-\.\w]*)\s*(?:=|$)')
EXPECTED_INLINE_COUNT = 3
REVIEWED_SINGLETON_IDS = {
    'growthops-session-restore-guard',
    'growthops-credential-ui-v5-preboot',
}


def fail(message: str) -> None:
    raise SystemExit('INLINE_SCRIPT_STATIC_FINALIZE_FAILED: ' + message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')

matches = []
for match in SCRIPT_RE.finditer(html):
    attrs = match.group('attrs') or ''
    if SRC_RE.search(attrs):
        continue
    matches.append(match)

if len(matches) != EXPECTED_INLINE_COUNT:
    fail(f'expected exactly {EXPECTED_INLINE_COUNT} inline script blocks, found {len(matches)}')

# Inventory all inline-script marker ids before writing anything. This keeps the
# review loop fail-closed while exposing only non-sensitive DOM marker names.
script_inventory = []
unreviewed_ids = []
for idx, match in enumerate(matches, start=1):
    attrs = match.group('attrs') or ''
    attr_names = [name.lower() for name in ATTR_NAME_RE.findall(attrs.strip())]
    id_match = ID_RE.search(attrs)
    script_id = id_match.group(2) if id_match else None
    script_inventory.append((idx, attr_names, script_id))
    if script_id and script_id not in REVIEWED_SINGLETON_IDS:
        unreviewed_ids.append(f'{idx}:{script_id}')
if unreviewed_ids:
    summary = '; '.join(
        f'{idx}:attrs={",".join(attrs) or "none"}:id={script_id or "none"}'
        for idx, attrs, script_id in script_inventory
    )
    fail('unreviewed inline-script marker id(s): ' + ','.join(unreviewed_ids) + '; inventory=' + summary)

prepared = []
for idx, match in enumerate(matches, start=1):
    attrs = match.group('attrs') or ''
    body = match.group('body')
    # Only ordinary executable classic/module script attributes are safe to externalize
    # mechanically. Reviewed historical marker ids are preserved only when each marker
    # is a singleton in the final HTML, proving no other script/style/DOM code refers to
    # that exact marker string. Any future attribute shape requires explicit review.
    attr_names = [name.lower() for name in ATTR_NAME_RE.findall(attrs.strip())]
    id_match = ID_RE.search(attrs)
    script_id = id_match.group(2) if id_match else None
    allowed_attrs = {'type'}
    if script_id is not None:
        if script_id not in REVIEWED_SINGLETON_IDS:
            fail(f'inline script {idx} has unreviewed id={script_id!r}')
        if html.count(script_id) != 1:
            fail(f'reviewed script id must be singleton; {script_id!r} occurrences={html.count(script_id)}')
        allowed_attrs.add('id')
    disallowed = [name for name in attr_names if name not in allowed_attrs]
    if disallowed:
        fail(f'inline script {idx} has unsupported attribute(s): {",".join(disallowed)}')
    type_match = TYPE_RE.search(attrs)
    script_type = (type_match.group(2).strip().lower() if type_match else '')
    if script_type not in ('', 'text/javascript', 'application/javascript', 'module'):
        fail(f'inline script {idx} is not an executable JS block: type={script_type!r}')
    if 'document.currentScript' in body:
        fail(f'inline script {idx} depends on document.currentScript')
    data = body.encode('utf-8')
    if not data.strip():
        fail(f'inline script {idx} is empty')
    name = f'app-inline-{idx:02d}.js'
    output = APP_DIR / name
    local_src = f'/app/{name}'
    replacement_attrs = attrs.rstrip()
    if replacement_attrs and not replacement_attrs.startswith((' ', '\t', '\r', '\n')):
        replacement_attrs = ' ' + replacement_attrs
    replacement = f'<script{replacement_attrs} src="{html_module.escape(local_src, quote=True)}"></script>'
    prepared.append((match, output, data, local_src, replacement, script_type, script_id))

APP_DIR.mkdir(parents=True, exist_ok=True)
for _, output, data, _, _, _, _ in prepared:
    tmp = output.with_suffix(output.suffix + '.tmp')
    tmp.write_bytes(data)
    os.replace(tmp, output)

# Replace from the end so original byte offsets remain valid.
rewritten = html
for match, _, _, _, replacement, _, _ in reversed(prepared):
    rewritten = rewritten[:match.start()] + replacement + rewritten[match.end():]

# Fail closed before committing the HTML rewrite.
remaining_inline = []
for match in SCRIPT_RE.finditer(rewritten):
    if not SRC_RE.search(match.group('attrs') or ''):
        remaining_inline.append(match.group(0)[:120])
if remaining_inline:
    fail(f'inline script blocks remain after rewrite: {len(remaining_inline)}')
for _, output, data, local_src, _, _, script_id in prepared:
    if rewritten.count(f'src="{local_src}"') != 1:
        fail(f'local app script reference drifted: {local_src}')
    if sha256(output.read_bytes()) != sha256(data):
        fail(f'written app script digest changed: {output.name}')
    if script_id and rewritten.count(f'id="{script_id}"') != 1:
        fail(f'reviewed script id not preserved exactly once: {script_id}')

INDEX.write_text(rewritten, encoding='utf-8')
print(
    'INLINE_SCRIPT_STATIC_FINALIZE_OK: '
    + '; '.join(
        f'{output.name}={sha256(data)}/{len(data)}B'
        for _, output, data, _, _, _, _ in prepared
    )
    + '; reviewed-ids=' + ','.join(sorted(REVIEWED_SINGLETON_IDS))
    + '; inline-script-blocks=0; execution-order=preserved'
)
