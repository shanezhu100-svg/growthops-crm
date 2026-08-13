#!/bin/sh
set -eu
rm -rf dist
mkdir -p dist
cp index.html dist/index.html
cp upgrade.js dist/upgrade.js
cp upgrade.css dist/upgrade.css
python3 - <<'PY'
from pathlib import Path
p=Path('dist/index.html')
s=p.read_text()
s=s.replace('</head>','<link rel="stylesheet" href="/upgrade.css"></head>')
s=s.replace('</body>','<script src="/upgrade.js"></script></body>')
p.write_text(s)
PY
