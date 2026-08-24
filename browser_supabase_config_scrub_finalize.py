from pathlib import Path
import re

root = Path(__file__).resolve().parent
dist = root / 'dist'
index_path = dist / 'index.html'
html = index_path.read_text(encoding='utf-8')

pattern = re.compile(
    r'<script>window\.__GROWTHOPS_SUPABASE_URL__=(?:"(?:[^"\\]|\\.)*"|null);'
    r'window\.__GROWTHOPS_SUPABASE_KEY__=(?:"(?:[^"\\]|\\.)*"|null);</script>'
)
html, count = pattern.subn('', html)
if count != 1:
    raise SystemExit(f'Unexpected browser Supabase config script count after HttpOnly migration: {count}')
index_path.write_text(html, encoding='utf-8')

for path in sorted(dist.rglob('*')):
    if not path.is_file() or path.suffix not in {'.html', '.js'}:
        continue
    text = path.read_text(encoding='utf-8', errors='ignore')
    for marker in ('__GROWTHOPS_SUPABASE_URL__', '__GROWTHOPS_SUPABASE_KEY__'):
        if marker in text:
            raise SystemExit(f'Dead browser Supabase config marker survived in {path.relative_to(root)}: {marker}')

print('BROWSER_SUPABASE_CONFIG_SCRUB_FINALIZE_OK: shipped-globals=0; publishable-config=removed-after-http-only-migration; browser-transport=same-origin-bff-only')
