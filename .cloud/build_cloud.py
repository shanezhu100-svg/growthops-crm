from pathlib import Path
import base64, gzip, hashlib, re

BASE_SHA = '03cc1429b4423ec5bce11ce614eb29175dbe4994648d3e2f43f36945c563fadc'
FINAL_SHA = '755ae3adc0b9078ad8506e2e3c6303f93673614bf7e54afd03dbaf22f08f472f'
HUNK_RE = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def apply_unified_patch(source: str, patch: str) -> str:
    src = source.splitlines(keepends=True)
    p = patch.splitlines(keepends=True)
    out = []
    src_pos = 0
    i = 0
    while i < len(p):
        if not p[i].startswith('@@ '):
            i += 1
            continue
        m = HUNK_RE.match(p[i])
        if not m:
            raise RuntimeError(f'Invalid patch hunk: {p[i].rstrip()}')
        old_start = int(m.group(1)) - 1
        if old_start < src_pos:
            raise RuntimeError('Overlapping patch hunks')
        out.extend(src[src_pos:old_start])
        src_pos = old_start
        i += 1
        while i < len(p) and not p[i].startswith('@@ '):
            line = p[i]
            if line.startswith('--- ') or line.startswith('+++ '):
                i += 1
                continue
            if line.startswith('\\ No newline at end of file'):
                i += 1
                continue
            if not line:
                i += 1
                continue
            marker, body = line[0], line[1:]
            if marker == ' ':
                if src_pos >= len(src) or src[src_pos] != body:
                    raise RuntimeError(f'Patch context mismatch at source line {src_pos + 1}')
                out.append(src[src_pos]); src_pos += 1
            elif marker == '-':
                if src_pos >= len(src) or src[src_pos] != body:
                    raise RuntimeError(f'Patch removal mismatch at source line {src_pos + 1}')
                src_pos += 1
            elif marker == '+':
                out.append(body)
            else:
                break
            i += 1
    out.extend(src[src_pos:])
    return ''.join(out)


def main() -> None:
    paths = [Path(f'app/part-{i:03d}.txt') for i in range(1, 14)]
    parts = [p.read_text(encoding='utf-8').strip() for p in paths]
    if len(parts[7]) == 14999:
        parts[7] = parts[7][:1840] + 'N' + parts[7][1840:]
    if len(parts[11]) == 14999:
        parts[11] = parts[11][:6048] + 'r' + parts[11][6048:]
    base = gzip.decompress(base64.b64decode(''.join(parts)))
    if sha256(base) != BASE_SHA:
        raise SystemExit(f'Historical CRM base SHA mismatch: {sha256(base)}')

    patch = ''.join(Path(f'.cloud/patch-{i:03d}.txt').read_text(encoding='utf-8') for i in range(1, 9))
    final = apply_unified_patch(base.decode('utf-8'), patch).encode('utf-8')
    if sha256(final) != FINAL_SHA:
        raise SystemExit(f'Final CRM SHA mismatch: {sha256(final)}')

    dist = Path('dist')
    dist.mkdir(exist_ok=True)
    (dist / 'index.html').write_bytes(final)
    print(f'GrowthOps CRM verified build: {len(final)} bytes sha256={FINAL_SHA}')


if __name__ == '__main__':
    main()
