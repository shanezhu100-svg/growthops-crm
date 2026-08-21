from pathlib import Path
import hashlib

root = Path(__file__).resolve().parent
dist = root / 'dist'
html = (dist / 'index.html').read_text(encoding='utf-8')
adapter = (dist / 'cloud-adapter.js').read_text(encoding='utf-8')

def require(condition, message):
    if not condition:
        raise SystemExit(message)

dynamic_status = """<span class="inline-flex px-2.5 py-1 rounded-full text-xs font-bold" :class="selectedClient.archived?'bg-slate-200 text-slate-600':selectedClient.status==='ACTIVE'?'bg-emerald-50 text-emerald-700':'bg-slate-100 text-slate-600'">{{ selectedClient.archived?'已归档':(selectedClient.status==='ACTIVE'?'合作中':'暂停') }}</span>"""
old_status = """<span class="inline-flex px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700">合作中</span>"""
require(html.count(dynamic_status) == 1, 'P2 client-detail inline status binding missing or duplicated')
require(old_status not in html, 'P2 old hard-coded client-detail status still present')
require('statusStyle(selectedClient.status)' not in html, 'P2 client-detail still calls missing statusStyle()')
require('statusText(selectedClient.status)' not in html, 'P2 client-detail still calls missing statusText()')

# Production must not expose or retain the destructive demo-reset feature.
require('resetDemoData' not in html, 'P2 resetDemoData implementation or binding still present')
require('重置演示' not in html, 'P2 reset-demo button label still present')
require('恢复初始演示数据' not in html, 'P2 reset-demo confirmation/copy still present')

# Client archive mode must be mutually exclusive. The default list contains
# current clients only; archive mode contains archived clients only. Search,
# platform filtering and row counts operate on that already-scoped list.
archive_filter = 'if(Boolean(c.archived)!==Boolean(this.showArchivedClients))return false;'
require(html.count(archive_filter) == 1, 'P2 exclusive active/archive client filter missing or duplicated')
require('if(c.archived&&!this.showArchivedClients)return false;' not in html, 'P2 legacy mixed archive-list filter remains')
require("{{ showArchivedClients?'归档客户':'客户管理' }}" in html, 'P2 archive-aware client heading missing')
require("{{ showArchivedClients?'返回客户':'查看归档' }}" in html, 'P2 archive toggle label missing')
require("家{{ showArchivedClients?'归档客户':'客户' }}" in html, 'P2 archive-aware client count missing')
require('仅显示已归档客户；历史广告、开户、财务和回款数据继续保留。' in html, 'P2 archive-view explanation missing')

def in_client_view(client, archive_mode):
    return bool(client.get('archived')) == bool(archive_mode)

sample_clients = [
    {'id': 1, 'archived': False},
    {'id': 2, 'archived': True},
    {'id': 3},
]
require([c['id'] for c in sample_clients if in_client_view(c, False)] == [1, 3], 'P2 current-client view semantics failed')
require([c['id'] for c in sample_clients if in_client_view(c, True)] == [2], 'P2 archived-client view semantics failed')

require(html.count('浏览器本地缓存占用 {{ storageUsageText }}') == 1, 'P2 browser-cache usage heading missing')
require('本地存储容量 {{ storageUsageText }}' not in html, 'P2 misleading local storage heading remains')
require('尽快迁移到数据库' not in html, 'P2 misleading migration warning remains')
require('这里只统计此浏览器的 localStorage，不代表 Supabase 数据库或存储配额。' in html, 'P2 localStorage/Supabase scope note missing')

script_order = (
    '<script src="/cloud-p1-overrides.js"></script>'
    '<script src="/cloud-p1-archive.js"></script>'
    '<script src="/cloud-adapter.js"></script>'
    '<script src="/cloud-p0-overrides.js"></script>'
)
require(html.count(script_order) == 1, 'P2 changed P1/archive/adapter/P0 script order')

# P2 billing rule A: only the first contract month may be clamped to startDate.
safe_auto_due = "dueDate:(()=>{const scheduled=this.monthDueDate(month,client.renewalAlertDay),start=String(client.startDate||'').slice(0,10);return start&&month===start.slice(0,7)&&scheduled<start?start:scheduled})(),"
require(html.count(safe_auto_due) == 1, 'P2 option-A automatic receivable due-date clamp missing or duplicated')
require(
    'dueDate:this.monthDueDate(month,client.renewalAlertDay),' not in html,
    'P2 legacy automatic receivable due-date rule remains'
)
require(
    "return this.createReceivableForClientMonth(client,firstMonth,{allowFuture:true})" in html,
    'P2 unexpectedly changed first-receivable generation rule'
)

def option_a_due(scheduled, start_date, month):
    start = str(start_date or '')[:10]
    return start if start and month == start[:7] and scheduled < start else scheduled

require(option_a_due('2026-08-25', '2026-08-28', '2026-08') == '2026-08-28', 'P2 option-A clamp example failed')
require(option_a_due('2026-08-25', '2026-08-20', '2026-08') == '2026-08-25', 'P2 option-A non-clamp example failed')
require(option_a_due('2026-09-25', '2026-08-28', '2026-09') == '2026-09-25', 'P2 option-A later-month due day changed')

require("if(d?.error==='INVALID_CREDENTIALS'){vm.notify('账号或密码错误');return}" in adapter, 'P2 login JSON-error compatibility guard missing')
require("finally{vm.loginForm.password=''}" in adapter, 'P2 login password cleanup missing')
require(adapter.count("rpc('crm_login'") == 1, 'P2 unexpected crm_login call count')

print(
    'P2_OUTPUT_TESTS_OK: '
    f'index={hashlib.sha256((dist / "index.html").read_bytes()).hexdigest()}; '
    f'adapter={hashlib.sha256((dist / "cloud-adapter.js").read_bytes()).hexdigest()}'
)
