from pathlib import Path
import hashlib, re

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

# One authoritative module-home entry point. Internal calls to navigateTo() remain
# untouched so client-detail returns and other in-module navigation keep context.
method_marker="    navigateTo(page){"
if html.count("    navigateToModuleHome(page){"):
    raise SystemExit('Module-home navigation already installed')
if html.count(method_marker)!=1:
    raise SystemExit(f'Unexpected navigateTo method count: {html.count(method_marker)}')
method=r'''    navigateToModuleHome(page){
      if(page==='assets')this.selectedAssetsClientId=0;
      else if(page==='ads')this.selectedAdsClientId=0;
      else if(page==='analytics')this.selectedAnalyticsClientId=0;
      this.navigateTo(page);
    },
    navigateTo(page){'''
html=html.replace(method_marker,method,1)

# Patch the real canonical desktop and mobile sidebar bindings directly. Do not
# add a second document/bridge click listener that can race with Vue navigation.
desktop_old='@click="navigateTo(item.key)"'
desktop_new='@click="navigateToModuleHome(item.key)"'
mobile_old='@click="navigateTo(item.key); mobileMenuOpen=false"'
mobile_new='@click="navigateToModuleHome(item.key); mobileMenuOpen=false"'
if html.count(desktop_old)!=1:
    raise SystemExit(f'Unexpected desktop sidebar binding count: {html.count(desktop_old)}')
if html.count(mobile_old)!=1:
    raise SystemExit(f'Unexpected mobile sidebar binding count: {html.count(mobile_old)}')
html=html.replace(desktop_old,desktop_new,1)
html=html.replace(mobile_old,mobile_new,1)

# The visible module title is also an explicit return to that module's all-client home.
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
        f'@click="navigateToModuleHome(\'{page}\')" '
        f'@keydown.enter.prevent="navigateToModuleHome(\'{page}\')" '
        f'@keydown.space.prevent="navigateToModuleHome(\'{page}\')"'
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
    'MODULE_HOME_NAVIGATION_FINALIZE_OK: authoritative=vue-sidebar; '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}'
)
