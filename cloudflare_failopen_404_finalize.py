from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'dist' / '404.html'

HTML = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow,noarchive">
  <title>404 · Not Found</title>
  <style>
    html,body{height:100%;margin:0;background:#f8fafc;color:#0f172a;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    body{display:grid;place-items:center;padding:24px;box-sizing:border-box}
    main{max-width:560px;text-align:center}
    h1{font-size:56px;line-height:1;margin:0 0 16px}
    p{font-size:16px;line-height:1.6;margin:0;color:#475569}
  </style>
</head>
<body>
  <main>
    <h1>404</h1>
    <p>The requested resource was not found.</p>
  </main>
</body>
</html>
'''

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(HTML, encoding='utf-8')

if OUTPUT.read_text(encoding='utf-8') != HTML:
    raise SystemExit('CLOUDFLARE_FAILOPEN_404_FINALIZE_FAILED output verification')

print(f'CLOUDFLARE_FAILOPEN_404_FINALIZE_OK: output=dist/404.html; bytes={OUTPUT.stat().st_size}; scripts=0; external-assets=0')
