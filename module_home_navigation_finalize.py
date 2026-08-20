from pathlib import Path
import hashlib, re

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
bridge_path=root/'dist'/'cloud-ui-action-bridge.js'
html=index_path.read_text(encoding='utf-8')
bridge=bridge_path.read_text(encoding='utf-8')

# Module-home reset is deliberately separate from navigateTo(). Internal navigation
# (for example client-detail -> assets) must preserve the selected client.
method_marker="    navigateTo(page){"
if html.count("    showAllClientsForModule(page){"):
    raise SystemExit('Module-home reset already installed')
if html.count(method_marker)!=1:
    raise SystemExit(f'Unexpected navigateTo method count: {html.count(method_marker)}')
method=r'''    showAllClientsForModule(page){
      if(page==='assets')this.selectedAssetsClientId=0;
      else if(page==='ads')this.selectedAdsClientId=0;
      else if(page==='analytics')this.selectedAnalyticsClientId=0;
    },
    navigateTo(page){'''
html=html.replace(method_marker,method,1)

# The visible module title is a direct "back to this module's all-client home" action.
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
        f'@click="showAllClientsForModule(\'{page}\')" '
        f'@keydown.enter.prevent="showAllClientsForModule(\'{page}\')" '
        f'@keydown.space.prevent="showAllClientsForModule(\'{page}\')"'
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

# Sidebar navigation is rendered by the canonical app with runtime bindings that are
# not source-stable. Use a non-blocking capture listener in the existing UI bridge:
# let the native/Vue navigation finish, then reset only the three module selectors.
bridge_marker="  const protectPendingSave=event=>{"
if bridge.count('const MODULE_HOME_NAV_LABELS=')!=0:
    raise SystemExit('Module-home bridge listener already installed')
if bridge.count(bridge_marker)!=1:
    raise SystemExit(f'Unexpected UI bridge insertion marker count: {bridge.count(bridge_marker)}')
bridge_runtime=r"""  const MODULE_HOME_NAV_LABELS=new Map([
    ['账号与商业资产','assets'],
    ['广告管理','ads'],
    ['投放数据分析','analytics'],
  ]);
  document.addEventListener('click',event=>{
    const control=event.target?.closest?.('button,a,[role="button"]');
    if(!control||!control.closest('aside'))return;
    const page=MODULE_HOME_NAV_LABELS.get(text(control));
    if(!page)return;
    queueMicrotask(()=>{
      if(vm.currentPage!==page)return;
      vm.showAllClientsForModule?.(page);
    });
  },true);

"""
bridge=bridge.replace(bridge_marker,bridge_runtime+bridge_marker,1)

index_path.write_text(html,encoding='utf-8')
bridge_path.write_text(bridge,encoding='utf-8')
print(
    'MODULE_HOME_NAVIGATION_FINALIZE_OK: '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}; '
    f'bridge={hashlib.sha256(bridge_path.read_bytes()).hexdigest()}'
)
