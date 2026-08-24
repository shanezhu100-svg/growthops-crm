from pathlib import Path

root = Path(__file__).resolve().parent
html = (root / 'dist' / 'index.html').read_text(encoding='utf-8')
adapter = (root / 'dist' / 'cloud-adapter.js').read_text(encoding='utf-8')


def require(condition, message):
    if not condition:
        raise SystemExit(message)


placeholder_old = ':placeholder="userForm.id?\'留空表示保留原密码\':\'至少 10 位\'"'
placeholder_new = ':placeholder="userForm.id?\'留空表示保留原密码（最多72 UTF-8字节）\':\'至少 10 位，最多 72 UTF-8 字节\'"'
require(placeholder_old not in html, 'stale admin password dynamic placeholder survived')
require(html.count(placeholder_new) == 1, 'final admin password dynamic placeholder must appear exactly once')

new_min = "if(!f.id&&f.password.length<10){vm.notify('新用户登录密码至少需要 10 位');return;}"
edit_min = "if(f.id&&f.password&&f.password.length<10){vm.notify('新密码至少需要 10 位；不修改密码请留空');return;}"
max_guard = "if(f.password&&new TextEncoder().encode(f.password).byteLength>72){vm.notify('密码最多 72 个 UTF-8 字节');return;}"
rpc_marker = "rpc('crm_upsert_user'"
for marker, label in ((new_min,'new-user minimum'),(edit_min,'edit minimum'),(max_guard,'72-byte maximum'),(rpc_marker,'upsert RPC')):
    require(adapter.count(marker) == 1, f'{label} must appear exactly once in authoritative cloud adapter')

new_pos = adapter.index(new_min)
edit_pos = adapter.index(edit_min)
max_pos = adapter.index(max_guard)
rpc_pos = adapter.index(rpc_marker)
require(new_pos < edit_pos < max_pos < rpc_pos, 'admin password validation order must be new-min -> edit-min -> byte-max -> RPC')
require('TextEncoder().encode(f.password).byteLength>72' in adapter, 'UTF-8 byte counting is not active')

# The canonical HTML method is not the authority after cloud-adapter loads. Do
# not accept a future regression that puts the sole byte check back in index.html.
require('new TextEncoder().encode(f.password).byteLength>72' not in html, 'authoritative admin password byte guard must not be misplaced in index.html')

print('ADMIN_PASSWORD_BYTE_CAP_OUTPUT_OK: placeholder=dynamic-edit-aware; authoritative-save=cloud-adapter; min-new+min-edit=preserved; max=72-utf8-bytes; validation-before-rpc')
