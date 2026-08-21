from pathlib import Path
import hashlib, re

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

# Keep one navigation authority: the original Vue navigateTo() method.
# Top-level module-home entry is expressed as a boolean argument instead of a
# second wrapper method, so the aggregate sentinel cannot be written and then
# immediately overwritten by normal navigation validation.
old_signature="    navigateTo(page){"
new_signature="    navigateTo(page,moduleHome=false){"
if html.count("    navigateToModuleHome(page){"):
    raise SystemExit('Legacy module-home wrapper must not exist before finalize')
if html.count(old_signature)!=1:
    raise SystemExit(f'Unexpected navigateTo signature count: {html.count(old_signature)}')
html=html.replace(old_signature,new_signature,1)

view_guard="if(!this.canViewPage(page)){this.notify('当前角色没有访问该页面的权限');return}"
module_home_guard=(
    view_guard+
    "if(moduleHome){if(page==='assets')this.selectedAssetsClientId=0;"
    "else if(page==='ads')this.selectedAdsClientId=0;"
    "else if(page==='analytics')this.selectedAnalyticsClientId=0;}"
)
if html.count(view_guard)!=1:
    raise SystemExit(f'Unexpected canViewPage guard count: {html.count(view_guard)}')
html=html.replace(view_guard,module_home_guard,1)

# Sentinel 0 is a valid aggregate selection. Only fall back to the first client
# when a non-zero concrete selection is stale or missing.
old_assets="if(page==='assets'&&!this.clients.some(c=>c.id===this.selectedAssetsClientId))this.selectedAssetsClientId=this.clients[0]?.id||null;"
new_assets="if(page==='assets'&&Number(this.selectedAssetsClientId)!==0&&!this.clients.some(c=>c.id===this.selectedAssetsClientId))this.selectedAssetsClientId=this.clients[0]?.id||null;"
old_analytics="if(page==='analytics'){if(!this.clients.some(c=>c.id===this.selectedAnalyticsClientId))this.selectedAnalyticsClientId=this.clients[0]?.id||null;this.syncAnalyticsAccountSelection()}"
new_analytics="if(page==='analytics'){if(Number(this.selectedAnalyticsClientId)!==0&&!this.clients.some(c=>c.id===this.selectedAnalyticsClientId))this.selectedAnalyticsClientId=this.clients[0]?.id||null;this.syncAnalyticsAccountSelection()}"
old_ads="if(page==='ads'){if(!this.clients.some(c=>c.id===this.selectedAdsClientId))this.selectedAdsClientId=this.clients[0]?.id||null;this.syncAdsAccountSelection()}"
new_ads="if(page==='ads'){if(Number(this.selectedAdsClientId)!==0&&!this.clients.some(c=>c.id===this.selectedAdsClientId))this.selectedAdsClientId=this.clients[0]?.id||null;this.syncAdsAccountSelection()}"
for old,new,label in (
    (old_assets,new_assets,'assets'),
    (old_analytics,new_analytics,'analytics'),
    (old_ads,new_ads,'ads'),
):
    if html.count(old)!=1:
        raise SystemExit(f'Unexpected {label} navigation validation count: {html.count(old)}')
    html=html.replace(old,new,1)

# Patch the real canonical desktop and mobile sidebar bindings directly. Internal
# calls remain plain navigateTo(page), preserving client-detail source context.
desktop_old='@click="navigateTo(item.key)"'
desktop_new='@click="navigateTo(item.key,true)"'
mobile_old='@click="navigateTo(item.key); mobileMenuOpen=false"'
mobile_new='@click="navigateTo(item.key,true); mobileMenuOpen=false"'
if html.count(desktop_old)!=1:
    raise SystemExit(f'Unexpected desktop sidebar binding count: {html.count(desktop_old)}')
if html.count(mobile_old)!=1:
    raise SystemExit(f'Unexpected mobile sidebar binding count: {html.count(mobile_old)}')
html=html.replace(desktop_old,desktop_new,1)
html=html.replace(mobile_old,mobile_new,1)

# The visible module title is also an explicit return to that module's aggregate home.
title_specs=(
    ('投放数据分析','analytics','所有客户投放数据'),
    ('广告管理','ads','所有客户广告管理'),
    ('账号与商业资产','assets','全部客户账号资产'),
)
for title,page,home_label in title_specs:
    pattern=re.compile(rf'<(?P<tag>h[1-3])(?P<attrs>[^>]*)>{re.escape(title)}</(?P=tag)>')
    matches=list(pattern.finditer(html))
    if len(matches)!=1:
        raise SystemExit(f'Unexpected title count for {title}: {len(matches)}')
    m=matches[0]
    attrs=m.group('attrs')
    if '@click=' in attrs or 'data-growthops-module-home' in attrs:
        raise SystemExit(f'Title already has click behavior: {title}')
    extra=(
        f' data-growthops-module-home="{page}" role="button" tabindex="0" '
        f'title="返回{home_label}" '
        f'@click="navigateTo(\'{page}\',true)" '
        f'@keydown.enter.prevent="navigateTo(\'{page}\',true)" '
        f'@keydown.space.prevent="navigateTo(\'{page}\',true)"'
    )
    replacement=f'<{m.group("tag")}{attrs}{extra}>{title}</{m.group("tag")}>'
    html=html[:m.start()]+replacement+html[m.end():]

style="""<style id="growthops-module-home-navigation-style">
[data-growthops-module-home]{cursor:pointer}
[data-growthops-module-home]:hover{opacity:.78}
[data-growthops-module-home]:focus-visible{outline:2px solid #6366f1;outline-offset:4px;border-radius:4px}
</style>"""
if 'growthops-module-home-navigation-style' in html:
    raise SystemExit('Module-home navigation style already installed')
if html.count('</head>')!=1:
    raise SystemExit('Unexpected HTML head ending')
html=html.replace('</head>',style+'</head>',1)

index_path.write_text(html,encoding='utf-8')
print(
    'MODULE_HOME_NAVIGATION_FINALIZE_OK: authority=navigateTo; sentinel-zero=valid; wrappers=removed; '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}'
)
