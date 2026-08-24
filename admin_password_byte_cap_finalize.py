from pathlib import Path

root = Path(__file__).resolve().parent
index_path = root / 'dist' / 'index.html'
html = index_path.read_text(encoding='utf-8')

# Keep the admin user form aligned with the database/BFF bcrypt write boundary.
# PostgreSQL pgcrypto bcrypt ignores password bytes after byte 72, while the
# existing minimum-password rule is character based. Preserve that distinction:
# >=10 characters for a non-empty password, <=72 UTF-8 bytes for bcrypt safety.
placeholder_old = 'placeholder="新密码（至少10位；留空=不修改）"'
placeholder_new = 'placeholder="新密码（至少10位，最多72字节；留空=不修改）"'
if html.count(placeholder_old) != 1:
    raise SystemExit(f'Unexpected admin password placeholder count: {html.count(placeholder_old)}')
if placeholder_new in html:
    raise SystemExit('Admin password byte-cap placeholder already present before finalize')
html = html.replace(placeholder_old, placeholder_new, 1)

minimum_old = "if(password&&password.length<10) return alert('密码至少10位');"
byte_cap = "if(password&&new TextEncoder().encode(password).byteLength>72) return alert('密码最多72字节（中文等字符可能占多个字节）');"
if html.count(minimum_old) != 1:
    raise SystemExit(f'Unexpected admin password minimum-validation count: {html.count(minimum_old)}')
if byte_cap in html:
    raise SystemExit('Admin password byte-cap validation already present before finalize')
html = html.replace(minimum_old, minimum_old + byte_cap, 1)

# Preserve create/update semantics exactly: new users require a password, while
# an empty update password remains null and therefore means "do not change it".
for required in (
    "if(!selectedUserId&&!password) return alert('新用户必须设置密码');",
    minimum_old,
    byte_cap,
    'p_password:password||null',
):
    if required not in html:
        raise SystemExit(f'Admin password form invariant missing after finalize: {required}')

index_path.write_text(html, encoding='utf-8')
print('ADMIN_PASSWORD_BYTE_CAP_FINALIZE_OK: min=10-characters; max=72-utf8-bytes; empty-update=no-change; ui-hint=aligned')
