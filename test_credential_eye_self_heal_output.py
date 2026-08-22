from pathlib import Path

root = Path(__file__).resolve().parent
security = (root / 'dist' / 'cloud-security-hotfix.js').read_text(encoding='utf-8')

required = (
    "const existingRevealControl=cell.querySelector('button[aria-label=\"显示密码和 2FA\"],button[aria-label=\"隐藏密码和 2FA\"]');",
    "if(cell.getAttribute(FIELD_REVEAL_ATTR)==='1'&&existingRevealControl)return true;",
    "if(cell.getAttribute(FIELD_REVEAL_ATTR)==='1')cell.removeAttribute(FIELD_REVEAL_ATTR);",
    "const installedRevealControl=row.passwordCell.querySelector('button[aria-label=\"显示密码和 2FA\"],button[aria-label=\"隐藏密码和 2FA\"]');",
    "row.passwordCell.getAttribute(FIELD_REVEAL_ATTR)==='1'&&installedRevealControl",
    "const targetAccountId=accountIdForProtectedField(row)||null;",
    "if(!cell.isConnected||!toggle.isConnected||!cell.contains(toggle))",
    "credentialUiV5Render();",
    "const liveRows=locateCredentialRows().filter(candidate=>candidate.platform===row.platform&&String(accountIdForProtectedField(candidate)||'')===targetId);",
    "const liveRow=liveRows.length===1?liveRows[0]:null;",
    "if(liveToggle){liveToggle.click();return;}",
    "管理员验证成功；凭证区域已刷新，请再次点击眼睛查看",
    "const accountId=targetAccountId;",
    "const credentialEphemeralReveals=new Map();",
    "return clientId&&platform&&accountId?JSON.stringify([clientId,platform,accountId]):'';",
    "credentialEphemeralReveals.set(revealKey,{value:visibleValue,expiresAt:revealExpiresAt});",
    "const activeReveal=revealKey?credentialEphemeralReveals.get(revealKey):null;",
    "fieldTimer=setTimeout(hide,Math.max(1,Math.min(10000,activeReveal.expiresAt-now)));",
    "if(document.hidden||!isCredentialSummaryContext()||resolveCredentialClientId()!==clientId)",
    "document.addEventListener('visibilitychange',()=>{if(document.hidden)clearCredentialEphemeralReveals();});",
    "window.addEventListener('pagehide',clearCredentialEphemeralReveals);",
    "window.addEventListener('beforeunload',clearCredentialEphemeralReveals);",
    "crm_unlock_credentials_v1",
    "crm_reveal_client_secret_value_v5",
    "setTimeout(hide,10000)",
)
for marker in required:
    if marker not in security:
        raise SystemExit(f'Missing credential eye self-heal marker: {marker}')

for forbidden in (
    "if(cell.getAttribute(FIELD_REVEAL_ATTR)==='1')return true;",
    "row.passwordCell.getAttribute(FIELD_REVEAL_ATTR)==='1'){",
    "cloud.rpc('crm_reveal_client_secrets'",
    "cloud.rpc('crm_reveal_client_secret_field_v3'",
    "cloud.rpc('crm_reveal_client_secret_field_v4'",
    "localStorage.setItem('growthops_credential",
    "sessionStorage.setItem('growthops_credential",
):
    if forbidden in security:
        raise SystemExit(f'Unsafe/stale/persistent credential reveal path survived: {forbidden}')

if security.count("credentialEphemeralReveals.set(") != 1:
    raise SystemExit('Ephemeral reveal store must have exactly one write path')
if "Date.now()+10000" not in security:
    raise SystemExit('Ephemeral reveal window is not capped at 10 seconds')

print('CREDENTIAL_EYE_SELF_HEAL_OUTPUT_OK: stale-marker=repair; unlock-rerender=reacquires-live-row; post-reveal-rerender=ephemeral-10s-rehydrate; hidden-page=clears; persistence=none; v5-scalar-preserved')
