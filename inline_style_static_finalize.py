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
URL_RE = re.compile(r'url\(\s*(?:(["\'])(.*?)\1|([^)]*))\s*\)', re.IGNORECASE | re.DOTALL)
EXPECTED_STYLE_COUNT = 4
REVIEWED_SINGLETON_IDS = {
    'growthops-session-restore-style',
    'growthops-credential-v6-placeholder-style',
    'growthops-module-home-navigation-style',
}


def fail(message: str) -> None:
    raise SystemExit('INLINE_STYLE_STATIC_FINALIZE_FAILED: ' + message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_base_stable_urls(css: str, idx: int) -> int:
    """Allow only CSS URLs whose meaning cannot change when moved to /app/*.css."""
    url_calls = list(URL_RE.finditer(css))
    raw_url_calls = list(re.finditer(r'url\s*\(', css, flags=re.IGNORECASE))
    if len(url_calls) != len(raw_url_calls):
        fail(f'style block {idx} contains an unparseable url(...) expression')

    for match in url_calls:
        value = (match.group(2) if match.group(1) else match.group(3) or '').strip()
        lower = value.lower()
        if not value:
            fail(f'style block {idx} contains an empty url(...)')
        if lower.startswith('data:'):
            continue
        if value.startswith('/') and not value.startswith('//'):
            continue
        if lower.startswith('https://'):
            continue
        fail(
            f'style block {idx} contains a base-relative or unsupported CSS url(...): '
            f'{value[:80]!r}'
        )
    return len(url_calls)


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')
matches = list(STYLE_RE.finditer(html))
if len(matches) != EXPECTED_STYLE_COUNT:
    fail(f'expected exactly {EXPECTED_STYLE_COUNT} style blocks, found {len(matches)}')

# First-party runtime JS has already been externalized at this stage. A reviewed
# style marker may be preserved on the replacement <link>, but no first-party JS
# may depend on the original <style> element by id.
first_party_js = []
for path in sorted(DIST.rglob('*.js')):
    try:
        rel = path.relative_to(DIST)
    except ValueError:
        continue
    if rel.parts and rel.parts[0] == 'vendor':
        continue
    first_party_js.append((rel.as_posix(), path.read_text(encoding='utf-8')))

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
url_count = 0
for idx, match in enumerate(matches, start=1):
    attrs = match.group('attrs') or ''
    css = match.group('body')
    id_match = ID_RE.search(attrs)
    style_id = id_match.group(2) if id_match else None
    if style_id:
        if html.count(style_id) != 1:
            fail(f'reviewed style id must be singleton in HTML; {style_id!r} occurrences={html.count(style_id)}')
        js_refs = [name for name, text in first_party_js if style_id in text]
        if js_refs:
            fail(f'reviewed style id is referenced by first-party JS: {style_id!r} -> {",".join(js_refs)}')
    low_css = css.lower()
    if '@import' in low_css:
        fail(f'style block {idx} contains @import; externalization would change fetch semantics')
    url_count += validate_base_stable_urls(css, idx)
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
    + '; reviewed-ids=' + ','.join(sorted(REVIEWED_SINGLETON_IDS))
    + f'; first-party-js-id-refs=0; style-blocks=0; order=preserved; @import=absent; base-stable-urls={url_count}'
)
