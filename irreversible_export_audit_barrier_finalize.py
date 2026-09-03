from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('IRREVERSIBLE_EXPORT_AUDIT_BARRIER_FINALIZE_FAILED: ' + message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f'{label} reviewed anchor expected once, found {count}')
    return text.replace(old, new, 1)


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


def statement(source: str, marker: str, start_at: int = 0):
    start = source.find(marker, start_at)
    if start < 0:
        fail(f'statement marker missing: {marker}')
    end = source.find(';', start)
    if end < 0:
        fail(f'statement terminator missing: {marker}')
    return start, end + 1, source[start:end + 1]


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
adapter = ADAPTER.read_text(encoding='utf-8')
for marker in ('async function flushSave()', 'let saveTimer=null;', "vm.downloadFullBackup=()=>{"):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)

helper = """  vm.persistExportAuditBarrier=async(attemptRows)=>{
    const rollbackRows=new Set(Array.isArray(attemptRows)?attemptRows:[]);
    try{await flushSave();return true;}
    catch(e){
      clearTimeout(saveTimer);saveTimer=null;
      vm.auditLogs=Array.isArray(vm.auditLogs)?vm.auditLogs.filter(row=>!rollbackRows.has(row)):[];
      vm.notify(`导出已取消，审计记录未能保存：${e?.message||'保存失败'}`);
      return false;
    }
  };
"""
if 'vm.persistExportAuditBarrier=' in adapter:
    fail('export audit barrier helper already present')
adapter = adapter.replace('  vm.downloadFullBackup=()=>{', helper + '  vm.downloadFullBackup=async()=>{', 1)
old_download = """    a.href=url;a.download=`growth-ops-backup-redacted-${vm.localDateKey()}.json`;document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);vm.logAudit('导出脱敏全量备份',a.download);vm.persist();vm.notify('脱敏业务备份已导出；不包含登录账号、密码、2FA 或恢复码');"""
new_download = """    a.href=url;a.download=`growth-ops-backup-redacted-${vm.localDateKey()}.json`;
    const exportAuditBefore=new Set(Array.isArray(vm.auditLogs)?vm.auditLogs:[]);
    vm.logAudit('导出脱敏全量备份',a.download);
    const exportAuditRows=Array.isArray(vm.auditLogs)?vm.auditLogs.filter(row=>!exportAuditBefore.has(row)):[];
    if(!(await vm.persistExportAuditBarrier(exportAuditRows))){URL.revokeObjectURL(url);return;}
    document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);vm.notify('脱敏业务备份已导出；不包含登录账号、密码、2FA 或恢复码');"""
adapter = replace_once(adapter, old_download, new_download, 'redacted full-backup audit-before-file barrier')
ADAPTER.write_text(adapter, encoding='utf-8')
adapter_sha = hashlib.sha256(adapter.encode('utf-8')).hexdigest()

if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

found = {'exportFinanceExcel': 0, 'exportRebateExcel': 0}
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text
    for name in ('exportFinanceExcel', 'exportRebateExcel'):
        bounds = method_bounds(text, name)
        if bounds is None:
            continue
        found[name] += 1
        start, end = bounds
        source = text[start:end]
        if 'persistExportAuditBarrier' in source or 'exportAuditBefore=' in source:
            fail(f'{name} already contains export audit barrier')
        write_start, write_end, write_stmt = statement(source, 'XLSX.writeFile(')
        audit_start, audit_end, audit_stmt = statement(source, 'this.logAudit(', write_end)
        notify_start, notify_end, notify_stmt = statement(source, 'this.notify(', audit_end)
        if not (write_start < audit_start < notify_start):
            fail(f'{name} expected reviewed write -> audit -> success-notify ordering')
        pieces = [source[:write_start], source[write_end:audit_start], source[audit_end:notify_start], source[notify_end:]]
        replacement = (
            "const exportAuditBefore=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]);"
            + audit_stmt +
            "const exportAuditRows=Array.isArray(this.auditLogs)?this.auditLogs.filter(row=>!exportAuditBefore.has(row)):[];"
            "if(typeof this.persistExportAuditBarrier!=='function'){"
            "const rollbackRows=new Set(exportAuditRows);this.auditLogs=Array.isArray(this.auditLogs)?this.auditLogs.filter(row=>!rollbackRows.has(row)):[];"
            "this.notify('导出已取消：审计持久化服务不可用');return;}"
            "return Promise.resolve(this.persistExportAuditBarrier(exportAuditRows)).then(exportAuditCommitted=>{if(!exportAuditCommitted)return;"
            + write_stmt + notify_stmt + "});"
        )
        source = pieces[0] + replacement + pieces[1] + pieces[2] + pieces[3]
        text = text[:start] + source + text[end:]
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

for name, count in found.items():
    if count != 1:
        fail(f'{name} expected in exactly one app-inline artifact, found {count}')
if len(changed) != 1:
    fail(f'expected exactly one app artifact change, found {len(changed)}')

print(
    'IRREVERSIBLE_EXPORT_AUDIT_BARRIER_FINALIZE_OK: '
    'finance+rebate+redacted-backup=audit-ack-before-file; '
    'failure=zero-file+attempt-audit-rollback+unrelated-audit-preserved; '
    'save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app=' + ','.join(f'{name}:{sha}' for name, sha in changed)
)
