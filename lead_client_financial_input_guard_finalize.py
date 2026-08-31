from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('LEAD_CLIENT_FINANCIAL_INPUT_GUARD_FINALIZE_FAILED: ' + message)


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


def insert_guard(source: str, name: str, guard: str, marker: str) -> str:
    signature = re.match(rf'{re.escape(name)}\([^)]*\)\s*\{{', source)
    if not signature:
        fail(f'{name} signature drifted')
    if marker in source:
        fail(f'{name} already contains financial-input guard')
    return source[:signature.end()] + guard + source[signature.end():]


if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

lead_guard = (
    "const leadExpectedBudgetCheck=Number(this.leadForm&&this.leadForm.expectedBudget!=null&&this.leadForm.expectedBudget!==''?this.leadForm.expectedBudget:0),"
    "leadAdQuoteCheck=Number(this.leadForm&&this.leadForm.adQuote!=null&&this.leadForm.adQuote!==''?this.leadForm.adQuote:0);"
    "if(!Number.isFinite(leadExpectedBudgetCheck)||leadExpectedBudgetCheck<0||!Number.isFinite(leadAdQuoteCheck)||leadAdQuoteCheck<0){this.notify('请输入有效预算或报价');return}"
)
client_guard = (
    "const clientMonthlyFeeCheck=Number(this.form&&this.form.monthlyFee!=null&&this.form.monthlyFee!==''?this.form.monthlyFee:0);"
    "if(!Number.isFinite(clientMonthlyFeeCheck)||clientMonthlyFeeCheck<0){this.notify('请输入有效月服务费');return}"
)

specs = {
    'saveLead': (lead_guard, 'leadExpectedBudgetCheck='),
    'saveClient': (client_guard, 'clientMonthlyFeeCheck='),
}
found = {name: 0 for name in specs}
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text
    for name, (guard, marker) in specs.items():
        bounds = method_bounds(text, name)
        if bounds is None:
            continue
        found[name] += 1
        start, end = bounds
        source = text[start:end].rstrip()
        patched = insert_guard(source, name, guard, marker)
        text = text[:start] + patched + text[end:]
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

for name, count in found.items():
    if count != 1:
        fail(f'{name} expected in exactly one app-inline artifact, found {count}')
if not changed:
    fail('no final runtime artifact changed')

print(
    'LEAD_CLIENT_FINANCIAL_INPUT_GUARD_FINALIZE_OK: '
    'lead=expectedBudget+adQuote-finite-nonnegative; client=monthlyFee-finite-nonnegative; '
    'negative+nan+infinity=denied-before-persist+audit+billing; zero+empty=preserved; '
    + 'artifacts=' + ','.join(f'{name}:{sha[:12]}' for name, sha in changed)
)
