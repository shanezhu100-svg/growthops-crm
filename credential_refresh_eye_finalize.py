from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security_path=root/'dist'/'cloud-security-hotfix.js'
security=security_path.read_text(encoding='utf-8')

# 1) Loading state must work in both account-assets and client-detail.
loading_start=security.find("  const applyCredentialLoadingToCards=()=>{")
loading_end=security.find("  const applyCredentialStatusUnavailable=()=>{", loading_start)
if loading_start<0 or loading_end<0:
    raise SystemExit('Unable to locate credential loading helper')
loading_block=security[loading_start:loading_end]
old_loading="    if(!isAccountAssetPage())return;\n"
if loading_block.count(old_loading)!=1:
    raise SystemExit(f'Unexpected loading context count: {loading_block.count(old_loading)}')
loading_block=loading_block.replace(old_loading,"    if(!isCredentialSummaryContext())return;\n",1)
security=security[:loading_start]+loading_block+security[loading_end:]

# 2) Safe-summary failure state also applies to client-detail.
unavailable_start=security.find("  const markAccountSafeSummaryUnavailable=()=>{")
unavailable_end=security.find("  const clearAccountSafeSummary=()=>{", unavailable_start)
if unavailable_start<0 or unavailable_end<0:
    raise SystemExit('Unable to locate safe-summary unavailable helper')
unavailable_block=security[unavailable_start:unavailable_end]
old_unavailable="    if(!isAccountAssetPage())return;\n"
if unavailable_block.count(old_unavailable)!=1:
    raise SystemExit(f'Unexpected unavailable context count: {unavailable_block.count(old_unavailable)}')
unavailable_block=unavailable_block.replace(old_unavailable,"    if(!isCredentialSummaryContext())return;\n",1)
security=security[:unavailable_start]+unavailable_block+security[unavailable_end:]

# 3) When switching client/context, clear any old inline secret controls and status
# markers before showing the new loading state. This prevents stale masked/eye UI.
ensure_start=security.find("  const ensureAccountSafeSummary=()=>{")
ensure_end=security.find("  const applyCredentialLoadingToCards=()=>{", ensure_start)
if ensure_start<0 or ensure_end<0:
    raise SystemExit('Unable to locate safe-summary ensure helper')
ensure_block=security[ensure_start:ensure_end]
old_switch="""    if(accountSafeSummaryClientId!==clientId){
      accountSafeSummaryClientId=clientId;
      accountSafeSummaryData=null;
      accountSafeSummaryFetchedAt=0;
    }
"""
new_switch="""    if(accountSafeSummaryClientId!==clientId){
      clearReveal();
      for(const row of locateCredentialRows()){
        for(const cell of [row.accountCell,row.passwordCell]){
          if(!cell)continue;
          cell.removeAttribute(STATUS_ATTR);
          cell.removeAttribute(LOGIN_IDENTIFIER_ATTR);
          cell.removeAttribute(FIELD_REVEAL_ATTR);
        }
      }
      accountSafeSummaryClientId=clientId;
      accountSafeSummaryData=null;
      accountSafeSummaryFetchedAt=0;
    }
"""
if ensure_block.count(old_switch)!=1:
    raise SystemExit(f'Unexpected safe-summary client switch count: {ensure_block.count(old_switch)}')
ensure_block=ensure_block.replace(old_switch,new_switch,1)
promise_marker="    accountSafeSummaryPromise=cloud.rpc('crm_client_account_safe_summary'"
if ensure_block.count(promise_marker)!=1:
    raise SystemExit(f'Unexpected safe-summary RPC marker count: {ensure_block.count(promise_marker)}')
ensure_block=ensure_block.replace(promise_marker,"    if(!accountSafeSummaryData)applyCredentialLoadingToCards();\n"+promise_marker,1)
security=security[:ensure_start]+ensure_block+security[ensure_end:]

# 4) Install the per-field eye control immediately in the same render pass that
# applies the safe summary. Do not wait for the next periodic UI scan.
apply_start=security.find("  const applyAccountSafeSummaryToCards=()=>{")
apply_end=security.find("  const markAccountSafeSummaryUnavailable=()=>{", apply_start)
if apply_start<0 or apply_end<0:
    raise SystemExit('Unable to locate safe-summary apply helper')
apply_block=security[apply_start:apply_end]
if 'installProtectedFieldControls();' not in apply_block:
    tail=apply_block.rfind("  };\n")
    if tail<0:
        raise SystemExit('Unable to locate safe-summary apply tail')
    apply_block=apply_block[:tail]+"    installProtectedFieldControls();\n"+apply_block[tail:]
security=security[:apply_start]+apply_block+security[apply_end:]

# Keep the removed top-level feature wording retired while describing the per-field eye.
old_hint='密码 / 2FA 已安全保存在 Vault'
new_hint='密码 / 2FA 已安全保存在 Vault；点击眼睛可由管理员短暂查看'
if new_hint not in security:
    if security.count(old_hint)<1:
        raise SystemExit('Credential masked-state hint missing')
    security=security.replace(old_hint,new_hint,1)

security_path.write_text(security,encoding='utf-8')
print('CREDENTIAL_REFRESH_EYE_FINALIZE_OK: security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
