from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('AD_STRUCTURE_INTEGRITY_FINALIZE_FAILED: ' + message)


def method_bounds(text: str, name: str):
    signature = re.compile(rf'(?:^|[,\n])\s*({re.escape(name)}\([^)]*\)\s*\{{)', re.M)
    match = signature.search(text)
    if not match:
        return None
    start = match.start() + match.group(0).index(match.group(1))
    tail = text[start:]
    defs = list(re.finditer(r'(?:^|[,]\s*|\n\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{', tail))
    if len(defs) < 2 or defs[0].group(1) != name:
        fail(f'{name} boundary parser drifted')
    end = start + defs[1].start() + defs[1].group(0).index(defs[1].group(1))
    return start, end


if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text
    bounds = method_bounds(text, 'editAdCampaign')
    if bounds is not None:
        found += 1
        start, end = bounds
        source = text[start:end]
        anchor = "if(!campaign)return;campaign.isSaved=false;"
        replacement = (
            "if(!campaign)return;"
            "const currentCampaign=(this.selectedAdsClient?.adCampaigns||[]).find(x=>String(x.id)===String(campaign.id));"
            "if(!currentCampaign){this.notify('该广告系列已不存在，请刷新页面后重试');return;}"
            "currentCampaign.isSaved=false;"
        )
        if source.count(anchor) != 1:
            fail(f'editAdCampaign stale-edit anchor count={source.count(anchor)}')
        source = source.replace(anchor, replacement, 1)
        text = text[:start] + source + text[end:]
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'editAdCampaign expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed artifact, found {len(changed)}')

print(
    'AD_STRUCTURE_INTEGRITY_FINALIZE_OK: campaign-edit=live-selected-client-id-required; '
    'stale-edit=denied-before-mutation+persist; '
    f'artifact={changed[0][0]}:{changed[0][1][:12]}'
)
