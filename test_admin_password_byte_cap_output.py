from pathlib import Path

root = Path(__file__).resolve().parent
html = (root / 'dist' / 'index.html').read_text(encoding='utf-8')

placeholder = 'placeholder="新密码（至少10位，最多72字节；留空=不修改）"'
minimum = "if(password&&password.length<10) return alert('密码至少10位');"
byte_cap = "if(password&&new TextEncoder().encode(password).byteLength>72) return alert('密码最多72字节（中文等字符可能占多个字节）');"
create_required = "if(!selectedUserId&&!password) return alert('新用户必须设置密码');"
empty_update = 'p_password:password||null'

for marker, label in (
    (placeholder, '72-byte password hint'),
    (minimum, '10-character minimum'),
    (byte_cap, 'UTF-8 byte-cap validation'),
    (create_required, 'new-user password requirement'),
    (empty_update, 'empty-update no-change transport'),
):
    if html.count(marker) != 1:
        raise SystemExit(f'Unexpected {label} marker count: {html.count(marker)}')

if 'placeholder="新密码（至少10位；留空=不修改）"' in html:
    raise SystemExit('Legacy admin password hint survived final output')
if 'password.length>72' in html:
    raise SystemExit('Character-count max must not replace UTF-8 byte-count max')

# The byte cap must execute after the existing minimum check and before the RPC
# submission. This keeps UI semantics aligned with the DB/BFF boundary.
min_pos = html.index(minimum)
cap_pos = html.index(byte_cap)
rpc_pos = html.index(empty_update)
if not min_pos < cap_pos < rpc_pos:
    raise SystemExit('Admin password validation ordering drifted')

print('ADMIN_PASSWORD_BYTE_CAP_OUTPUT_OK: hint=72B; min=10-characters; max=72-utf8-bytes; ordering=min-before-cap-before-rpc; empty-update=preserved')
