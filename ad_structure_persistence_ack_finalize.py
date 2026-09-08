from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parent
ADAPTER = ROOT / 'dist' / 'cloud-adapter.js'
APP_DIR = ROOT / 'dist' / 'app'


def fail(message: str) -> None:
    raise SystemExit('AD_STRUCTURE_PERSISTENCE_ACK_FINALIZE_FAILED: ' + message)


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


if not ADAPTER.is_file():
    fail('dist/cloud-adapter.js missing')
adapter = ADAPTER.read_text(encoding='utf-8')
for marker in ('async function flushSave()', 'vm.persistResourceCatalogBarrier=()=>flushSave();'):
    if marker not in adapter:
        fail('required final adapter marker missing: ' + marker)
if 'vm.persistAdStructureBarrier=' in adapter:
    fail('ad structure barrier already present')
adapter = replace_once(
    adapter,
    '  vm.persistResourceCatalogBarrier=()=>flushSave();',
    '  vm.persistResourceCatalogBarrier=()=>flushSave();\n  vm.persistAdStructureBarrier=()=>flushSave();',
    'ad structure barrier placement',
)
ADAPTER.write_text(adapter, encoding='utf-8')
adapter_sha = hashlib.sha256(adapter.encode('utf-8')).hexdigest()

if not APP_DIR.is_dir():
    fail('dist/app missing')
files = sorted(APP_DIR.glob('app-inline-*.js'))
if not files:
    fail('no final app-inline JS artifacts')

replacements = {
'addAdCampaign': r'''addAdCampaign(){const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),c=this.selectedAdsClient,a=this.selectedAdsAccount;if(!c||!a){this.notify('请先选择广告账户');return}if(typeof this.persistAdStructureBarrier!=='function'){this.notify('广告系列未添加：云端持久化服务不可用');return}const clientId=String(c.id),beforeWasArray=Array.isArray(c.adCampaigns),beforeContainer=beforeWasArray?null:clone(c.adCampaigns),attempt=this.emptyAdCampaign(),attemptSnapshot=clone(attempt);c.adCampaigns=beforeWasArray?c.adCampaigns:[];c.adCampaigns.push(attempt);const authoritativeClient=()=>Array.isArray(this.clients)?this.clients.find(x=>String(x.id)===clientId):this.selectedAdsClient,rollback=()=>{const liveClient=authoritativeClient();if(liveClient!==c)return;liveClient.adCampaigns=Array.isArray(liveClient.adCampaigns)?liveClient.adCampaigns:[];const i=liveClient.adCampaigns.findIndex(x=>String(x.id)===String(attempt.id));if(i>=0&&liveClient.adCampaigns[i]===attempt&&same(liveClient.adCampaigns[i],attemptSnapshot)){liveClient.adCampaigns.splice(i,1);if(!beforeWasArray&&liveClient.adCampaigns.length===0)liveClient.adCampaigns=clone(beforeContainer)}};return Promise.resolve(this.persistAdStructureBarrier()).then(()=>{this.notify('已添加广告系列')},e=>{rollback();this.persist();this.notify(`广告系列未添加：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})}''',
'editAdCampaign': r'''editAdCampaign(campaign){if(!campaign)return;const c=this.selectedAdsClient,currentCampaign=(c?.adCampaigns||[]).find(x=>String(x.id)===String(campaign.id));if(!currentCampaign){this.notify('该广告系列已不存在，请刷新页面后重试');return;}if(typeof this.persistAdStructureBarrier!=='function'){this.notify('方案编辑状态未保存：云端持久化服务不可用');return}const clientId=String(c.id),beforeSaved=currentCampaign.isSaved;currentCampaign.isSaved=false;const authoritativeClient=()=>Array.isArray(this.clients)?this.clients.find(x=>String(x.id)===clientId):this.selectedAdsClient,rollback=()=>{const liveClient=authoritativeClient();if(liveClient!==c)return;const liveCampaign=(liveClient.adCampaigns||[]).find(x=>String(x.id)===String(currentCampaign.id));if(liveCampaign===currentCampaign&&currentCampaign.isSaved===false)currentCampaign.isSaved=beforeSaved};return Promise.resolve(this.persistAdStructureBarrier()).then(()=>{this.notify('已打开方案编辑器')},e=>{rollback();this.persist();this.notify(`方案编辑状态未保存：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})}''',
'removeAdCampaign': r'''removeAdCampaign(campaign){const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),c=this.selectedAdsClient;if(!c||!campaign)return;const clientId=String(c.id),authoritativeClient=()=>Array.isArray(this.clients)?this.clients.find(x=>String(x.id)===clientId):this.selectedAdsClient,campaignById=()=>((c.adCampaigns||[]).find(x=>String(x.id)===String(campaign.id))),currentCampaign=campaignById();if(!currentCampaign){this.notify('该广告系列已不存在，请刷新页面后重试');return;}const adSetCount=(currentCampaign.adSets||[]).length,adCount=(currentCampaign.adSets||[]).reduce((n,s)=>n+(s.ads||[]).length,0);this.askConfirm({title:'删除广告系列',message:`确定删除【${currentCampaign.name||currentCampaign.planName||'未命名广告系列'}】吗？\n将同时删除其中 ${adSetCount} 个广告组、${adCount} 个广告设置。`,confirmText:'确认删除'},()=>{if(authoritativeClient()!==c||this.selectedAdsClient!==c){this.notify('当前广告客户状态已变化，请重新确认删除');return}const liveCampaign=campaignById();if(!liveCampaign){this.notify('该广告系列已不存在，请刷新页面后重试');return;}if(typeof this.persistAdStructureBarrier!=='function'){this.notify('广告系列未删除：云端持久化服务不可用');return}const beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),beforeSnapshot=clone(liveCampaign),beforeIndex=(c.adCampaigns||[]).indexOf(liveCampaign),targetId=String(liveCampaign.id);c.adCampaigns=(c.adCampaigns||[]).filter(x=>String(x.id)!==targetId);this.logAudit('删除广告系列',`${c.name} · ${liveCampaign.name||liveCampaign.planName||'未命名'}`);const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const liveClient=authoritativeClient();if(liveClient!==c)return;liveClient.adCampaigns=Array.isArray(liveClient.adCampaigns)?liveClient.adCampaigns:[];if(liveClient.adCampaigns.some(x=>String(x.id)===targetId))return;const at=Math.max(0,Math.min(beforeIndex,liveClient.adCampaigns.length));liveClient.adCampaigns.splice(at,0,clone(beforeSnapshot))};return Promise.resolve(this.persistAdStructureBarrier()).then(()=>{this.notify('广告系列已删除')},e=>{rollback();this.persist();this.notify(`广告系列未删除：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})})}''',
'addAdSet': r'''addAdSet(campaign){if(!campaign)return;const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),c=this.selectedAdsClient,currentCampaign=(c?.adCampaigns||[]).find(x=>String(x.id)===String(campaign.id));if(!currentCampaign){this.notify('该广告系列已不存在，请刷新页面后重试');return;}if(typeof this.persistAdStructureBarrier!=='function'){this.notify('广告组未添加：云端持久化服务不可用');return}const clientId=String(c.id),campaignId=String(currentCampaign.id),beforeWasArray=Array.isArray(currentCampaign.adSets),beforeContainer=beforeWasArray?null:clone(currentCampaign.adSets),attempt=this.emptyAdSet(),attemptSnapshot=clone(attempt);currentCampaign.adSets=beforeWasArray?currentCampaign.adSets:[];currentCampaign.adSets.push(attempt);const authoritativeClient=()=>Array.isArray(this.clients)?this.clients.find(x=>String(x.id)===clientId):this.selectedAdsClient,rollback=()=>{const liveClient=authoritativeClient();if(liveClient!==c)return;const liveCampaign=(liveClient.adCampaigns||[]).find(x=>String(x.id)===campaignId);if(liveCampaign!==currentCampaign)return;liveCampaign.adSets=Array.isArray(liveCampaign.adSets)?liveCampaign.adSets:[];const i=liveCampaign.adSets.findIndex(x=>String(x.id)===String(attempt.id));if(i>=0&&liveCampaign.adSets[i]===attempt&&same(liveCampaign.adSets[i],attemptSnapshot)){liveCampaign.adSets.splice(i,1);if(!beforeWasArray&&liveCampaign.adSets.length===0)liveCampaign.adSets=clone(beforeContainer)}};return Promise.resolve(this.persistAdStructureBarrier()).then(()=>{this.notify('已添加广告组')},e=>{rollback();this.persist();this.notify(`广告组未添加：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})}''',
'removeAdSet': r'''removeAdSet(campaign,adset){if(!campaign||!adset)return;const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),c=this.selectedAdsClient;if(!c)return;const clientId=String(c.id),authoritativeClient=()=>Array.isArray(this.clients)?this.clients.find(x=>String(x.id)===clientId):this.selectedAdsClient,campaignById=()=>((c.adCampaigns||[]).find(x=>String(x.id)===String(campaign.id)));const adSetById=()=>{const liveCampaign=campaignById();return (liveCampaign?.adSets||[]).find(x=>String(x.id)===String(adset.id));};const currentAdSet=adSetById();if(!currentAdSet){this.notify('该广告组已不存在，请刷新页面后重试');return;}this.askConfirm({title:'删除广告组',message:`确定删除广告组【${currentAdSet.name||'未命名广告组'}】吗？\n其中 ${(currentAdSet.ads||[]).length} 个广告也会一并删除。`,confirmText:'确认删除'},()=>{if(authoritativeClient()!==c||this.selectedAdsClient!==c){this.notify('当前广告客户状态已变化，请重新确认删除');return}const liveCampaign=campaignById(),liveAdSet=adSetById();if(!liveCampaign||!liveAdSet){this.notify('该广告组已不存在，请刷新页面后重试');return;}if(typeof this.persistAdStructureBarrier!=='function'){this.notify('广告组未删除：云端持久化服务不可用');return}const beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),beforeSnapshot=clone(liveAdSet),beforeIndex=(liveCampaign.adSets||[]).indexOf(liveAdSet),campaignObject=liveCampaign,targetId=String(liveAdSet.id);liveCampaign.adSets=(liveCampaign.adSets||[]).filter(x=>String(x.id)!==targetId);this.logAudit('删除广告组',liveAdSet.name||'未命名广告组');const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const liveClient=authoritativeClient();if(liveClient!==c)return;const currentParent=(liveClient.adCampaigns||[]).find(x=>String(x.id)===String(campaignObject.id));if(currentParent!==campaignObject)return;currentParent.adSets=Array.isArray(currentParent.adSets)?currentParent.adSets:[];if(currentParent.adSets.some(x=>String(x.id)===targetId))return;const at=Math.max(0,Math.min(beforeIndex,currentParent.adSets.length));currentParent.adSets.splice(at,0,clone(beforeSnapshot))};return Promise.resolve(this.persistAdStructureBarrier()).then(()=>{this.notify('广告组已删除')},e=>{rollback();this.persist();this.notify(`广告组未删除：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})})}''',
'addCreative': r'''addCreative(adset){if(!adset)return;const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b),c=this.selectedAdsClient,adSetMatches=(c?.adCampaigns||[]).flatMap(x=>(x.adSets||[]).filter(s=>String(s.id)===String(adset.id)));if(adSetMatches.length!==1){this.notify('该广告组已不存在或无法唯一定位，请刷新页面后重试');return;}if(typeof this.persistAdStructureBarrier!=='function'){this.notify('广告未添加：云端持久化服务不可用');return}const currentAdSet=adSetMatches[0],clientId=String(c.id),beforeWasArray=Array.isArray(currentAdSet.ads),beforeContainer=beforeWasArray?null:clone(currentAdSet.ads),attempt=this.emptyCreative(),attemptSnapshot=clone(attempt);currentAdSet.ads=beforeWasArray?currentAdSet.ads:[];currentAdSet.ads.push(attempt);const authoritativeClient=()=>Array.isArray(this.clients)?this.clients.find(x=>String(x.id)===clientId):this.selectedAdsClient,liveMatches=()=>{const liveClient=authoritativeClient();if(liveClient!==c)return [];return (liveClient.adCampaigns||[]).flatMap(x=>(x.adSets||[]).filter(s=>String(s.id)===String(currentAdSet.id)));},rollback=()=>{const matches=liveMatches();if(matches.length!==1||matches[0]!==currentAdSet)return;currentAdSet.ads=Array.isArray(currentAdSet.ads)?currentAdSet.ads:[];const i=currentAdSet.ads.findIndex(x=>String(x.id)===String(attempt.id));if(i>=0&&currentAdSet.ads[i]===attempt&&same(currentAdSet.ads[i],attemptSnapshot)){currentAdSet.ads.splice(i,1);if(!beforeWasArray&&currentAdSet.ads.length===0)currentAdSet.ads=clone(beforeContainer)}};return Promise.resolve(this.persistAdStructureBarrier()).then(()=>{this.notify('已添加广告')},e=>{rollback();this.persist();this.notify(`广告未添加：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})}''',
'removeCreative': r'''removeCreative(adset,ad){if(!adset||!ad)return;const clone=value=>value==null?value:JSON.parse(JSON.stringify(value)),c=this.selectedAdsClient;if(!c)return;const clientId=String(c.id),authoritativeClient=()=>Array.isArray(this.clients)?this.clients.find(x=>String(x.id)===clientId):this.selectedAdsClient,adSetById=()=>{const matches=(c.adCampaigns||[]).flatMap(x=>(x.adSets||[]).filter(s=>String(s.id)===String(adset.id)));return matches.length===1?matches[0]:null;};const adById=()=>{const liveAdSet=adSetById(),matches=(liveAdSet?.ads||[]).filter(x=>String(x.id)===String(ad.id));return matches.length===1?matches[0]:null;};const currentAdSet=adSetById(),currentAd=adById();if(!currentAdSet||!currentAd){this.notify('该广告已不存在或无法唯一定位，请刷新页面后重试');return;}this.askConfirm({title:'删除广告',message:`确定删除广告【${currentAd.name||'未命名广告'}】吗？`,confirmText:'确认删除'},()=>{if(authoritativeClient()!==c||this.selectedAdsClient!==c){this.notify('当前广告客户状态已变化，请重新确认删除');return}const liveAdSet=adSetById(),liveAd=adById();if(!liveAdSet||!liveAd){this.notify('该广告已不存在或无法唯一定位，请刷新页面后重试');return;}if(typeof this.persistAdStructureBarrier!=='function'){this.notify('广告未删除：云端持久化服务不可用');return}const beforeAudits=new Set(Array.isArray(this.auditLogs)?this.auditLogs:[]),beforeSnapshot=clone(liveAd),beforeIndex=(liveAdSet.ads||[]).indexOf(liveAd),parentObject=liveAdSet,targetId=String(liveAd.id);liveAdSet.ads=(liveAdSet.ads||[]).filter(x=>String(x.id)!==targetId);this.logAudit('删除广告',liveAd.name||'未命名广告');const attemptAudits=(Array.isArray(this.auditLogs)?this.auditLogs:[]).filter(row=>!beforeAudits.has(row)),rollback=()=>{if(Array.isArray(this.auditLogs)&&attemptAudits.length){const doomed=new Set(attemptAudits);for(let i=this.auditLogs.length-1;i>=0;i-=1)if(doomed.has(this.auditLogs[i]))this.auditLogs.splice(i,1)}const liveClient=authoritativeClient();if(liveClient!==c)return;const matches=(liveClient.adCampaigns||[]).flatMap(x=>(x.adSets||[]).filter(s=>String(s.id)===String(parentObject.id)));if(matches.length!==1||matches[0]!==parentObject)return;parentObject.ads=Array.isArray(parentObject.ads)?parentObject.ads:[];if(parentObject.ads.some(x=>String(x.id)===targetId))return;const at=Math.max(0,Math.min(beforeIndex,parentObject.ads.length));parentObject.ads.splice(at,0,clone(beforeSnapshot))};return Promise.resolve(this.persistAdStructureBarrier()).then(()=>{this.notify('广告已删除')},e=>{rollback();this.persist();this.notify(`广告未删除：云端保存失败，已恢复原状态：${e?.message||'保存失败'}`)})})}''',
}

required = {
    'addAdCampaign': ('selectedAdsAccount', 'emptyAdCampaign()', 'this.persist()', "this.notify('已添加广告系列')"),
    'editAdCampaign': ('currentCampaign.isSaved=false', 'this.persist()', "this.notify('已打开方案编辑器')"),
    'removeAdCampaign': ('campaignById', 'askConfirm', 'this.persist()', "logAudit('删除广告系列'", "this.notify('广告系列已删除')"),
    'addAdSet': ('currentCampaign', 'emptyAdSet()', 'this.persist()', "this.notify('已添加广告组')"),
    'removeAdSet': ('adSetById', 'askConfirm', 'this.persist()', "logAudit('删除广告组'", "this.notify('广告组已删除')"),
    'addCreative': ('adSetMatches.length!==1', 'emptyCreative()', 'this.persist()', "this.notify('已添加广告')"),
    'removeCreative': ('adById', 'askConfirm', 'this.persist()', "logAudit('删除广告'", "this.notify('广告已删除')"),
}

counts = {name: 0 for name in replacements}
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text
    for name, replacement in replacements.items():
        bounds = method_bounds(text, name)
        if bounds is None:
            continue
        counts[name] += 1
        start, end = bounds
        source = text[start:end].strip().rstrip(',').strip()
        missing = [marker for marker in required[name] if marker not in source]
        if missing:
            fail(f'{name} reviewed source drifted: ' + ', '.join(missing))
        if 'persistAdStructureBarrier' in source:
            fail(f'{name} already contains ad structure durability barrier')
        text = text[:start] + replacement + text[end:]
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

for name, count in counts.items():
    if count != 1:
        fail(f'{name} expected in exactly one app artifact, found {count}')
if len(changed) != 1:
    fail(f'expected exactly one changed app artifact, found {len(changed)}')

print(
    'AD_STRUCTURE_PERSISTENCE_ACK_FINALIZE_OK: '
    'campaign+adset+creative add/edit/delete=cloud-ack-before-success-ui; '
    'delete-audits=attempt-owned+rollback-on-failure; failure=operation-owned-nested-state+rollback-persisted; '
    'concurrency=client+parent+same-id-replacement+field-level-preserved; confirm-time-client-identity=rechecked; '
    'missing-barrier=fail-closed; save-queue=shared-flushSave; '
    f'adapter={adapter_sha}; app={changed[0][0]}:{changed[0][1]}'
)
