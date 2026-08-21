from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
html=index_path.read_text(encoding='utf-8')

# Layout-only refinement for the visible SOP account chooser. Navigation and
# account-selection behavior stay owned by module_home_navigation_finalize.py.
old_grid='''              <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 mt-5">'''
new_grid='''              <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mt-4">'''
if html.count(old_grid)!=1:
    raise SystemExit(f'Unexpected SOP account grid count: {html.count(old_grid)}')
html=html.replace(old_grid,new_grid,1)

old_meta='''                  <div class="mt-4 grid grid-cols-1 gap-2 text-[10px]">'''
new_meta='''                  <div class="mt-3 grid grid-cols-2 gap-2 text-[10px]">'''
if html.count(old_meta)!=1:
    raise SystemExit(f'Unexpected SOP account metadata grid count: {html.count(old_meta)}')
html=html.replace(old_meta,new_meta,1)

# Keep account cards compact without changing their click target or content.
old_card='''class="group text-left rounded-2xl border border-slate-200 bg-slate-50/70 p-4 hover:bg-white hover:border-indigo-300 hover:shadow-sm transition"'''
new_card='''class="group text-left rounded-2xl border border-slate-200 bg-slate-50/70 p-3.5 hover:bg-white hover:border-indigo-300 hover:shadow-sm transition"'''
if html.count(old_card)!=1:
    raise SystemExit(f'Unexpected SOP account card class count: {html.count(old_card)}')
html=html.replace(old_card,new_card,1)

index_path.write_text(html,encoding='utf-8')
print(
    'SOP_ACCOUNT_LAYOUT_FINALIZE_OK: desktop=4-cols; tablet=2-cols; mobile=1-col; metadata=2-cols; '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}'
)
