from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

require('grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mt-4' in html,
        'SOP account chooser must render four columns on wide screens')
require('mt-3 grid grid-cols-2 gap-2 text-[10px]' in html,
        'SOP account metadata must use a compact two-column layout')
require('p-3.5 hover:bg-white hover:border-indigo-300' in html,
        'SOP account cards must use compact padding')
require('grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 mt-5' not in html,
        'legacy three-column SOP account grid must not survive')
require('mt-4 grid grid-cols-1 gap-2 text-[10px]' not in html,
        'legacy stacked SOP account metadata must not survive')
require('@click="selectedSopAccountKey=item.key; onSopAccountChange()"' in html,
        'SOP account card click behavior must remain intact')
require('进入 Checklist' in html,
        'SOP account card action label must remain intact')

print(
    'SOP_ACCOUNT_LAYOUT_OUTPUT_TESTS_OK: desktop=4-cols; tablet=2-cols; mobile=1-col; metadata=2-cols; '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}'
)
