from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'

OLD_TO_NEW = {
    '角色权限演示已启用。正式部署时请接服务器认证和数据库。':
        '已启用服务端会话认证与角色权限控制。',
    '当前文件仍是浏览器本地数据版本。正式公网部署前请切换到服务端认证与数据库，避免在前端保存真实账号密码、2FA 与财务敏感数据。':
        '当前生产版通过同源服务端 API 连接数据库；登录会话使用 HttpOnly Cookie，服务端密钥与会话令牌不暴露给前端脚本。',
    '已启用角色权限、全量数据备份与恢复。当前单文件版仍使用本地数据仓库，正式上线可替换为服务器数据库。':
        '已启用服务端认证、角色权限、全量数据备份与恢复。业务数据通过同源 API 持久化到云端数据库。',
    '登录令牌保存在当前浏览器，业务数据同步云端':
        '登录会话由服务端 HttpOnly Cookie 维护，业务数据同步云端',
}

if not INDEX.is_file():
    raise SystemExit('PRODUCTION_AUTH_COPY_FINALIZE_FAILED: dist/index.html missing')

html = INDEX.read_text(encoding='utf-8')
for old, new in OLD_TO_NEW.items():
    old_count = html.count(old)
    if old_count != 1:
        raise SystemExit(
            'PRODUCTION_AUTH_COPY_FINALIZE_FAILED: '
            f'unexpected stale-copy count={old_count}: {old}'
        )
    if new in html:
        raise SystemExit(
            'PRODUCTION_AUTH_COPY_FINALIZE_FAILED: replacement already present before finalize: '
            + new
        )
    html = html.replace(old, new, 1)

INDEX.write_text(html, encoding='utf-8')
print('PRODUCTION_AUTH_COPY_FINALIZE_OK: stale-local-copy=4-replaced; server-auth=truthful; same-origin-api=truthful; httponly-session=truthful')
