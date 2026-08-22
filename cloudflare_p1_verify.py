from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'

# P1 verifier scope is intentionally narrow: Cloudflare output/parity only.
# Application security is already enforced by sh build.sh and its existing tests.
EXPECTED_SHA256 = {
    'index.html': '941be51fcaf60acd0bb350c1822260f24555340fb2d719effe0f339c3b69a1e5',
    'cloud-adapter.js': '2a5b5da0f94ba66a2b58ed64b923e0167e7723eb7ccccd3c6384dfbeb471a2a6',
    'cloud-security-hotfix.js': 'f2b3f08c9bbabc4e974c859fe6d86396d028f46b43354b6d74572b5efa938194',
    'cloud-p1-overrides.js': 'e50e05322a0d56e78bf112a52be08ff54263f4ce88cb0b9b91f6613722b8ccab',
    'cloud-ui-action-bridge.js': 'b15e0b792e2f0ba6e99bef53fea96dde78b647b5528ae199311c4be9b37027a7',
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if not DIST.is_dir():
    raise SystemExit('CLOUDFLARE_P1_VERIFY_FAILED: dist/ missing; run sh build.sh first')

for name, expected in EXPECTED_SHA256.items():
    path = DIST / name
    if not path.is_file():
        raise SystemExit(f'CLOUDFLARE_P1_VERIFY_FAILED: missing dist/{name}')
    actual = sha256(path)
    if actual != expected:
        raise SystemExit(
            f'CLOUDFLARE_P1_VERIFY_FAILED: dist/{name} hash drift; '
            f'expected={expected}; actual={actual}'
        )

print(
    'CLOUDFLARE_P1_OUTPUT_PARITY_OK: '
    f'dist=present; key_artifacts={len(EXPECTED_SHA256)}; production_hashes=match'
)
