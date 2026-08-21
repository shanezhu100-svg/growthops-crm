from pathlib import Path
import hashlib, re

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

# Keep one navigation authority: the original Vue navigateTo() method.
# Top-level module-home entry is expressed as a boolean argument instead of a
# second wrapper method, so aggregate sentinels cannot be written and then
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
    "else if(page==='analytics')this.selectedAnalyticsClientId=0;"
    "else if(page==='sop')this.selectedSopClientId=0;}"
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

# SOP now has the same explicit aggregate-home model as Assets / Ads / Analytics.
sop_select_old='<option :value="null">请选择客户</option><option v-for="c in activeClients" :value="c.id" :key="c.id">{{ c.name }}</option>'
sop_select_new='<option :value="0">所有客户</option><option v-for="c in activeClients" :value="c.id" :key="c.id">{{ c.name }}</option>'
if html.count(sop_select_old)!=1:
    raise SystemExit(f'Unexpected SOP client selector option count: {html.count(sop_select_old)}')
html=html.replace(sop_select_old,sop_select_new,1)

# Add aggregate SOP computed data beside the existing SOP computed properties.
sop_computed_marker="    completedSopCount(){return this.selectedSopSteps.filter(step=>!!this.sopChecked[step.id]).length},"
if html.count(sop_computed_marker)!=1:
    raise SystemExit(f'Unexpected completedSopCount marker count: {html.count(sop_computed_marker)}')
sop_computed=r'''    sopAllClientRows(){const today=this.localDateKey();return this.activeClients.map(c=>{const fb=c.fbAccounts||[],tk=c.tkAccounts||[],keys=[...fb.map(a=>`FB:${a.id}`),...tk.map(a=>`TK:${a.id}`)],configs=c.sopAccountConfigs&&typeof c.sopAccountConfigs==='object'?c.sopAccountConfigs:{},configured=keys.filter(key=>configs[key]).length,todayTasks=keys.reduce((n,key)=>n+(Array.isArray(configs[key]?.dailyTasks?.[today])?configs[key].dailyTasks[today].length:0),0);return{client:c,fbAccounts:fb.length,tkAccounts:tk.length,accounts:keys.length,configured,todayTasks}}).sort((a,b)=>b.todayTasks-a.todayTasks||b.configured-a.configured||String(a.client.name).localeCompare(String(b.client.name),'zh-CN'))},
    sopAllAccountCount(){return this.sopAllClientRows.reduce((n,row)=>n+row.accounts,0)},
    sopAllConfiguredAccountCount(){return this.sopAllClientRows.reduce((n,row)=>n+row.configured,0)},
    sopAllTodayTaskCount(){return this.sopAllClientRows.reduce((n,row)=>n+row.todayTasks,0)},
'''+sop_computed_marker
html=html.replace(sop_computed_marker,sop_computed,1)

# Insert the all-client SOP landing view before the existing client/account detail view.
sop_detail_old='          <div v-if="selectedSopClient && selectedSopAccount" class="space-y-5">'
if html.count(sop_detail_old)!=1:
    raise SystemExit(f'Unexpected SOP detail root count: {html.count(sop_detail_old)}')
sop_home=r'''          <div v-if="selectedSopClientId===0" class="space-y-5">
            <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              <div class="bg-white border border-indigo-100 rounded-2xl p-5 soft-shadow"><div class="text-[10px] text-indigo-600 font-bold">在管客户</div><div class="text-2xl font-black text-indigo-700 mt-2">{{ activeClients.length }}</div><div class="text-[10px] text-slate-400 mt-1">所有未归档客户</div></div>
              <div class="bg-white border border-blue-100 rounded-2xl p-5 soft-shadow"><div class="text-[10px] text-blue-600 font-bold">可执行账号</div><div class="text-2xl font-black text-blue-700 mt-2">{{ sopAllAccountCount }}</div><div class="text-[10px] text-slate-400 mt-1">Facebook + TikTok</div></div>
              <div class="bg-white border border-violet-100 rounded-2xl p-5 soft-shadow"><div class="text-[10px] text-violet-600 font-bold">已配置 SOP 账号</div><div class="text-2xl font-black text-violet-700 mt-2">{{ sopAllConfiguredAccountCount }}</div><div class="text-[10px] text-slate-400 mt-1">已建立账号级执行配置</div></div>
              <div class="bg-slate-950 text-white rounded-2xl p-5 soft-shadow"><div class="text-[10px] text-emerald-300 font-bold">今日任务</div><div class="text-2xl font-black mt-2">{{ sopAllTodayTaskCount }}</div><div class="text-[10px] text-slate-400 mt-1">全部客户账号今日计划任务</div></div>
            </div>

            <div class="bg-white border border-slate-200 rounded-2xl soft-shadow overflow-hidden">
              <div class="p-5 border-b border-slate-100"><h3 class="font-extrabold text-sm">所有客户每日 SOP</h3><p class="text-[11px] text-slate-400 mt-1">先查看所有客户的账号与今日任务概况；点击「进入 SOP」后，再选择该客户的具体 Facebook / TikTok 账号执行任务。</p></div>
              <div class="overflow-x-auto scrollbar"><table class="w-full min-w-[920px] text-xs"><thead class="bg-slate-50 text-slate-500"><tr><th class="p-3.5 text-left">客户</th><th class="p-3.5 text-left">Facebook</th><th class="p-3.5 text-left">TikTok</th><th class="p-3.5 text-left">可执行账号</th><th class="p-3.5 text-left">已配置 SOP</th><th class="p-3.5 text-left">今日任务</th><th class="p-3.5 text-left">操作</th></tr></thead><tbody class="divide-y divide-slate-100"><tr v-for="row in sopAllClientRows" :key="row.client.id" class="hover:bg-slate-50/70"><td class="p-3.5"><div class="font-extrabold text-slate-900">{{ row.client.name }}</div><div class="text-[10px] text-slate-400 mt-1">{{ row.client.project || row.client.product || '客户项目' }}</div></td><td class="p-3.5"><span class="inline-flex px-2 py-1 rounded-lg bg-blue-50 text-blue-700 font-bold text-[10px]">{{ row.fbAccounts }} 个账户</span></td><td class="p-3.5"><span class="inline-flex px-2 py-1 rounded-lg bg-slate-100 text-slate-700 font-bold text-[10px]">{{ row.tkAccounts }} 个账户</span></td><td class="p-3.5 font-extrabold text-slate-700">{{ row.accounts }}</td><td class="p-3.5 font-extrabold text-violet-600">{{ row.configured }}</td><td class="p-3.5 font-black text-emerald-600">{{ row.todayTasks }}</td><td class="p-3.5"><button type="button" @click="selectedSopClientId=row.client.id; syncSopAccountSelection(true)" class="h-8 px-3 rounded-lg bg-indigo-50 text-indigo-700 font-bold text-[11px]"><i class="fa-solid fa-list-check mr-1"></i>进入 SOP</button></td></tr></tbody></table></div>
              <div v-if="!sopAllClientRows.length" class="py-12 text-center text-xs text-slate-400">暂无在管客户</div>
            </div>
          </div>

          <div v-else-if="selectedSopClient && selectedSopAccount" class="space-y-5">'''
html=html.replace(sop_detail_old,sop_home,1)

# When a concrete SOP client is selected but no account is active, show every
# executable FB/TikTok account directly in the page instead of hiding the only
# choices in the top-right select. The select remains available as a fast switch.
sop_account_empty_old='''          <div v-else-if="selectedSopClient && selectedSopAccounts.length" class="bg-white border border-slate-200 rounded-2xl py-16 text-center text-xs text-slate-400"><i class="fa-solid fa-arrow-up-right-dots text-3xl text-slate-200 block mb-3"></i><div class="font-bold text-slate-600">请选择执行账号</div><div class="mt-1">{{ selectedSopClient.name }} 有 {{ selectedSopAccounts.length }} 个 FB / TikTok 账号，请在右上角明确选择本次执行账号。</div><button type="button" @click="openClientDetail(selectedSopClient.id)" class="mt-4 h-9 px-4 rounded-xl border border-slate-200 bg-white text-xs font-bold text-slate-600 hover:bg-slate-50">查看 {{ selectedSopClient.name }} 资产</button></div>'''
if html.count(sop_account_empty_old)!=1:
    raise SystemExit(f'Unexpected SOP account-empty state count: {html.count(sop_account_empty_old)}')
sop_account_options=r'''          <div v-else-if="selectedSopClient && selectedSopAccounts.length" class="space-y-4">
            <div class="bg-white border border-slate-200 rounded-2xl p-5 soft-shadow">
              <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div><div class="font-extrabold text-sm text-slate-900">选择执行账号</div><p class="text-[11px] text-slate-400 mt-1">{{ selectedSopClient.name }} 有 {{ selectedSopAccounts.length }} 个可执行 FB / TikTok 账号，直接点击账号进入对应 SOP Checklist。</p></div>
                <button type="button" @click="openClientDetail(selectedSopClient.id,'sop')" class="h-9 px-4 rounded-xl border border-slate-200 bg-white text-xs font-bold text-slate-600 hover:bg-slate-50 shrink-0"><i class="fa-solid fa-box-archive mr-1.5"></i>查看客户资产</button>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 mt-5">
                <button v-for="item in selectedSopAccounts" :key="item.key" type="button" @click="selectedSopAccountKey=item.key; onSopAccountChange()" class="group text-left rounded-2xl border border-slate-200 bg-slate-50/70 p-4 hover:bg-white hover:border-indigo-300 hover:shadow-sm transition">
                  <div class="flex items-start gap-3">
                    <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" :class="item.platform==='FB'?'bg-blue-50 text-blue-600':'bg-slate-950 text-white'"><i :class="item.platform==='FB'?'fa-brands fa-facebook':'fa-brands fa-tiktok'"></i></div>
                    <div class="min-w-0 flex-1"><div class="flex items-center justify-between gap-2"><div class="font-extrabold text-sm text-slate-900 truncate">{{ item.account.accountName || item.account.adAccountId || '未命名账号' }}</div><i class="fa-solid fa-chevron-right text-[10px] text-slate-300 group-hover:text-indigo-500 shrink-0"></i></div><div class="text-[10px] font-bold mt-1" :class="item.platform==='FB'?'text-blue-600':'text-slate-600'">{{ item.platformName }}</div></div>
                  </div>
                  <div class="mt-4 grid grid-cols-1 gap-2 text-[10px]">
                    <div class="rounded-xl bg-white border border-slate-100 px-3 py-2"><div class="text-slate-400">广告账号 ID</div><div class="font-mono font-bold text-slate-700 mt-0.5 break-all">{{ item.account.adAccountId || '未录入' }}</div></div>
                    <div class="rounded-xl bg-white border border-slate-100 px-3 py-2"><div class="text-slate-400">{{ item.platform==='FB' ? 'BM ID' : 'BC ID' }}</div><div class="font-mono font-bold text-slate-700 mt-0.5 break-all">{{ item.platform==='FB' ? (item.account.bmId || '未录入') : (item.account.bcId || '未录入') }}</div></div>
                  </div>
                  <div class="mt-3 pt-3 border-t border-slate-200 flex items-center justify-between"><span class="text-[10px] text-slate-400">点击进入账号 SOP</span><span class="inline-flex items-center gap-1 text-[10px] font-extrabold text-indigo-600">进入 Checklist <i class="fa-solid fa-arrow-right text-[9px]"></i></span></div>
                </button>
              </div>
            </div>
          </div>'''
html=html.replace(sop_account_empty_old,sop_account_options,1)

# The visible module title is also an explicit return to that module's aggregate home.
title_specs=(
    ('投放数据分析','analytics','所有客户投放数据'),
    ('广告管理','ads','所有客户广告管理'),
    ('账号与商业资产','assets','全部客户账号资产'),
    ('每日 SOP 管理','sop','所有客户每日 SOP'),
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
    'MODULE_HOME_NAVIGATION_FINALIZE_OK: authority=navigateTo; sentinel-zero=valid; wrappers=removed; sop=all-clients+account-options; '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}'
)
