from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / 'dist' / 'app'
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'


def fail(message: str) -> None:
    raise SystemExit('AD_PLAN_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


def method_bounds(text: str, name: str):
    match = re.search(rf'(?:^|[,\n])\s*({re.escape(name)}\([^)]*\)\s*\{{)', text, flags=re.M)
    if not match:
        return None
    start = match.start() + match.group(0).index(match.group(1))
    open_pos = text.find('{', start)
    depth = 0; quote = ''; escaped = False; line_comment = False; block_comment = False; i = open_pos
    while i < len(text):
        ch = text[i]; nxt = text[i + 1] if i + 1 < len(text) else ''
        if line_comment:
            if ch == '\n': line_comment = False
            i += 1; continue
        if block_comment:
            if ch == '*' and nxt == '/': block_comment = False; i += 2; continue
            i += 1; continue
        if quote:
            if escaped: escaped = False
            elif ch == '\\': escaped = True
            elif ch == quote: quote = ''
            i += 1; continue
        if ch == '/' and nxt == '/': line_comment = True; i += 2; continue
        if ch == '/' and nxt == '*': block_comment = True; i += 2; continue
        if ch in ('"', "'", '`'): quote = ch; i += 1; continue
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0: return start, i + 1
        i += 1
    fail(f'{name} closing brace missing')


if not ADAPTER.is_file() or 'vm.persistAdStructureBarrier=()=>flushSave();' not in ADAPTER.read_text(encoding='utf-8'):
    fail('shared ad structure durability barrier missing')
if not APP_DIR.is_dir():
    fail('dist/app missing')

replacement = r'''saveAdsPlan(campaign){if(!campaign)return;const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),c=this.selectedAdsClient,currentCampaign=(c?.adCampaigns||[]).find(x=>String(x.id)===String(campaign.id));if(currentCampaign!==campaign){this.notify('该广告方案已不存在或状态已变化，请刷新页面后重试');return}if(!String(campaign.planName||'').trim()&&!String(campaign.name||'').trim()){this.notify('请至少填写方案名称或广告系列名称');return}const adPlanSets=campaign.adSets||[],adPlanInvalid=adPlanSets.some(adset=>{const ageMinRaw=adset?.ageMin,ageMaxRaw=adset?.ageMax,budgetRaw=adset?.budget,ageMin=(ageMinRaw===null||ageMinRaw===undefined||ageMinRaw==='')?18:Number(ageMinRaw),ageMax=(ageMaxRaw===null||ageMaxRaw===undefined||ageMaxRaw==='')?65:Number(ageMaxRaw),budget=budgetRaw===''?null:Number(budgetRaw??0);return !Number.isFinite(ageMin)||!Number.isFinite(ageMax)||ageMin<18||ageMin>65||ageMax<18||ageMax>65||ageMin>ageMax||(budget!==null&&(!Number.isFinite(budget)||budget<0));});if(adPlanInvalid){this.notify('请输入有效的广告方案年龄范围和预算');return}if(typeof this.persistAdStructureBarrier!=='function'){this.notify('广告方案未保存：云端持久化服务不可用');return}const clientId=String(c.id),beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),beforeAdSets=clone(campaign.adSets),beforeSaved=campaign.isSaved,beforeSavedAt=campaign.savedAt,beforeUpdatedAt=campaign.updatedAt;campaign.adSets=adPlanSets.map(adset=>({...adset,ageMin:(adset.ageMin===null||adset.ageMin===undefined||adset.ageMin==='')?18:Number(adset.ageMin),ageMax:(adset.ageMax===null||adset.ageMax===undefined||adset.ageMax==='')?65:Number(adset.ageMax),budget:adset.budget===''?'':Number(adset.budget??0)}));campaign.isSaved=true;campaign.savedAt=campaign.savedAt||this.localDateKey();campaign.updatedAt=this.localDateKey();this.logAudit('保存广告方案',`${c?.name||''} · ${campaign.planName||campaign.name||'未命名方案'}`);const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),attemptAdSets=clone(campaign.adSets),attemptSaved=campaign.isSaved,attemptSavedAt=campaign.savedAt,attemptUpdatedAt=campaign.updatedAt,authoritativeClient=()=>Array.isArray(this.clients)?this.clients.find(x=>String(x.id)===clientId):this.selectedAdsClient,rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const liveClient=authoritativeClient();if(liveClient!==c)return;const liveCampaign=(liveClient.adCampaigns||[]).find(x=>String(x.id)===String(campaign.id));if(liveCampaign!==campaign)return;if(same(campaign.adSets,attemptAdSets))campaign.adSets=clone(beforeAdSets);if(campaign.isSaved===attemptSaved)campaign.isSaved=beforeSaved;if(campaign.savedAt===attemptSavedAt)campaign.savedAt=beforeSavedAt;if(campaign.updatedAt===attemptUpdatedAt)campaign.updatedAt=beforeUpdatedAt};return Promise.resolve(this.persistAdStructureBarrier()).then(()=>{this.notify('广告方案已保存，并加入方案列表')},e=>{rollback();this.persist();this.notify(`广告方案未保存：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})}'''

count = 0; changed = []
for path in sorted(APP_DIR.glob('app-inline-*.js')):
    text = path.read_text(encoding='utf-8'); original = text
    bounds = method_bounds(text, 'saveAdsPlan')
    if bounds is None: continue
    count += 1; start, end = bounds; source = text[start:end]
    for marker in ('adPlanInvalid', 'campaign.isSaved=true', 'this.persist()', "logAudit('保存广告方案'", "this.notify('广告方案已保存，并加入方案列表')"):
        if marker not in source: fail('saveAdsPlan reviewed source drifted: ' + marker)
    if 'persistAdStructureBarrier' in source: fail('saveAdsPlan already ACK-aware')
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding='utf-8')
    changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))
if count != 1 or len(changed) != 1:
    fail(f'saveAdsPlan expected once / one artifact; method={count}; artifacts={len(changed)}')
print('AD_PLAN_PERSISTENCE_ACK_FINALIZE_OK: save=validation+normalization+audit+cloud-ack-before-success; failure=field-level+attempt-audit-rollback+rollback-persisted; concurrency=client+campaign+field-authority-preserved; missing-barrier=fail-closed; save-queue=shared-flushSave; app=' + changed[0][0] + ':' + changed[0][1])
