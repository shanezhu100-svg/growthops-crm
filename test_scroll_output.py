from pathlib import Path
import hashlib

root = Path(__file__).resolve().parent
dist = root / 'dist'
index_path = dist / 'index.html'
html = index_path.read_text(encoding='utf-8')


def require(condition, message):
    if not condition:
        raise SystemExit(message)

script_id = 'id="growthops-client-scroll-state"'
require(html.count(script_id) == 1, 'client scroll state script missing or duplicated')
require("const STORAGE_KEY='growthops_client_scroll_state_v1';" in html, 'isolated scroll session state missing')
require("if('scrollRestoration' in history)history.scrollRestoration='manual';" in html, 'browser automatic scroll restoration is not disabled')
require("vm.$watch('currentPage'" in html and "{flush:'sync'}" in html, 'page transition watcher must capture the old page synchronously')
require("if(from==='clients'&&to==='client-detail')" in html, 'clients to client-detail transition guard missing')
require("restorePosition(0);" in html, 'client detail must not inherit the clients list scroll position')
require("if(from==='client-detail'&&to==='clients')" in html, 'client-detail to clients transition guard missing')
require("restorePosition(state.clients);" in html, 'clients list scroll position is not restored on detail back')
require("state.details[clientKey]=y" in html, 'detail-page scroll state is not isolated per client')
require("vm.$nextTick" in html and "setTimeout(apply,180)" in html, 'scroll restoration must run after Vue DOM rendering and retry once layout settles')
require("window.__GROWTHOPS_CLIENT_SCROLL_STATE__" in html, 'scroll state runtime marker missing')
require(
    '<script src="/cloud-security-hotfix.js"></script><script id="growthops-client-scroll-state">' in html,
    'client scroll state script must load after the security hotfix without disturbing earlier override order'
)

print(
    'SCROLL_OUTPUT_TESTS_OK: '
    f'index={hashlib.sha256(index_path.read_bytes()).hexdigest()}'
)
