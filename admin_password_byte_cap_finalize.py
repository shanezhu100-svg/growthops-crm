from pathlib import Path

root = Path(__file__).resolve().parent
index_path = root / 'dist' / 'index.html'
adapter_path = root / 'dist' / 'cloud-adapter.js'
html = index_path.read_text(encoding='utf-8')
adapter = adapter_path.read_text(encoding='utf-8')

# build_final.py already owns the edit/new-user password semantics. Patch the
# dynamic Vue placeholder it actually emits rather than a stale canonical label.
placeholder_old = ':placeholder="userForm.id?\'留空表示保留原密码\':\'至少 10 位\'"'
placeholder_new = ':placeholder="userForm.id?\'留空表示保留原密码（最多72 UTF-8字节）\':\'至少 10 位，最多 72 UTF-8 字节\'"'
if html.count(placeholder_old) != 1:
    raise SystemExit(f'Unexpected admin password dynamic placeholder count: {html.count(placeholder_old)}')
if placeholder_new in html:
    raise SystemExit('Admin password dynamic placeholder already patched before finalizer')
html = html.replace(placeholder_old, placeholder_new, 1)

# cloud-adapter.js overrides vm.saveAuthUser after the Vue app mounts, so this is
# the authoritative browser-side save path. Preserve both existing 10-character
# rules and insert the bcrypt byte ceiling after them, before the RPC.
minimum_block = """    if(!f.id&&f.password.length<10){vm.notify('新用户登录密码至少需要 10 位');return;}
    if(f.id&&f.password&&f.password.length<10){vm.notify('新密码至少需要 10 位；不修改密码请留空');return;}
"""
maximum_guard = "    if(f.password&&new TextEncoder().encode(f.password).byteLength>72){vm.notify('密码最多 72 个 UTF-8 字节');return;}\n"
if adapter.count(minimum_block) != 1:
    raise SystemExit(f'Unexpected authoritative admin password minimum block count: {adapter.count(minimum_block)}')
if maximum_guard in adapter:
    raise SystemExit('Admin password byte guard already exists before finalizer')
adapter = adapter.replace(minimum_block, minimum_block + maximum_guard, 1)

rpc_marker = "rpc('crm_upsert_user'"
if adapter.count(rpc_marker) != 1:
    raise SystemExit(f'Unexpected crm_upsert_user browser RPC count: {adapter.count(rpc_marker)}')
min_pos = adapter.index("if(!f.id&&f.password.length<10)")
max_pos = adapter.index("new TextEncoder().encode(f.password).byteLength>72")
rpc_pos = adapter.index(rpc_marker)
if not (min_pos < max_pos < rpc_pos):
    raise SystemExit('Admin password browser validation order drifted')

index_path.write_text(html, encoding='utf-8')
adapter_path.write_text(adapter, encoding='utf-8')
print('ADMIN_PASSWORD_BYTE_CAP_FINALIZE_OK: placeholder=dynamic-edit-aware; browser-save=cloud-adapter-authoritative; minimum=10chars-preserved; maximum=72-utf8-bytes-before-rpc')
