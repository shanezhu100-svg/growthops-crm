from pathlib import Path
import hashlib
import html as html_module
import os
import re

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
INDEX = DIST / 'index.html'
APP_DIR = DIST / 'app'

STYLE_RE = re.compile(r'<style(?P<attrs>[^>]*)>(?P<body>.*?)</style>', re.IGNORECASE | re.DOTALL)
ID_RE = re.compile(r'\bid\s*=\s*(["\'])(.*?)\1', re.IGNORECASE | re.DOTALL)
ATTR_NAME_RE = re.compile(r'([:@A-Za-z_][:\-\.\w]*)\s*(?:=|$)')
EXPECTED_STYLE_COUNT = 4
REVIEWED_SINGLETON_IDS = set()


def fail(message: str) -> None:
    raise SystemExit('INLINE_STYLE_STATIC_FINALIZE_FAILED: ' + message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')
matches = list(STYLE_RE.finditer(html))
if len(matches) != EXPECTED_STYLE_COUNT:
    fail(f'expected exactly {EXPECTED_STYLE_COUNT} style blocks, found {len(matches)}')

inventory = []
unreviewed = []
for idx, match in enumerate(matches, start=1):
    attrs = match.group('attrs') or ''
    attr_names = [name.lower() for name in ATTR_NAME_RE.findall(attrs.strip())]
    id_match = ID_RE.search(attrs)
    style_id = id_match.group(2) if id_match else None
    inventory.append((idx, attr_names, style_id))
    if style_id and style_id not in REVIEWED_SINGLETON_IDS:
        unreviewed.append(f'{idx}:{style_id}')
    unknown_attrs = [name for name in attr_names if name != 'id']
    if unknown_attrs:
        unreviewed.append(f'{idx}:attrs={",".join(unknown_attrs)}')
if unreviewed:
    summary = '; '.join(
        f'{idx}:attrs={",".join(attrs) or "none"}:id={style_id or "none"}'
        for idx, attrs, style_id in inventory
    )
    fail('review required: ' + ','.join(unreviewed) + '; inventory=' + summary)

prepared = []
for idx, match in enumerate(matches, start=1):
    attrs = match.group('attrs') or ''
    css = match.group('body')
    id_match = ID_RE.search(attrs)
    style_id = id_match.group(2) if id_match else None
    if style_id:
        if html.count(style_id) != 1:
            fail(f'reviewed style id must be singleton; {style_id!r} occurrences={html.count(style_id)}')
    low_css = css.lower()
    if '@import' in low_css:
        fail(f'style block {idx} contains @import; externalization would change fetch semantics')
    if re.search(r'url\s*\(', css, flags=re.I):
        fail(f'style block {idx} contains url(...); externalization would change relative URL semantics')
    data = css.encode('utf-8')
    if not data.strip():
        fail(f'style block {idx} is empty')
    name = f'app-style-{idx:02d}.css'
    output = APP_DIR / name
    href = f'/app/{name}'
    id_attr = f' id="{html_module.escape(style_id, quote=True)}"' if style_id else ''
    replacement = f'<link rel="stylesheet" href="{href}"{id_attr} />'
    prepared.append((match, output, data, href, replacement, style_id))

APP_DIR.mkdir(parents=True, exist_ok=True)
for _, output, data, _, _, _ in prepared:
    tmp = output.with_suffix(output.suffix + '.tmp')
    tmp.write_bytes(data)
    os.replace(tmp, output)

rewritten = html
for match, _, _, _, replacement, _ in reversed(prepared):
    rewritten = rewritten[:match.start()] + replacement + rewritten[match.end():]

if STYLE_RE.search(rewritten):
    fail('inline style block remains after rewrite')
for _, output, data, href, _, style_id in prepared:
    if rewritten.count(f'href="{href}"') != 1:
        fail(f'local stylesheet reference drifted: {href}')
    if sha256(output.read_bytes()) != sha256(data):
        fail(f'written stylesheet digest changed: {output.name}')
    if style_id and rewritten.count(f'id="{style_id}"') != 1:
        fail(f'reviewed style id not preserved exactly once: {style_id}')

INDEX.write_text(rewritten, encoding='utf-8')
print(
    'INLINE_STYLE_STATIC_FINALIZE_OK: '
    + '; '.join(f'{output.name}={sha256(data)}/{len(data)}B' for _, output, data, _, _, _ in prepared)
    + '; style-blocks=0; order=preserved; url-import=absent'
)
