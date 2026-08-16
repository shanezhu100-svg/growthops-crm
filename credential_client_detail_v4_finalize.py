from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
security_path=root/'dist'/'cloud-security-hotfix.js'
security=security_path.read_text(encoding='utf-8')

context_marker="  const currentExternalAssetAccount=platform=>{\n"
if security.count(context_marker)!=1:
    raise SystemExit(f'Unexpected credential context insertion marker count: {security.count(context_marker)}')
security=security.replace(
    context_marker,
    "  const isCredentialSummaryContext=()=>isAccountAssetPage()||vm.currentPage==='client-detail';\n"+context_marker,
    1,
)

old_apply="if(!isAccountAssetPage()||!accountSafeSummaryData)return;"
if security.count(old_apply)!=1:
    raise SystemExit(f'Unexpected safe summary apply context count: {security.count(old_apply)}')
security=security.replace(old_apply,"if(!isCredentialSummaryContext()||!accountSafeSummaryData)return;",1)

old_ensure="""    if(!isAccountAssetPage()){
      if(accountSafeSummaryData||accountSafeSummaryClientId)clearAccountSafeSummary();
      return;
    }
"""
new_ensure="""    if(!isCredentialSummaryContext()){
      if(accountSafeSummaryData||accountSafeSummaryClientId)clearAccountSafeSummary();
      return;
    }
"""
if security.count(old_ensure)!=1:
    raise SystemExit(f'Unexpected safe summary ensure context count: {security.count(old_ensure)}')
security=security.replace(old_ensure,new_ensure,1)

old_controls="if(vm.currentUser?.role!=='ADMIN'||!isAccountAssetPage()||!accountSafeSummaryData)return;"
if security.count(old_controls)!=1:
    raise SystemExit(f'Unexpected protected controls context count: {security.count(old_controls)}')
security=security.replace(
    old_controls,
    "if(vm.currentUser?.role!=='ADMIN'||!isCredentialSummaryContext()||!accountSafeSummaryData)return;",
    1,
)

# Retire the browser-side full-client reveal implementation. The database RPC is
# intentionally kept temporarily for older deployed Previews until this build is
# user-verified, but the new frontend must have no code path that calls it.
legacy_start=security.find('  async function revealSelectedClientLegacy(){')
wrapper_start=security.find('  async function revealSelectedClient(){',legacy_start+1)
if legacy_start<0 or wrapper_start<0 or wrapper_start<=legacy_start:
    raise SystemExit('Unable to locate legacy full-client reveal block')
security=security[:legacy_start]+security[wrapper_start:]

old_wrapper="""  async function revealSelectedClient(){
    if(isAccountAssetPage()){
      if(vm.currentUser?.role!=='ADMIN'){
        vm.notify('只有管理员可以查看密码 / 2FA');
        return;
      }
      ensureAccountSafeSummary();
      installProtectedFieldControls();
      vm.notify('登录账号 / 邮箱已显示；密码 / 2FA 请点击对应眼睛短暂查看');
      return;
    }
    return revealSelectedClientLegacy();
  }
"""
new_wrapper="""  async function revealSelectedClient(){
    if(!isCredentialSummaryContext())return;
    if(vm.currentUser?.role!=='ADMIN'){
      vm.notify('登录账号 / 邮箱可查看；密码 / 2FA 仅管理员可解锁');
      ensureAccountSafeSummary();
      return;
    }
    ensureAccountSafeSummary();
    installProtectedFieldControls();
    vm.notify('登录账号 / 邮箱已显示；密码 / 2FA 请点击对应眼睛并验证管理员身份');
  }
"""
if security.count(old_wrapper)!=1:
    raise SystemExit(f'Unexpected protected reveal wrapper count: {security.count(old_wrapper)}')
security=security.replace(old_wrapper,new_wrapper,1)

# Client-detail uses the same summary refresh loop as the account asset page.
# The existing else branch already invokes ensureAccountSafeSummary(); after the
# context widening above it now remains active on client-detail.

security_path.write_text(security,encoding='utf-8')
print('CREDENTIAL_CLIENT_DETAIL_V4_FINALIZE_OK: security='+hashlib.sha256(security_path.read_bytes()).hexdigest())
