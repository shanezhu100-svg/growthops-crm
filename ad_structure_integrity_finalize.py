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


def patch_edit_campaign(source: str) -> str:
    anchor = "if(!campaign)return;campaign.isSaved=false;"
    replacement = (
        "if(!campaign)return;"
        "const currentCampaign=(this.selectedAdsClient?.adCampaigns||[]).find(x=>String(x.id)===String(campaign.id));"
        "if(!currentCampaign){this.notify('该广告系列已不存在，请刷新页面后重试');return;}"
        "currentCampaign.isSaved=false;"
    )
    if source.count(anchor) != 1:
        fail(f'editAdCampaign stale-edit anchor count={source.count(anchor)}')
    return source.replace(anchor, replacement, 1)


def patch_remove_campaign(source: str) -> str:
    old_head = (
        "const c=this.selectedAdsClient;if(!c||!campaign)return;"
        "const adSetCount=(campaign.adSets||[]).length,adCount=(campaign.adSets||[]).reduce((n,s)=>n+(s.ads||[]).length,0);"
    )
    new_head = (
        "const c=this.selectedAdsClient;if(!c||!campaign)return;"
        "const campaignById=()=>((c.adCampaigns||[]).find(x=>String(x.id)===String(campaign.id))),currentCampaign=campaignById();"
        "if(!currentCampaign){this.notify('该广告系列已不存在，请刷新页面后重试');return;}"
        "const adSetCount=(currentCampaign.adSets||[]).length,adCount=(currentCampaign.adSets||[]).reduce((n,s)=>n+(s.ads||[]).length,0);"
    )
    if source.count(old_head) != 1:
        fail(f'removeAdCampaign live-target head anchor count={source.count(old_head)}')
    source = source.replace(old_head, new_head, 1)
    source = source.replace(
        "campaign.name||campaign.planName||'未命名广告系列'",
        "currentCampaign.name||currentCampaign.planName||'未命名广告系列'",
        1,
    )
    callback_old = "confirmText:'确认删除'},()=>{c.adCampaigns=(c.adCampaigns||[]).filter(x=>String(x.id)!==String(campaign.id));this.persist();this.logAudit('删除广告系列',`${c.name} · ${campaign.name||campaign.planName||'未命名'}`);"
    callback_new = "confirmText:'确认删除'},()=>{const liveCampaign=campaignById();if(!liveCampaign){this.notify('该广告系列已不存在，请刷新页面后重试');return;}c.adCampaigns=(c.adCampaigns||[]).filter(x=>String(x.id)!==String(liveCampaign.id));this.persist();this.logAudit('删除广告系列',`${c.name} · ${liveCampaign.name||liveCampaign.planName||'未命名'}`);"
    if source.count(callback_old) != 1:
        fail(f'removeAdCampaign confirmation recheck anchor count={source.count(callback_old)}')
    return source.replace(callback_old, callback_new, 1)


def patch_add_set(source: str) -> str:
    anchor = "if(!campaign)return;campaign.adSets=Array.isArray(campaign.adSets)?campaign.adSets:[];campaign.adSets.push(this.emptyAdSet());"
    replacement = (
        "if(!campaign)return;"
        "const currentCampaign=(this.selectedAdsClient?.adCampaigns||[]).find(x=>String(x.id)===String(campaign.id));"
        "if(!currentCampaign){this.notify('该广告系列已不存在，请刷新页面后重试');return;}"
        "currentCampaign.adSets=Array.isArray(currentCampaign.adSets)?currentCampaign.adSets:[];"
        "currentCampaign.adSets.push(this.emptyAdSet());"
    )
    if source.count(anchor) != 1:
        fail(f'addAdSet live-parent anchor count={source.count(anchor)}')
    return source.replace(anchor, replacement, 1)


def patch_remove_set(source: str) -> str:
    head_anchor = "if(!campaign||!adset)return;this.askConfirm("
    head_replacement = (
        "if(!campaign||!adset)return;"
        "const campaignById=()=>((this.selectedAdsClient?.adCampaigns||[]).find(x=>String(x.id)===String(campaign.id)));"
        "const adSetById=()=>{const liveCampaign=campaignById();return (liveCampaign?.adSets||[]).find(x=>String(x.id)===String(adset.id));};"
        "const currentAdSet=adSetById();"
        "if(!currentAdSet){this.notify('该广告组已不存在，请刷新页面后重试');return;}"
        "this.askConfirm("
    )
    if source.count(head_anchor) != 1:
        fail(f'removeAdSet live-target head anchor count={source.count(head_anchor)}')
    source = source.replace(head_anchor, head_replacement, 1)
    source = source.replace("adset.name||'未命名广告组'", "currentAdSet.name||'未命名广告组'", 1)
    source = source.replace("(adset.ads||[]).length", "(currentAdSet.ads||[]).length", 1)
    callback_old = "confirmText:'确认删除'},()=>{campaign.adSets=(campaign.adSets||[]).filter(x=>String(x.id)!==String(adset.id));this.persist();this.logAudit('删除广告组',adset.name||'未命名广告组');"
    callback_new = (
        "confirmText:'确认删除'},()=>{const liveCampaign=campaignById(),liveAdSet=adSetById();"
        "if(!liveCampaign||!liveAdSet){this.notify('该广告组已不存在，请刷新页面后重试');return;}"
        "liveCampaign.adSets=(liveCampaign.adSets||[]).filter(x=>String(x.id)!==String(liveAdSet.id));"
        "this.persist();this.logAudit('删除广告组',liveAdSet.name||'未命名广告组');"
    )
    if source.count(callback_old) != 1:
        fail(f'removeAdSet confirmation recheck anchor count={source.count(callback_old)}')
    return source.replace(callback_old, callback_new, 1)


def patch_add_creative(source: str) -> str:
    anchor = "if(!adset)return;adset.ads=Array.isArray(adset.ads)?adset.ads:[];adset.ads.push(this.emptyCreative());"
    replacement = (
        "if(!adset)return;"
        "const adSetMatches=(this.selectedAdsClient?.adCampaigns||[]).flatMap(c=>(c.adSets||[]).filter(s=>String(s.id)===String(adset.id)));"
        "if(adSetMatches.length!==1){this.notify('该广告组已不存在或无法唯一定位，请刷新页面后重试');return;}"
        "const currentAdSet=adSetMatches[0];"
        "currentAdSet.ads=Array.isArray(currentAdSet.ads)?currentAdSet.ads:[];"
        "currentAdSet.ads.push(this.emptyCreative());"
    )
    if source.count(anchor) != 1:
        fail(f'addCreative live-parent anchor count={source.count(anchor)}')
    return source.replace(anchor, replacement, 1)


def patch_remove_creative(source: str) -> str:
    head_anchor = "if(!adset||!ad)return;this.askConfirm("
    head_replacement = (
        "if(!adset||!ad)return;"
        "const adSetById=()=>{const matches=(this.selectedAdsClient?.adCampaigns||[]).flatMap(c=>(c.adSets||[]).filter(s=>String(s.id)===String(adset.id)));return matches.length===1?matches[0]:null;};"
        "const adById=()=>{const liveAdSet=adSetById(),matches=(liveAdSet?.ads||[]).filter(x=>String(x.id)===String(ad.id));return matches.length===1?matches[0]:null;};"
        "const currentAdSet=adSetById(),currentAd=adById();"
        "if(!currentAdSet||!currentAd){this.notify('该广告已不存在或无法唯一定位，请刷新页面后重试');return;}"
        "this.askConfirm("
    )
    if source.count(head_anchor) != 1:
        fail(f'removeCreative live-target head anchor count={source.count(head_anchor)}')
    source = source.replace(head_anchor, head_replacement, 1)
    source = source.replace("ad.name||'未命名广告'", "currentAd.name||'未命名广告'", 1)
    callback_old = "confirmText:'确认删除'},()=>{adset.ads=(adset.ads||[]).filter(x=>String(x.id)!==String(ad.id));this.persist();this.logAudit('删除广告',ad.name||'未命名广告');"
    callback_new = (
        "confirmText:'确认删除'},()=>{const liveAdSet=adSetById(),liveAd=adById();"
        "if(!liveAdSet||!liveAd){this.notify('该广告已不存在或无法唯一定位，请刷新页面后重试');return;}"
        "liveAdSet.ads=(liveAdSet.ads||[]).filter(x=>String(x.id)!==String(liveAd.id));"
        "this.persist();this.logAudit('删除广告',liveAd.name||'未命名广告');"
    )
    if source.count(callback_old) != 1:
        fail(f'removeCreative confirmation recheck anchor count={source.count(callback_old)}')
    return source.replace(callback_old, callback_new, 1)


found = {
    'editAdCampaign': 0,
    'removeAdCampaign': 0,
    'addAdSet': 0,
    'removeAdSet': 0,
    'addCreative': 0,
    'removeCreative': 0,
}
changed = []
for path in files:
    text = path.read_text(encoding='utf-8')
    original = text
    text, did_edit = replace_method(text, 'editAdCampaign', patch_edit_campaign)
    if did_edit:
        found['editAdCampaign'] += 1
    text, did_remove = replace_method(text, 'removeAdCampaign', patch_remove_campaign)
    if did_remove:
        found['removeAdCampaign'] += 1
    text, did_add_set = replace_method(text, 'addAdSet', patch_add_set)
    if did_add_set:
        found['addAdSet'] += 1
    text, did_remove_set = replace_method(text, 'removeAdSet', patch_remove_set)
    if did_remove_set:
        found['removeAdSet'] += 1
    text, did_add_creative = replace_method(text, 'addCreative', patch_add_creative)
    if did_add_creative:
        found['addCreative'] += 1
    text, did_remove_creative = replace_method(text, 'removeCreative', patch_remove_creative)
    if did_remove_creative:
        found['removeCreative'] += 1
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append((path.name, hashlib.sha256(text.encode('utf-8')).hexdigest()))

for name, count in found.items():
    if count != 1:
        fail(f'{name} expected in exactly one app-inline artifact, found {count}')
if len(changed) != 1:
    fail(f'expected exactly one changed artifact, found {len(changed)}')

print(
    'AD_STRUCTURE_INTEGRITY_FINALIZE_OK: '
    'campaign-edit=live-selected-client-id-required; '
    'campaign-delete=live-target-before-confirm+rechecked-on-confirm; '
    'adset-add=live-campaign-required; '
    'adset-delete=live-target-before-confirm+rechecked-on-confirm; '
    'creative-add=unique-live-adset-required; '
    'creative-delete=unique-live-target-before-confirm+rechecked-on-confirm; '
    'stale=denied-before-mutation+persist+audit; '
    f'artifact={changed[0][0]}:{changed[0][1][:12]}'
)
