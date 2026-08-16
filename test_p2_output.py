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
