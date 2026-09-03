from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('AD_DATA_INPUT_GUARD_FINALIZE_FAILED: ' + message)


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


def replace_method(text: str, name: str, patcher):
    bounds = method_bounds(text, name)
    if bounds is None:
        return text, False
    start, end = bounds
    source = text[start:end]
    patched = patcher(source)
    if patched == source:
        fail(f'{name} patch made no change')
    return text[:start] + patched + text[end:], True


if not APP_DIR.is_dir():
    fail('dist/app missing; run final runtime build first')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts found')


def patch_save_record(source: str) -> str:
    if 'const adRawNumericFields=' in source:
        fail('saveAdDataRecord already contains ad raw numeric guard')
    anchor = 'if(!client||!account)return;'
    if source.count(anchor) != 1:
        fail(f'saveAdDataRecord expected one client/account anchor, found {source.count(anchor)}')
    guard = (
        "const adRawNumericFields=['spend','impressions','clicks','leads','conversions','revenue'];"
        "if(this.selectedAdsPlatform==='FB')adRawNumericFields.push('reach');"
        "if(adRawNumericFields.some(key=>{const value=this.adDataForm?.[key];"
        "if(value===null||value===undefined||value==='')return false;"
        "const numeric=Number(value);return !Number.isFinite(numeric)||numeric<0}))"
        "{this.notify('请输入有效的广告投放数值');return;}"
    )
    return source.replace(anchor, anchor + guard, 1)


def patch_delete_record(source: str) -> str:
    # The UI can hold a stale row while account data changes, and both the row and
    # finance-month lock can change while a confirmation dialog is open. Validate
    # current account membership before confirmation and again inside the callback;
    # re-check the month lock at the actual mutation boundary as well.
    initial_anchor = "if(!client||!account||!record)return;if(!this.assertMonthUnlocked(String(record.date||'').slice(0,7),'删除广告数据'))return;"
    initial_replacement = (
        "if(!client||!account||!record)return;"
        "const adDeleteRecordExists=()=>Array.isArray(account.adDataRecords)&&account.adDataRecords.some(r=>String(r.id)===String(record.id));"
        "if(!adDeleteRecordExists()){this.notify('该广告数据记录已不存在，请刷新页面后重试');return;}"
        "if(!this.assertMonthUnlocked(String(record.date||'').slice(0,7),'删除广告数据'))return;"
    )
    if source.count(initial_anchor) != 1:
        fail(f'deleteAdDataRecord initial stale-target anchor count={source.count(initial_anchor)}')
    source = source.replace(initial_anchor, initial_replacement, 1)

    callback_anchor = "confirmText:'确认删除'},()=>{account.adDataRecords="
    callback_replacement = (
        "confirmText:'确认删除'},()=>{"
        "if(!adDeleteRecordExists()){this.notify('该广告数据记录已不存在，请刷新页面后重试');return;}"
        "if(!this.assertMonthUnlocked(String(record.date||'').slice(0,7),'删除广告数据'))return;"
        "account.adDataRecords="
    )
    if source.count(callback_anchor) != 1:
        fail(f'deleteAdDataRecord confirm callback anchor count={source.count(callback_anchor)}')
    return source.replace(callback_anchor, callback_replacement, 1)


found = {'saveAdDataRecord': 0, 'deleteAdDataRecord': 0}
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text
    text, did_save = replace_method(text, 'saveAdDataRecord', patch_save_record)
    if did_save:
        found['saveAdDataRecord'] += 1
    text, did_delete = replace_method(text, 'deleteAdDataRecord', patch_delete_record)
    if did_delete:
        found['deleteAdDataRecord'] += 1
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

for name, count in found.items():
    if count != 1:
        fail(f'{name} expected in exactly one app-inline artifact, found {count}')
if len(changed) != 1:
    fail(f'expected exactly one changed artifact, found {len(changed)}')

print(
    'AD_DATA_INPUT_GUARD_FINALIZE_OK: '
    'record-input=spend+impressions+clicks+leads+conversions+revenue+fb-reach-finite-nonnegative; '
    'record-delete=stale-target-denied-before-confirm+rechecked-on-confirm+month-lock-rechecked-on-confirm; '
    'invalid-record-input=denied-before-month-lock+mutation+sync+persist+audit; '
    f'artifact={changed[0][0]}:{changed[0][1][:12]}'
)
