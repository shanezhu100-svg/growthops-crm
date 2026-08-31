from pathlib import Path

ROOT = Path(__file__).resolve().parent
SECURITY = (ROOT / 'dist' / 'cloud-security-hotfix.js').read_text(encoding='utf-8')
BRIDGE = (ROOT / 'dist' / 'cloud-ui-action-bridge.js').read_text(encoding='utf-8')
MIGRATION = (ROOT / 'supabase/migrations/20260830071649_client_account_safe_summary_correspondence.sql').read_text(encoding='utf-8')


def require(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit('CLIENT_ACCOUNT_CORRESPONDENCE_OUTPUT_FAILED: ' + message)


# Multi-account summary must resolve by the currently visible account ID and never
# reuse one platform-level summary across multiple cards. Client edit is a special
# case: internal IDs may not be rendered into the card at all, so after exact token
# matching fails it may use the stable platform-local v-for order.
for marker in (
    "facebook:{listKey:'fbAccounts',summaryKey:'facebookAccounts',pager:'FB',legacyKey:'facebook'}",
    "tiktok:{listKey:'tkAccounts',summaryKey:'tiktokAccounts',pager:'TK',legacyKey:'tiktok'}",
    "google:{listKey:'googleAccounts',summaryKey:'googleAccounts',pager:'GOOGLE',legacyKey:''}",
    "instagram:{listKey:'instagramAccounts',summaryKey:'instagramAccounts',pager:'INSTAGRAM',legacyKey:''}",
    "const currentId=String(current?.id??'')",
    "summaries.find(item=>String(item?.id??'')===currentId)",
    "if(vm.currentPage==='client-form'&&list.length>1)",
    "const platformRows=locateCredentialRows().filter(candidate=>candidate.platform===row.platform)",
    "const rowIndex=platformRows.findIndex(candidate=>candidate.card===row.card)",
    "if(rowIndex>=0&&rowIndex<list.length)return list[rowIndex]",
    "if(platformAccounts.length<=1)return accountSafeSummaryData?.[config.legacyKey]||null",
    "return null;",
):
    require(marker in SECURITY, 'account-correspondence marker missing: ' + marker)

require("if(row.platform==='facebook'||row.platform==='tiktok')return accountSafeSummaryData?.[row.platform]||null" not in SECURITY,
        'legacy platform-level FB/TK summary path still present')

# Every client-form credential section must classify to the same four platform keys
# understood by credentialPlatformConfig. Otherwise overlays can render but remain
# blank because summaryForCredentialRow receives an empty platform key.
for marker in (
    "if(value.includes('facebook'))return 'facebook';",
    "if(value.includes('tiktok'))return 'tiktok';",
    "if(value.includes('google'))return 'google';",
    "if(value.includes('instagram'))return 'instagram';",
):
    require(marker in SECURITY, 'four-platform card ancestry resolver missing: ' + marker)

# The ordinal fallback must stay confined to the edit form; detail/assets keep their
# pager/token mapping and fail closed instead of guessing across multiple accounts.
require(SECURITY.count("vm.currentPage==='client-form'&&list.length>1") == 1,
        'client-form order fallback scope drifted')

# Refresh persistence is metadata-only and waits for authenticated state before it
# restores a protected route.
for marker in (
    "const UI_ROUTE_STATE_KEY='growthops_ui_route_state_v1'",
    "const UI_ROUTE_SELECTION_KEYS=['selectedClientId','selectedAssetsClientId','selectedAdsClientId','selectedAnalyticsClientId','selectedSopClientId','selectedSopAccountKey']",
    "if(uiRouteStateRestored||!vm.currentUser)return",
    "const page=UI_ROUTE_PAGES.has(hashPage)?hashPage:(stored?.page||'')",
    "sessionStorage.setItem(UI_ROUTE_STATE_KEY,raw)",
    "sessionStorage.removeItem(UI_ROUTE_STATE_KEY)",
    "syncUiRouteState();",
    "setInterval(()=>{syncDetailClientPager();install()},250)",
    "vm.resetAssetPager('detail')",
    "const CLIENT_DETAIL_RETURN_KEY='growthops_client_detail_return_page'",
):
    require(marker in BRIDGE, 'refresh/detail-state marker missing: ' + marker)

route_start = BRIDGE.find("const UI_ROUTE_STATE_KEY")
route_end = BRIDGE.find("const CLIENT_DETAIL_RETURN_KEY", route_start)
require(route_start >= 0 and route_end > route_start, 'unable to bound route-state implementation')
route_region = BRIDGE[route_start:route_end].lower()
for forbidden in ('token_key', 'loginaccount', 'loginpassword', 'password', 'twofa', 'credential', 'accountsafe', 'vault'):
    require(forbidden not in route_region, 'sensitive value entered refresh persistence: ' + forbidden)

# DB package must return the same id-keyed safe-array model for all four credential
# platforms while preserving the service-only execution boundary. Password/2FA may
# be inspected only to calculate booleans and must never enter the response payload.
for marker in (
    "'facebookAccounts',v_facebook",
    "'tiktokAccounts',v_tiktok",
    "'googleAccounts',v_google",
    "'instagramAccounts',v_instagram",
    "from jsonb_array_elements(coalesce(v_client->'fbAccounts','[]'::jsonb)) with ordinality",
    "from jsonb_array_elements(coalesce(v_client->'tkAccounts','[]'::jsonb)) with ordinality",
    "from jsonb_array_elements(coalesce(v_client->'googleAccounts','[]'::jsonb)) with ordinality",
    "from jsonb_array_elements(coalesce(v_client->'instagramAccounts','[]'::jsonb)) with ordinality",
    "into v_facebook",
    "into v_tiktok",
    "into v_google",
    "into v_instagram",
    "'loginAccount',coalesce(e.value->>'loginAccount','')",
    "'hasPassword',public.crm_secret_value_nonempty(e.value->'loginPassword')",
    "revoke all on function public.crm_client_account_safe_summary(text,text) from public, anon, authenticated",
    "grant execute on function public.crm_client_account_safe_summary(text,text) to service_role",
):
    require(marker in MIGRATION, 'migration marker missing: ' + marker)

for forbidden_key in ("'loginPassword',", "'password',", "'2FA',", "'twoFactor',"):
    require(forbidden_key not in MIGRATION, 'safe-summary response appears to expose secret key: ' + forbidden_key)

print(
    'CLIENT_ACCOUNT_CORRESPONDENCE_OUTPUT_OK: '
    'login-account=direct-safe-summary+id-matched; multi-account=client-form-order-fallback+nonform-fail-closed; '
    'platform-card=facebook+tiktok+google+instagram; '
    'refresh=session-route+selection-metadata-only; detail-pager=client-isolated; '
    'db=facebook+tiktok+google+instagram-per-account-summary+service-role-only'
)
