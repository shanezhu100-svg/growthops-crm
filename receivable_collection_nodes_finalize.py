from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('RECEIVABLE_COLLECTION_NODES_FINALIZE_FAILED: ' + message)


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


def rename_method(source: str, old_name: str, new_name: str) -> str:
    old = old_name + '('
    new = new_name + '('
    if source.count(old) < 1:
        fail(f'{old_name} definition marker missing')
    return source.replace(old, new, 1)


if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

found_alert = 0
found_create = 0
changed = []

helpers_and_wrapper = r'''financeReceivableCollectionNodes(r){const raw=Array.isArray(r?.collectionNodes)?r.collectionNodes:[];if(!raw.length)return[];const validDate=value=>{const s=String(value||'');if(!/^\d{4}-\d{2}-\d{2}$/.test(s))return false;const[y,m,d]=s.split('-').map(Number),dt=new Date(Date.UTC(y,m-1,d));return dt.getUTCFullYear()===y&&dt.getUTCMonth()===m-1&&dt.getUTCDate()===d},master=Number(r?.amount||0),rows=[];for(let i=0;i<raw.length;i++){const item=raw[i]||{},amount=Number(item.amount),dueDate=String(item.dueDate||'');if(!Number.isFinite(amount)||amount<=0||!validDate(dueDate))return[];rows.push({id:String(item.id||`node-${i+1}`),dueDate,amount:Math.round(amount*100)/100,label:String(item.label||'')})}const total=rows.reduce((sum,item)=>sum+item.amount,0);if(!Number.isFinite(master)||master<=0||Math.abs(total-master)>0.01)return[];return rows.sort((a,b)=>a.dueDate.localeCompare(b.dueDate)||a.id.localeCompare(b.id))},
financeReceivableCollectionAllocation(r){const nodes=this.financeReceivableCollectionNodes(r);if(!nodes.length)return{};let remaining=(Array.isArray(r?.payments)?r.payments:[]).reduce((sum,p)=>{const amount=Number(p?.amount);return sum+(Number.isFinite(amount)&&amount>0?amount:0)},0),out={};for(const node of nodes){const paid=Math.min(node.amount,Math.max(0,remaining));out[node.id]=Math.round(paid*100)/100;remaining=Math.max(0,remaining-paid)}return out},
financeReceivableBuildCollectionNodes(r,plan){if(!r||!plan||String(plan.mode||'').toUpperCase()!=='SEMI_MONTHLY')return[];const amount=Number(r.amount),month=String(r.settlementMonth||'');if(!Number.isFinite(amount)||amount<=0||!/^\d{4}-\d{2}$/.test(month))return[];const firstDay=Math.max(1,Math.min(28,Number(plan.firstDay||15)||15)),ratio=Number(plan.firstRatio==null?0.5:plan.firstRatio);if(!Number.isFinite(ratio)||ratio<=0||ratio>=1)return[];const[y,m]=month.split('-').map(Number),lastDay=new Date(Date.UTC(y,m,0)).getUTCDate(),pad=n=>String(n).padStart(2,'0'),first=Math.round(amount*ratio*100)/100,second=Math.round((amount-first)*100)/100;if(first<=0||second<=0)return[];return[{id:`${month}-D${pad(firstDay)}`,dueDate:`${month}-${pad(firstDay)}`,amount:first,label:`${firstDay}日收款`},{id:`${month}-EOM`,dueDate:`${month}-${pad(lastDay)}`,amount:second,label:'月末收款'}]},
alertList(){const base=this._legacyAlertList(),receivables=Array.isArray(this.financeReceivables)?this.financeReceivables:[],explicit=receivables.map(r=>({r,nodes:this.financeReceivableCollectionNodes(r)})).filter(x=>x.nodes.length);if(!explicit.length)return base;const masterAlertIds=new Set(explicit.map(x=>`RECEIVABLE-${x.r.id}`)),out=base.filter(item=>!masterAlertIds.has(String(item?.id||''))),legacyRows=receivables.filter(r=>!explicit.some(x=>x.r===r)),synthetic=[];for(const entry of explicit){const allocation=this.financeReceivableCollectionAllocation(entry.r);for(const node of entry.nodes){const paid=Number(allocation[node.id]||0);synthetic.push({...entry.r,id:`${entry.r.id}::COLLECTION::${node.id}`,amount:node.amount,dueDate:node.dueDate,payments:paid>0?[{id:`allocation-${node.id}`,amount:paid}]:[],collectionNodes:[]})}}const view=Object.create(this);view.financeReceivables=[...legacyRows,...synthetic];const nodeAlerts=this._legacyAlertList.call(view),prefixes=explicit.map(x=>`RECEIVABLE-${x.r.id}::COLLECTION::`);for(const item of nodeAlerts){const id=String(item?.id||'');if(prefixes.some(prefix=>id.startsWith(prefix)))out.push(item)}return out}'''

create_wrapper = r'''createReceivableForClientMonth(client,month,opts){const before=new Set(Array.isArray(this.financeReceivables)?this.financeReceivables:[]),added=this._legacyCreateReceivableForClientMonth(client,month,opts);if(!added||!client||String(client.collectionPlan?.mode||'').toUpperCase()!=='SEMI_MONTHLY')return added;const created=(Array.isArray(this.financeReceivables)?this.financeReceivables:[]).filter(row=>!before.has(row)&&String(row?.clientId)===String(client.id));for(const row of created){const nodes=this.financeReceivableBuildCollectionNodes(row,client.collectionPlan);if(nodes.length)row.collectionNodes=nodes}return added}'''

for path in files:
    text = path.read_text(encoding='utf-8')
    original = text

    bounds = method_bounds(text, 'alertList')
    if bounds is not None:
        found_alert += 1
        start, end = bounds
        legacy = rename_method(text[start:end], 'alertList', '_legacyAlertList')
        text = text[:start] + legacy + ',' + helpers_and_wrapper + text[end:]

    bounds = method_bounds(text, 'createReceivableForClientMonth')
    if bounds is not None:
        found_create += 1
        start, end = bounds
        legacy = rename_method(text[start:end], 'createReceivableForClientMonth', '_legacyCreateReceivableForClientMonth')
        text = text[:start] + legacy + ',' + create_wrapper + text[end:]

    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

if found_alert != 1:
    fail(f'alertList expected exactly once, found {found_alert}')
if found_create != 1:
    fail(f'createReceivableForClientMonth expected exactly once, found {found_create}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'RECEIVABLE_COLLECTION_NODES_FINALIZE_OK: '
    'master-receivable=accounting-authority; explicit-nodes=reminder-authority; '
    'payments=earliest-due-allocation; invalid-node-plan=legacy-fail-safe; '
    'semi-monthly=client-plan+15th/default+month-end+ratio; legacy=no-node-compatible; '
    f'artifact={changed[0][0]}:{changed[0][1][:12]}'
)
