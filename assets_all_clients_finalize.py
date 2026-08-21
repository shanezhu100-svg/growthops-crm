from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
security_path=root/'dist'/'cloud-security-hotfix.js'
html=index_path.read_text(encoding='utf-8')
security=security_path.read_text(encoding='utf-8')

# 1) Add an explicit aggregate option to the account-assets client selector.
select_start=html.find('<select v-model.number="selectedAssetsClientId"')
if select_start<0:
    raise SystemExit('Account-assets client selector not found')
select_open_end=html.find('>',select_start)
select_close=html.find('</select>',select_open_end)
if select_open_end<0 or select_close<0:
    raise SystemExit('Account-assets client selector boundaries not found')
select_body=html[select_open_end+1:select_close]
if '全部客户' in select_body:
    raise SystemExit('Account-assets aggregate option already exists before finalizer')
html=html[:select_open_end+1]+'\n                <option :value="0">全部客户</option>'+html[select_open_end+1:]

# 2) Hide the single-client shortcut when aggregate mode is selected.
old_detail='<button v-if="selectedAssetsClient" @click="openClientDetail(selectedAssetsClient.id)"'
new_detail='<button v-if="selectedAssetsClient && selectedAssetsClientId!==0" @click="openClientDetail(selectedAssetsClient.id)"'
if html.count(old_detail)!=1:
    raise SystemExit(f'Unexpected account-assets detail shortcut count: {html.count(old_detail)}')
html=html.replace(old_detail,new_detail,1)

# 3) Insert a real all-client asset overview before the existing single-client detail block.
single_marker='<div v-if="selectedAssetsClient" class="space-y-5">'
if html.count(single_marker)!=1:
    raise SystemExit(f'Unexpected single-client asset block count: {html.count(single_marker)}')
all_clients_block=r'''<div v-if="selectedAssetsClientId===0" class="space-y-5">
              <div class="grid grid-cols-2 xl:grid-cols-5 gap-3">
                <div class="bg-white border border-indigo-100 rounded-2xl p-4 soft-shadow"><div class="text-[10px] font-bold text-indigo-600">全部客户</div><div class="text-2xl font-black text-indigo-700 mt-1">{{ clients.length }}</div><div class="text-[10px] text-slate-400 mt-1">客户档案总数</div></div>
                <div class="bg-white border border-blue-100 rounded-2xl p-4 soft-shadow"><div class="text-[10px] font-bold text-blue-600">Facebook</div><div class="text-2xl font-black text-blue-700 mt-1">{{ clients.reduce((n,c)=>n+(c.fbAccounts||[]).length,0) }}</div><div class="text-[10px] text-slate-400 mt-1">账号资产</div></div>
                <div class="bg-white border border-slate-200 rounded-2xl p-4 soft-shadow"><div class="text-[10px] font-bold text-slate-700">TikTok</div><div class="text-2xl font-black text-slate-900 mt-1">{{ clients.reduce((n,c)=>n+(c.tkAccounts||[]).length,0) }}</div><div class="text-[10px] text-slate-400 mt-1">账号资产</div></div>
                <div class="bg-white border border-red-100 rounded-2xl p-4 soft-shadow"><div class="text-[10px] font-bold text-red-600">Google</div><div class="text-2xl font-black text-red-600 mt-1">{{ clients.reduce((n,c)=>n+(c.googleAccounts||[]).length,0) }}</div><div class="text-[10px] text-slate-400 mt-1">账号资产</div></div>
                <div class="bg-white border border-fuchsia-100 rounded-2xl p-4 soft-shadow col-span-2 xl:col-span-1"><div class="text-[10px] font-bold text-fuchsia-600">Instagram</div><div class="text-2xl font-black text-fuchsia-700 mt-1">{{ clients.reduce((n,c)=>n+(c.instagramAccounts||[]).length,0) }}</div><div class="text-[10px] text-slate-400 mt-1">账号资产</div></div>
              </div>

              <div class="bg-white border border-slate-200 rounded-2xl soft-shadow overflow-hidden">
                <div class="p-5 border-b border-slate-100"><h3 class="font-extrabold text-sm">全部客户账号资产</h3><p class="text-[11px] text-slate-400 mt-1">汇总每个客户的 Facebook、TikTok、Google 与 Instagram 资产；点击“查看资产”进入该客户详细资料。</p></div>
                <div class="overflow-x-auto scrollbar">
                  <table class="w-full min-w-[920px] text-xs">
                    <thead class="bg-slate-50 text-slate-500"><tr><th class="p-3.5 text-left">客户</th><th class="p-3.5 text-center">Facebook</th><th class="p-3.5 text-center">TikTok</th><th class="p-3.5 text-center">Google</th><th class="p-3.5 text-center">Instagram</th><th class="p-3.5 text-center">资产合计</th><th class="p-3.5 text-right">操作</th></tr></thead>
                    <tbody class="divide-y divide-slate-100">
                      <tr v-for="c in clients" :key="`all-assets-${c.id}`" class="hover:bg-slate-50/70">
                        <td class="p-3.5"><div class="font-extrabold text-slate-900 flex items-center gap-2"><span>{{ c.name }}</span><span v-if="c.archived" class="px-1.5 py-0.5 rounded-md bg-slate-100 text-[9px] text-slate-400">已归档</span></div><div class="text-[10px] text-slate-400 mt-1">{{ c.project || c.product || '客户项目' }}</div></td>
                        <td class="p-3.5 text-center"><span class="inline-flex min-w-[34px] justify-center px-2 py-1 rounded-lg bg-blue-50 text-blue-700 font-bold">{{ (c.fbAccounts||[]).length }}</span></td>
                        <td class="p-3.5 text-center"><span class="inline-flex min-w-[34px] justify-center px-2 py-1 rounded-lg bg-slate-100 text-slate-700 font-bold">{{ (c.tkAccounts||[]).length }}</span></td>
                        <td class="p-3.5 text-center"><span class="inline-flex min-w-[34px] justify-center px-2 py-1 rounded-lg bg-red-50 text-red-600 font-bold">{{ (c.googleAccounts||[]).length }}</span></td>
                        <td class="p-3.5 text-center"><span class="inline-flex min-w-[34px] justify-center px-2 py-1 rounded-lg bg-fuchsia-50 text-fuchsia-700 font-bold">{{ (c.instagramAccounts||[]).length }}</span></td>
                        <td class="p-3.5 text-center font-black text-slate-800">{{ (c.fbAccounts||[]).length+(c.tkAccounts||[]).length+(c.googleAccounts||[]).length+(c.instagramAccounts||[]).length }}</td>
                        <td class="p-3.5 text-right"><button type="button" @click="selectedAssetsClientId=c.id" class="h-8 px-3 rounded-lg bg-indigo-50 text-indigo-700 text-[11px] font-bold hover:bg-indigo-100"><i class="fa-regular fa-folder-open mr-1"></i>查看资产</button></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-if="!clients.length" class="py-12 text-center text-xs text-slate-400">暂无客户资料</div>
              </div>
            </div>

            <div v-else-if="selectedAssetsClient" class="space-y-5">'''
html=html.replace(single_marker,all_clients_block,1)

# 4) In aggregate mode, never resolve a stale/visible client for credential RPCs.
resolver_marker='''    if(isAccountAssetPage()){\n      const visibleClientId=resolveVisibleClientId();\n      if(visibleClientId)return visibleClientId;\n'''
resolver_replacement='''    if(isAccountAssetPage()){\n      const explicitAssetsClientId=vm.selectedAssetsClientId;\n      const explicitAssetsClientText=String(explicitAssetsClientId??'');\n      if(explicitAssetsClientText==='0'||explicitAssetsClientText.toUpperCase()==='ALL')return '';\n      if(explicitAssetsClientId!==undefined&&explicitAssetsClientId!==null&&explicitAssetsClientText!=='')return explicitAssetsClientText;\n      const visibleClientId=resolveVisibleClientId();\n      if(visibleClientId)return visibleClientId;\n'''
if security.count(resolver_marker)!=1:
    raise SystemExit(f'Unexpected account-assets credential resolver marker count: {security.count(resolver_marker)}')
security=security.replace(resolver_marker,resolver_replacement,1)

index_path.write_text(html,encoding='utf-8')
security_path.write_text(security,encoding='utf-8')
print('ASSETS_ALL_CLIENTS_FINALIZE_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest()+'; security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
