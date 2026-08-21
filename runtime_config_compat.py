from pathlib import Path
import json

root = Path(__file__).resolve().parent
config_path = root / 'public-runtime-config.json'
config = json.loads(config_path.read_text(encoding='utf-8'))

url = str(config.get('supabaseUrl') or '').strip()
key = str(config.get('supabasePublishableKey') or '').strip()
if not url.startswith('https://'):
    raise SystemExit('Invalid public Supabase URL')
if not key.startswith('sb_publishable_'):
    raise SystemExit('Invalid Supabase publishable key')
if "'" in url or "'" in key:
    raise SystemExit('Public runtime config contains unsupported quote characters')

# build_final.py still expects the two public values in the historical root
# index.html format. Generate the smallest possible compatibility shim at build
# time so the repository no longer needs to carry a second CRM application.
compat = (
    '<!doctype html><meta charset="utf-8">'
    '<script>'
    f"const SUPABASE_URL='{url}';"
    f"const API_KEY='{key}';"
    '</script>\n'
)
(root / 'index.html').write_text(compat, encoding='utf-8')
print('PUBLIC_RUNTIME_CONFIG_COMPAT_OK')
