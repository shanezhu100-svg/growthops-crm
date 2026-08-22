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
    "requestAnimationFrame(()=>{",
    "credentialUiV5Render();",
    "const liveRows=locateCredentialRows().filter(candidate=>candidate.platform===row.platform&&String(accountIdForProtectedField(candidate)||'')===targetId);",
    "const liveRow=liveRows.length===1?liveRows[0]:null;",
    "if(liveToggle){liveToggle.click();return;}",
    "管理员验证成功；凭证区域已刷新，请再次点击眼睛查看",
    "const accountId=targetAccountId;",
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
):
    if forbidden in security:
        raise SystemExit(f'Unsafe/stale credential eye path survived: {forbidden}')

print('CREDENTIAL_EYE_SELF_HEAL_OUTPUT_OK: marker-alone=no-longer-trusted; unlock-rerender=reacquires-live-row; ambiguous-row=no-auto-reveal; v5-scalar-preserved')
