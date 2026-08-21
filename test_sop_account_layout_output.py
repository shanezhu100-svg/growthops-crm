from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

# SOP account chooser must be grouped by platform, not one mixed account grid.
require('data-sop-platform-groups' in html,
        'SOP account chooser platform-group container missing')
require(':data-sop-platform-group="platformGroup.key"' in html,
        'SOP platform group marker missing')
require("[{key:'FB',name:'Facebook',icon:'fa-brands fa-facebook'},{key:'TK',name:'TikTok',icon:'fa-brands fa-tiktok'}]" in html,
        'SOP chooser must define Facebook and TikTok groups')
require('{{ platformGroup.name }} 账号' in html,
        'SOP platform group heading missing')
require("selectedSopAccounts.filter(item=>item.platform===platformGroup.key).length" in html,
        'SOP platform account count missing')
require("v-for=\"item in selectedSopAccounts.filter(item=>item.platform===platformGroup.key)\"" in html,
        'SOP account cards must be filtered by platform group')
require('暂无 {{ platformGroup.name }} 可执行账号' in html,
        'SOP empty-platform hint missing')

# Responsive layout remains horizontal within each platform group.
require('grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mt-3' in html,
        'SOP platform group must render 4 columns on wide screens')
require('mt-3 grid grid-cols-2 gap-2 text-[10px]' in html,
        'SOP account metadata must remain two-column')
require('p-3.5 hover:border-indigo-300' in html,
        'SOP account cards must remain compact')

# The old mixed account grid and unfiltered v-for must be gone from final output.
require('grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 mt-5' not in html,
        'legacy three-column mixed SOP account grid must not survive')
require('v-for="item in selectedSopAccounts"' not in html,
        'legacy mixed SOP account iteration must not survive')

# Account behavior must remain unchanged.
require('@click="selectedSopAccountKey=item.key; onSopAccountChange()"' in html,
        'SOP account card click behavior must remain intact')
require('进入 Checklist' in html,
        'SOP account card action label must remain intact')
require("openClientDetail(selectedSopClient.id,'sop')" in html,
        'SOP client asset return-source behavior must remain intact')

print(
    'SOP_ACCOUNT_LAYOUT_OUTPUT_TESTS_OK: grouped=FB+TK; desktop=4-cols-per-group; tablet=2-cols; mobile=1-col; metadata=2-cols; '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}'
)
