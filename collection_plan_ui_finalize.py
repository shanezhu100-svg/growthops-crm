from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('COLLECTION_PLAN_UI_FINALIZE_FAILED: ' + message)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f'{label} expected exactly once, found {count}')
    return text.replace(old, new, 1)


if not INDEX.is_file():
    fail('dist/index.html missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

html = INDEX.read_text(encoding='utf-8')

billing_anchor = '''<form-field label="投放服务费计费方式"><select v-model="form.billingMode" class="field"><option value="FULL_MONTH">整月计费</option><option value="PRORATE">按实际服务天数折算</option><option value="MANUAL">手工账单确认</option></select></form-field><form-field label="每月付款到期日"><input v-model.number="form.renewalAlertDay" type="number" min="1" max="31" class="field" /></form-field>'''
collection_fields = '''<form-field label="投放服务费计费方式"><select v-model="form.billingMode" class="field"><option value="FULL_MONTH">整月计费</option><option value="PRORATE">按实际服务天数折算</option><option value="MANUAL">手工账单确认</option></select></form-field><form-field label="收款节奏"><select v-model="form.collectionPlan.mode" class="field"><option value="MONTHLY">月结一次</option><option value="SEMI_MONTHLY">半月收款</option></select><div class="text-[10px] text-slate-400 mt-1">仅影响之后新生成应收的催款节点；历史已生成账单不追溯修改。</div></form-field><template v-if="form.collectionPlan.mode==='SEMI_MONTHLY'"><form-field label="首个收款日"><input v-model.number="form.collectionPlan.firstDay" type="number" min="1" max="28" step="1" class="field" /><div class="text-[10px] text-slate-400 mt-1">第二个节点自动取当月最后一天。</div></form-field><form-field label="首笔收款比例"><select v-model.number="form.collectionPlan.firstRatio" class="field"><option :value="0.25">25%</option><option :value="0.3">30%</option><option :value="0.4">40%</option><option :value="0.5">50%</option><option :value="0.6">60%</option><option :value="0.7">70%</option><option :value="0.75">75%</option></select></form-field></template><form-field label="月结默认到期日"><input v-model.number="form.renewalAlertDay" type="number" min="1" max="31" class="field" /><div class="text-[10px] text-slate-400 mt-1">月结一次时使用；半月收款由节点日期覆盖提醒。</div></form-field>'''
html = replace_once(html, billing_anchor, collection_fields, 'client form billing/collection fields')

detail_anchor = '''<div class="bg-white border border-slate-200 rounded-2xl p-4"><div class="text-[11px] text-slate-400">付款到期日</div><div class="text-xl font-extrabold text-amber-600 mt-2">每月 {{ selectedClient.renewalAlertDay }} 号</div></div>'''
detail_new = '''<div class="bg-white border border-slate-200 rounded-2xl p-4"><div class="text-[11px] text-slate-400">收款节奏</div><div class="text-xl font-extrabold text-amber-600 mt-2" v-if="selectedClient.collectionPlan?.mode==='SEMI_MONTHLY'">{{ selectedClient.collectionPlan.firstDay || 15 }} 日 + 月末</div><div class="text-xl font-extrabold text-amber-600 mt-2" v-else>每月 {{ selectedClient.renewalAlertDay }} 号</div><div class="text-[10px] text-slate-400 mt-1" v-if="selectedClient.collectionPlan?.mode==='SEMI_MONTHLY'">首笔 {{ Math.round(Number(selectedClient.collectionPlan.firstRatio || 0.5) * 100) }}% · 余额月末收取</div></div>'''
html = replace_once(html, detail_anchor, detail_new, 'client detail collection summary')
INDEX.write_text(html, encoding='utf-8')

app_changes = []
app_found = 0
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text

    normalize_anchor = "c.billingMode=['FULL_MONTH','PRORATE','MANUAL'].includes(c.billingMode)?c.billingMode:'FULL_MONTH';"
    if normalize_anchor in text:
        app_found += 1
        normalize_new = normalize_anchor + "const rawCollectionPlan=c.collectionPlan&&typeof c.collectionPlan==='object'?c.collectionPlan:{},collectionMode=String(rawCollectionPlan.mode||'MONTHLY').toUpperCase(),collectionFirstDayRaw=Number(rawCollectionPlan.firstDay==null?15:rawCollectionPlan.firstDay),collectionFirstRatioRaw=Number(rawCollectionPlan.firstRatio==null?0.5:rawCollectionPlan.firstRatio),collectionFirstDay=Number.isFinite(collectionFirstDayRaw)?Math.max(1,Math.min(28,Math.trunc(collectionFirstDayRaw))):15;c.collectionPlan={mode:collectionMode==='SEMI_MONTHLY'?'SEMI_MONTHLY':'MONTHLY',firstDay:collectionFirstDay,firstRatio:Number.isFinite(collectionFirstRatioRaw)&&collectionFirstRatioRaw>0&&collectionFirstRatioRaw<1?collectionFirstRatioRaw:0.5};"
        text = replace_once(text, normalize_anchor, normalize_new, 'normalizeClient collection plan')

        default_anchor = "monthlyFee:'',billingMode:'FULL_MONTH',startDate:'',endDate:'',renewalAlertDay:25,status:'ACTIVE'"
        default_new = "monthlyFee:'',billingMode:'FULL_MONTH',collectionPlan:{mode:'MONTHLY',firstDay:15,firstRatio:0.5},startDate:'',endDate:'',renewalAlertDay:25,status:'ACTIVE'"
        text = replace_once(text, default_anchor, default_new, 'defaultForm collection plan')

    if text != original:
        path.write_text(text, encoding='utf-8')
        app_changes.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if app_found != 1 or len(app_changes) != 1:
    fail(f'normalize/default app artifact expected exactly once, found anchors={app_found}, changed={len(app_changes)}')

print(
    'COLLECTION_PLAN_UI_FINALIZE_OK: '
    'client-form=monthly+semi-monthly; semi-monthly=first-day+ratio+automatic-month-end; '
    'legacy-client=normalized-monthly-default; invalid-plan=normalized-safe-default; '
    'history=new-receivables-only+no-retroactive-rewrite; detail=truthful-collection-summary; '
    f'index={hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]}; '
    + 'app=' + ','.join(f'{name}:{sha[:12]}' for name, sha in app_changes)
)
