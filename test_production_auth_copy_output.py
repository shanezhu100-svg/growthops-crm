from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / 'dist' / 'index.html'

STALE = (
    '角色权限演示已启用。正式部署时请接服务器认证和数据库。',
    '当前文件仍是浏览器本地数据版本。正式公网部署前请切换到服务端认证与数据库，避免在前端保存真实账号密码、2FA 与财务敏感数据。',
    '已启用角色权限、全量数据备份与恢复。当前单文件版仍使用本地数据仓库，正式上线可替换为服务器数据库。',
)
CURRENT = (
    '已启用服务端会话认证与角色权限控制。',
    '当前生产版通过同源服务端 API 连接数据库；登录会话使用 HttpOnly Cookie，服务端密钥与会话令牌不暴露给前端脚本。',
    '已启用服务端认证、角色权限、全量数据备份与恢复。业务数据通过同源 API 持久化到云端数据库。',
)

if not INDEX.is_file():
    raise SystemExit('PRODUCTION_AUTH_COPY_OUTPUT_TEST_FAILED: dist/index.html missing')

html = INDEX.read_text(encoding='utf-8')
for marker in STALE:
    if marker in html:
        raise SystemExit('PRODUCTION_AUTH_COPY_OUTPUT_TEST_FAILED: stale deployment copy still shipped: ' + marker)
for marker in CURRENT:
    count = html.count(marker)
    if count != 1:
        raise SystemExit(
            'PRODUCTION_AUTH_COPY_OUTPUT_TEST_FAILED: '
            f'current copy count={count}: {marker}'
        )

# Keep the public copy aligned with the actual transport/session boundary. These
# source-level markers are intentionally narrow and complement the behavioral
# HttpOnly/session and browser-config scrub regression suites.
required_build_files = (
    ROOT / 'api' / 'crm.js',
    ROOT / 'functions' / 'api' / 'crm.js',
)
for path in required_build_files:
    source = path.read_text(encoding='utf-8')
    if 'HttpOnly' not in source:
        raise SystemExit('PRODUCTION_AUTH_COPY_OUTPUT_TEST_FAILED: HttpOnly cookie boundary missing from ' + str(path.relative_to(ROOT)))

print('PRODUCTION_AUTH_COPY_OUTPUT_TESTS_OK: stale-local-copy=absent; server-auth-copy=present; same-origin-api-copy=present; httponly-session-copy=present')
