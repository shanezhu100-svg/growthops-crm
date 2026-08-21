from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

# Layout-only refinement for the visible SOP account chooser. Navigation and
# account-selection behavior stay owned by module_home_navigation_finalize.py.
# Replace the single mixed FB/TikTok grid with two explicit platform groups,
# while preserving the same card click action and account metadata.
chooser_start_marker='          <div v-else-if="selectedSopClient && selectedSopAccounts.length" class="space-y-4">'
chooser_end_marker='          <div v-else-if="selectedSopClient" class="bg-white border border-slate-200 rounded-2xl py-16 text-center text-xs text-slate-400">'
start=html.find(chooser_start_marker)
end=html.find(chooser_end_marker,start)
if start<0 or end<=start:
    raise SystemExit('Unable to bound SOP account chooser block')
old_block=html[start:end]
if old_block.count('v-for="item in selectedSopAccounts"')!=1:
    raise SystemExit('Unexpected mixed SOP account list before grouping')
if 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 mt-5' not in old_block:
    raise SystemExit('Expected pre-layout SOP account grid missing')

new_block=r'''          <div v-else-if="selectedSopClient && selectedSopAccounts.length" class="space-y-4">
            <div class="bg-white border border-slate-200 rounded-2xl p-5 soft-shadow">
              <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div><div class="font-extrabold text-sm text-slate-900">选择执行账号</div><p class="text-[11px] text-slate-400 mt-1">{{ selectedSopClient.name }} 有 {{ selectedSopAccounts.length }} 个可执行 FB / TikTok 账号；已按平台分组，直接点击账号进入对应 SOP Checklist。</p></div>
                <button type="button" @click="openClientDetail(selectedSopClient.id,'sop')" class="h-9 px-4 rounded-xl border border-slate-200 bg-white text-xs font-bold text-slate-600 hover:bg-slate-50 shrink-0"><i class="fa-solid fa-box-archive mr-1.5"></i>查看客户资产</button>
              </div>

              <div class="space-y-5 mt-4" data-sop-platform-groups>
                <section v-for="platformGroup in [{key:'FB',name:'Facebook',icon:'fa-brands fa-facebook'},{key:'TK',name:'TikTok',icon:'fa-brands fa-tiktok'}]" :key="platformGroup.key" :data-sop-platform-group="platformGroup.key" class="rounded-2xl border p-3.5" :class="platformGroup.key==='FB'?'border-blue-100 bg-blue-50/20':'border-slate-200 bg-slate-50/60'">
                  <div class="flex items-center justify-between gap-3 px-1">
                    <div class="flex items-center gap-2.5">
                      <div class="w-8 h-8 rounded-lg flex items-center justify-center" :class="platformGroup.key==='FB'?'bg-blue-600 text-white':'bg-slate-950 text-white'"><i :class="platformGroup.icon"></i></div>
                      <div><div class="font-extrabold text-xs text-slate-900">{{ platformGroup.name }} 账号</div><div class="text-[10px] text-slate-400 mt-0.5">选择 {{ platformGroup.name }} 账号进入对应 SOP</div></div>
                    </div>
                    <span class="inline-flex items-center px-2.5 py-1 rounded-full bg-white border text-[10px] font-extrabold" :class="platformGroup.key==='FB'?'border-blue-100 text-blue-700':'border-slate-200 text-slate-700'">{{ selectedSopAccounts.filter(item=>item.platform===platformGroup.key).length }} 个账号</span>
                  </div>

                  <div v-if="selectedSopAccounts.some(item=>item.platform===platformGroup.key)" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mt-3">
                    <button v-for="item in selectedSopAccounts.filter(item=>item.platform===platformGroup.key)" :key="item.key" type="button" @click="selectedSopAccountKey=item.key; onSopAccountChange()" class="group text-left rounded-2xl border border-slate-200 bg-white p-3.5 hover:border-indigo-300 hover:shadow-sm transition">
                      <div class="flex items-start gap-3">
                        <div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" :class="item.platform==='FB'?'bg-blue-50 text-blue-600':'bg-slate-950 text-white'"><i :class="item.platform==='FB'?'fa-brands fa-facebook':'fa-brands fa-tiktok'"></i></div>
                        <div class="min-w-0 flex-1"><div class="flex items-center justify-between gap-2"><div class="font-extrabold text-sm text-slate-900 truncate">{{ item.account.accountName || item.account.adAccountId || '未命名账号' }}</div><i class="fa-solid fa-chevron-right text-[10px] text-slate-300 group-hover:text-indigo-500 shrink-0"></i></div><div class="text-[10px] font-bold mt-1" :class="item.platform==='FB'?'text-blue-600':'text-slate-600'">{{ item.platformName }}</div></div>
                      </div>
                      <div class="mt-3 grid grid-cols-2 gap-2 text-[10px]">
                        <div class="rounded-xl bg-slate-50 border border-slate-100 px-3 py-2"><div class="text-slate-400">广告账号 ID</div><div class="font-mono font-bold text-slate-700 mt-0.5 break-all">{{ item.account.adAccountId || '未录入' }}</div></div>
                        <div class="rounded-xl bg-slate-50 border border-slate-100 px-3 py-2"><div class="text-slate-400">{{ item.platform==='FB' ? 'BM ID' : 'BC ID' }}</div><div class="font-mono font-bold text-slate-700 mt-0.5 break-all">{{ item.platform==='FB' ? (item.account.bmId || '未录入') : (item.account.bcId || '未录入') }}</div></div>
                      </div>
                      <div class="mt-3 pt-3 border-t border-slate-200 flex items-center justify-between"><span class="text-[10px] text-slate-400">点击进入账号 SOP</span><span class="inline-flex items-center gap-1 text-[10px] font-extrabold text-indigo-600">进入 Checklist <i class="fa-solid fa-arrow-right text-[9px]"></i></span></div>
                    </button>
                  </div>
                  <div v-else class="mt-3 rounded-xl border border-dashed border-slate-200 bg-white/70 px-4 py-5 text-center text-[11px] text-slate-400">暂无 {{ platformGroup.name }} 可执行账号</div>
                </section>
              </div>
            </div>
          </div>
'''

html=html[:start]+new_block+html[end:]

index_path.write_text(html,encoding='utf-8')
print(
    'SOP_ACCOUNT_LAYOUT_FINALIZE_OK: grouped=FB+TK; desktop=4-cols-per-group; tablet=2-cols; mobile=1-col; metadata=2-cols; '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}'
)
