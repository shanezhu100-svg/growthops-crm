from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'

GOOGLE_IMPORT = "    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');\n"
OLD_FAMILY = 'font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;'
NEW_FAMILY = 'font-family: "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;'


def fail(message: str) -> None:
    raise SystemExit('SYSTEM_FONT_FINALIZE_FAILED: ' + message)


if not INDEX.is_file():
    fail('dist/index.html missing')
html = INDEX.read_text(encoding='utf-8')

if html.count(GOOGLE_IMPORT) != 1:
    fail(f'expected Google Inter import exactly once, found {html.count(GOOGLE_IMPORT)}')
if html.count(OLD_FAMILY) != 1:
    fail(f'expected Inter body font family exactly once, found {html.count(OLD_FAMILY)}')
if NEW_FAMILY in html:
    fail('system-font target already present before migration')

html = html.replace(GOOGLE_IMPORT, '', 1)
html = html.replace(OLD_FAMILY, NEW_FAMILY, 1)
INDEX.write_text(html, encoding='utf-8')

if 'fonts.googleapis.com' in html or 'fonts.gstatic.com' in html:
    fail('Google Fonts network reference remains in final page')
if GOOGLE_IMPORT in html or OLD_FAMILY in html:
    fail('Google Inter source markers remain after rewrite')
if html.count(NEW_FAMILY) != 1:
    fail('system-font body family was not written exactly once')

print(
    'SYSTEM_FONT_FINALIZE_OK: google-fonts=removed; inter-network-font=removed; '
    'body-font=PingFang-SC+Microsoft-YaHei+system-ui; external-font-network=none'
)
