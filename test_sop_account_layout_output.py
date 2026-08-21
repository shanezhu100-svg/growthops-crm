from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

chooser_start_marker='          <div v-else-if="selectedSopClient && selectedSopAccounts.length" class="space-y-4">'
chooser_end_marker='          <div v-else-if="selectedSopClient" class="bg-white border border-slate-200 rounded-2xl py-16 text-center text-xs text-slate-400">'
start=html.find(chooser_start_marker)
end=html.find(chooser_end_marker,start)
require(start>=0 and end>start,'unable to bound final SOP account chooser')
chooser=html[start:end]

# SOP account card area must be grouped by platform, not one mixed account grid.
require('data-sop-platform-groups' in chooser,
        'SOP account chooser platform-group container missing')
require(':data-sop-platform-group="platformGroup.key"' in chooser,
        'SOP platform group marker missing')
require("[{key:'FB',name:'Facebook',icon:'fa-brands fa-facebook'},{key:'TK',name:'TikTok',icon:'fa-brands fa-tiktok'}]" in chooser,
        'SOP chooser must define Facebook and TikTok groups')
require('{{ platformGroup.name }} 账号' in chooser,
        'SOP platform group heading missing')
require("selectedSopAccounts.filter(item=>item.platform===platformGroup.key).length" in chooser,
        'SOP platform account count missing')
require('v-for="item in selectedSopAccounts.filter(item=>item.platform===platformGroup.key)"' in chooser,
        'SOP account cards must be filtered by platform group')
require('暂无 {{ platformGroup.name }} 可执行账号' in chooser,
        'SOP empty-platform hint missing')

# Responsive layout remains horizontal within each platform group.
require('grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mt-3' in chooser,
        'SOP platform group must render 4 columns on wide screens')
require('mt-3 grid grid-cols-2 gap-2 text-[10px]' in chooser,
        'SOP account metadata must remain two-column')
require('p-3.5 hover:border-indigo-300' in chooser,
        'SOP account cards must remain compact')

# Only the card area must lose the old mixed iteration. The top-right account
# select intentionally keeps its own unfiltered selectedSopAccounts v-for.
require('grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 mt-5' not in chooser,
        'legacy three-column mixed SOP account grid must not survive in chooser')
require('v-for="item in selectedSopAccounts"' not in chooser,
        'legacy mixed SOP account card iteration must not survive in chooser')

# Account behavior must remain unchanged.
require('@click="selectedSopAccountKey=item.key; onSopAccountChange()"' in chooser,
        'SOP account card click behavior must remain intact')
require('进入 Checklist' in chooser,
        'SOP account card action label must remain intact')
require("openClientDetail(selectedSopClient.id,'sop')" in chooser,
        'SOP client asset return-source behavior must remain intact')
require('v-for="item in selectedSopAccounts"' in html,
        'top-right SOP account select should remain available as a fast switch')

print(
    'SOP_ACCOUNT_LAYOUT_OUTPUT_TESTS_OK: grouped=FB+TK; desktop=4-cols-per-group; tablet=2-cols; mobile=1-col; metadata=2-cols; '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}'
)
