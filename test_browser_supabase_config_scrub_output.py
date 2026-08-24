from pathlib import Path

root = Path(__file__).resolve().parent
dist = root / 'dist'
html = (dist / 'index.html').read_text(encoding='utf-8')
adapter = (dist / 'cloud-adapter.js').read_text(encoding='utf-8')

for path in sorted(dist.rglob('*')):
    if not path.is_file() or path.suffix not in {'.html', '.js'}:
        continue
    text = path.read_text(encoding='utf-8', errors='ignore')
    for forbidden in (
        '__GROWTHOPS_SUPABASE_URL__',
        '__GROWTHOPS_SUPABASE_KEY__',
        "const SUPABASE_URL=window.",
        "const API_KEY=window.",
    ):
        if forbidden in text:
            raise SystemExit(f'BROWSER_SUPABASE_CONFIG_SCRUB_OUTPUT_FAILED {forbidden} survived in {path.relative_to(root)}')

if "fetch('/api/crm'" not in adapter or "credentials:'same-origin'" not in adapter:
    raise SystemExit('BROWSER_SUPABASE_CONFIG_SCRUB_OUTPUT_FAILED same-origin BFF transport missing')
if '/rest/v1/rpc/' in adapter:
    raise SystemExit('BROWSER_SUPABASE_CONFIG_SCRUB_OUTPUT_FAILED direct Supabase transport survived')
if '<script src="/cloud-adapter.js"></script>' not in html:
    raise SystemExit('BROWSER_SUPABASE_CONFIG_SCRUB_OUTPUT_FAILED cloud adapter script missing')

print('BROWSER_SUPABASE_CONFIG_SCRUB_OUTPUT_OK: dist-browser-supabase-globals=0; direct-rpc=0; same-origin-bff=present; cloud-adapter=present')
