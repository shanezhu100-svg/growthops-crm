from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('LEAD_LINK_REPAIR_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f'{label} reviewed anchor expected once, found {count}')
    return text.replace(old, new, 1)


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
        i += 1
    fail(f'{name} closing brace missing')


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
adapter = ADAPTER.read_text(encoding='utf-8')
for marker in ('async function flushSave()', 'vm.persistLeadSaveBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)
if 'vm.persistLeadLinkRepairBarrier=' in adapter:
    fail('lead link repair barrier already present')
adapter = replace_once(
    adapter,
    '  vm.persistLeadSaveBarrier=()=>flushSave();',
    '  vm.persistLeadSaveBarrier=()=>flushSave();\n  vm.persistLeadLinkRepairBarrier=()=>flushSave();',
    'lead link repair barrier placement',
)
ADAPTER.write_text(adapter, encoding='utf-8')
adapter_sha = hashlib.sha256(adapter.encode('utf-8')).hexdigest()

if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

replacement = """openConvertedLeadClient(lead){const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),targetId=String(lead?.id??''),resolveLead=()=>Array.isArray(this.leads)?this.leads.find(row=>String(row?.id??'')===targetId)||null:(lead||null);const target=resolveLead();if(!target){this.notify('潜在客户状态已变化，请重新操作');return}const linkedId=String(target?.convertedClientId??''),client=this.clients.find(c=>String(c.id)===linkedId);if(client){this.selectedClientId=client.id;this.navigateTo('client-detail');return}if(typeof this.persistLeadLinkRepairBarrier!=='function'){this.notify('关联的正式客户已不存在，但关联修复未保存：云端持久化服务不可用');return}const beforeId=clone(target.convertedClientId),beforeAt=clone(target.convertedAt),attemptRow=target;target.convertedClientId=null;target.convertedAt='';return Promise.resolve(this.persistLeadLinkRepairBarrier()).then(()=>{this.notify('关联的正式客户已不存在，请重新确认合作')},e=>{const current=resolveLead();if(current===attemptRow&&current.convertedClientId===null&&current.convertedAt===''){current.convertedClientId=clone(beforeId);current.convertedAt=clone(beforeAt)}this.persist();this.notify(`关联的正式客户已不存在，但关联修复未保存，已恢复原关联状态：${e?.message||'保存失败'}`)})}"""

found = 0
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    bounds = method_bounds(text, 'openConvertedLeadClient')
    if bounds is None:
        continue
    found += 1
    start, end = bounds
    source = text[start:end].strip().rstrip(',').strip()
    required = (
        'this.clients.find',
        'lead?.convertedClientId',
        "this.notify('关联的正式客户已不存在，请重新确认合作')",
        'lead.convertedClientId=null',
        "lead.convertedAt=''",
        'this.persist()',
        'this.selectedClientId=client.id',
        "this.navigateTo('client-detail')",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        fail('openConvertedLeadClient reviewed source drifted: ' + ', '.join(missing))
    if 'persistLeadLinkRepairBarrier' in source:
        fail('openConvertedLeadClient already contains durability barrier')
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found != 1:
    fail(f'openConvertedLeadClient expected in exactly one app-inline artifact, found {found}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'LEAD_LINK_REPAIR_PERSISTENCE_ACK_FINALIZE_OK: '
    'existing-link=navigation-unchanged; missing-link=live-lead+cloud-ack-before-repair-success; '
    'failure=converted-link-rollback+rollback-persisted; '
    'concurrency=same-id-replacement+field-change-preserved; missing-barrier=fail-closed; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
