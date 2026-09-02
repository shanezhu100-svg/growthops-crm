from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('OPENING_DEAL_LIFECYCLE_GUARD_FINALIZE_FAILED: ' + message)


def method_bounds(text: str, name: str):
    match = re.search(rf'(?:^|[,\n])\s*({re.escape(name)}\([^)]*\)\s*\{{)', text, flags=re.M)
    if not match:
        return None
    start = match.start() + match.group(0).index(match.group(1))
    open_pos = text.find('{', start)
    if open_pos < 0:
        fail(f'{name} opening brace missing')
    depth = 0
    quote = ''
    escaped = False
    line_comment = False
    block_comment = False
    i = open_pos
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ''
        if line_comment:
            if ch == '\n':
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == '*' and nxt == '/':
                block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == quote:
                quote = ''
            i += 1
            continue
        if ch == '/' and nxt == '/':
            line_comment = True
            i += 2
            continue
        if ch == '/' and nxt == '*':
            block_comment = True
            i += 2
            continue
        if ch in ('"', "'", '`'):
            quote = ch
            i += 1
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
            if depth < 0:
                break
        i += 1
    fail(f'{name} closing brace missing')


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
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')


def patch_save(source: str) -> str:
    # Editing UI state can outlive the underlying opening row. A truthy form id must
    # resolve before derived dates, finance synchronization, persistence, or audit.
    old = "const previous=this.openingForm.id?this.openingDeals.find(d=>String(d.id)===String(this.openingForm.id)):null;let effectiveStartDate="
    new = "const previous=this.openingForm.id?this.openingDeals.find(d=>String(d.id)===String(this.openingForm.id)):null;if(this.openingForm.id&&!previous){this.notify('该开户渠道记录已不存在，请刷新页面后重试');return}let effectiveStartDate="
    if '该开户渠道记录已不存在' in source:
        fail('saveOpeningDeal already contains stale-edit guard')
    if source.count(old) != 1:
        fail(f'saveOpeningDeal stale-edit anchor count={source.count(old)}')
    return source.replace(old, new, 1)


def patch_delete(source: str) -> str:
    # A locked OPENING_DEAL cost and its source opening row form one historical fact.
    # Block before confirmation and re-check inside the callback to avoid a TOCTOU
    # window if the finance month becomes locked while the confirmation is open.
    head = "const clientName=this.openingClientName(deal),providerName=this.openingProviderName(deal),contactName=this.openingContactName(deal);"
    guarded_head = head + "const linkedCost=this.financeCosts.find(c=>c.sourceType==='OPENING_DEAL'&&String(c.sourceId)===String(deal.id)),linkedCostMonth=String(linkedCost?.date||'').slice(0,7),linkedCostLocked=()=>!!(linkedCost&&linkedCostMonth&&this.isMonthLocked(linkedCostMonth));if(linkedCostLocked()){this.notify(`关联开户成本所在 ${linkedCostMonth} 已月结，不能删除该开户渠道记录`);return}"
    if '关联开户成本所在' in source or 'linkedCostLocked=' in source:
        fail('deleteOpeningDeal already contains linked-cost lock guard')
    if source.count(head) != 1:
        fail(f'deleteOpeningDeal head anchor count={source.count(head)}')
    source = source.replace(head, guarded_head, 1)

    callback_pattern = re.compile(r'(\},\(\)=>\{\s*)(const before=this\.openingDeals\.length;)')
    if len(callback_pattern.findall(source)) != 1:
        fail(f'deleteOpeningDeal callback anchor count={len(callback_pattern.findall(source))}')
    source = callback_pattern.sub(
        r"\1if(linkedCostLocked()){this.notify(`关联开户成本所在 ${linkedCostMonth} 已月结，不能删除该开户渠道记录`);return}\2",
        source,
        count=1,
    )

    old_inner = "const linkedCost=this.financeCosts.find(c=>c.sourceType==='OPENING_DEAL'&&String(c.sourceId)===String(deal.id));if(linkedCost&&!this.isMonthLocked(String(linkedCost.date||'').slice(0,7)))this.financeCosts=this.financeCosts.filter(c=>String(c.id)!==String(linkedCost.id));"
    new_inner = "if(linkedCost)this.financeCosts=this.financeCosts.filter(c=>String(c.id)!==String(linkedCost.id));"
    if source.count(old_inner) != 1:
        fail(f'deleteOpeningDeal linked-cost cleanup anchor count={source.count(old_inner)}')
    return source.replace(old_inner, new_inner, 1)


found = {'saveOpeningDeal': 0, 'deleteOpeningDeal': 0}
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text
    text, save_changed = replace_method(text, 'saveOpeningDeal', patch_save)
    if save_changed:
        found['saveOpeningDeal'] += 1
    text, delete_changed = replace_method(text, 'deleteOpeningDeal', patch_delete)
    if delete_changed:
        found['deleteOpeningDeal'] += 1
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

for name, count in found.items():
    if count != 1:
        fail(f'{name} expected in exactly one app-inline artifact, found {count}')
if len(changed) != 1:
    fail(f'expected exactly one changed artifact, found {len(changed)}')

print(
    'OPENING_DEAL_LIFECYCLE_GUARD_FINALIZE_OK: '
    'stale-edit=denied-before-cost-sync+persist+audit; '
    'locked-linked-cost=delete-denied-before-confirm+rechecked-on-confirm; '
    'create+existing-edit+unlocked-delete=preserved; '
    + 'artifact=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed)
)
