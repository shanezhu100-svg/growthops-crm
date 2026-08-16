from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
index_path=root/'dist'/'index.html'
security_path=root/'dist'/'cloud-security-hotfix.js'
html=index_path.read_text(encoding='utf-8')
security=security_path.read_text(encoding='utf-8')

def require(condition,message):
    if not condition:
        raise SystemExit(message)

for marker in (
    '<option :value="0">全部客户</option>',
    '<div v-if="selectedAssetsClientId===0" class="space-y-5">',
    '<div v-else-if="selectedAssetsClient" class="space-y-5">',
    '全部客户账号资产',
    '@click="selectedAssetsClientId=c.id"',
    "clients.reduce((n,c)=>n+(c.fbAccounts||[]).length,0)",
    "clients.reduce((n,c)=>n+(c.tkAccounts||[]).length,0)",
    "clients.reduce((n,c)=>n+(c.googleAccounts||[]).length,0)",
    "clients.reduce((n,c)=>n+(c.instagramAccounts||[]).length,0)",
    'selectedAssetsClient && selectedAssetsClientId!==0',
):
    require(marker in html,f'all-client asset UI marker missing: {marker}')

for marker in (
    'const explicitAssetsClientId=vm.selectedAssetsClientId;',
    "if(explicitAssetsClientText==='0'||explicitAssetsClientText.toUpperCase()==='ALL')return '';",
    "if(explicitAssetsClientId!==undefined&&explicitAssetsClientId!==null&&explicitAssetsClientText!=='')return explicitAssetsClientText;",
):
    require(marker in security,f'all-client credential isolation marker missing: {marker}')

# Aggregate selection must appear before the customer loop in the selector.
select_start=html.find('<select v-model.number="selectedAssetsClientId"')
select_end=html.find('</select>',select_start)
select_body=html[select_start:select_end]
require(select_body.find('全部客户') < select_body.find('v-for="c in clients"'),'aggregate option must be first in asset client selector')

# No single-client edit/detail branch should render in the aggregate branch.
all_block=html.split('<div v-if="selectedAssetsClientId===0" class="space-y-5">',1)[1].split('<div v-else-if="selectedAssetsClient" class="space-y-5">',1)[0]
require('openClientForm(selectedAssetsClient)' not in all_block,'aggregate asset view must not expose single-client editor')
require('crm_reveal_client_secrets' not in all_block,'aggregate asset view must not embed reveal behavior')

print('ASSETS_ALL_CLIENTS_OUTPUT_TESTS_OK: index='+hashlib.sha256(index_path.read_bytes()).hexdigest()+'; security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
