from pathlib import Path
import hashlib, re, sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / ".final-page-canonical"
TARGET_BYTES = 643031
TARGET_SHA256 = "51ca745531e98d1799d0ac181e97e29a1fdd6ea2eb77587b41051d9519103e43"
PAT = re.compile(r"offset-(\d+)-(\d+)\.htmlpart$")

parts = []
for p in SRC.iterdir():
    m = PAT.fullmatch(p.name)
    if not m:
        continue
    start, end = map(int, m.groups())
    raw = p.read_bytes()
    if end <= start:
        raise SystemExit(f"invalid range: {p.name}")
    if len(raw) != end - start:
        raise SystemExit(f"size mismatch: {p.name}: got {len(raw)}, expected {end-start}")
    parts.append((start, end, p, raw))

parts.sort(key=lambda x: (x[0], x[1]))
if not parts:
    raise SystemExit("no canonical source chunks found")

pos = 0
out = bytearray()
for start, end, p, raw in parts:
    if start != pos:
        kind = "overlap" if start < pos else "gap"
        raise SystemExit(f"{kind}: expected next start {pos}, got {start} ({p.name})")
    out.extend(raw)
    pos = end

if pos != TARGET_BYTES:
    raise SystemExit(f"incomplete source: ended at {pos}, expected {TARGET_BYTES}")

digest = hashlib.sha256(out).hexdigest()
if digest != TARGET_SHA256:
    raise SystemExit(f"SHA-256 mismatch: {digest} != {TARGET_SHA256}")

print(f"OK final CRM source: {len(out)} bytes; SHA-256 {digest}")
