# Cloudflare Migration Rollback

This runbook keeps the currently validated Vercel deployment as the recovery origin while Cloudflare is introduced in phases.

## Frozen Vercel recovery target

- Production deployment: `dpl_GrqUWZuHikcp2LX5PTpyozLC8skH`
- Production URL: `https://growthops-gkume1n0z-shanezhu100-svgs-projects.vercel.app`
- Stable alias: `https://growthops-crm.vercel.app`
- Stable Git commit: `78fa37c34501302ed7cd27cc5804cb055d90a932`
- Checkpoint state: `READY`

Do not delete or redeploy this recovery target as part of P1 Cloudflare Preview work.

## P1 rollback: Pages/static hosting only

P1 does not change Supabase or authentication.

If Cloudflare Pages Preview is broken:

1. Stop using the Cloudflare Preview URL.
2. Continue using the frozen Vercel production/preview.
3. Leave Supabase untouched.
4. Fix the Cloudflare build/output configuration in a new preview.

No database rollback is required because P1 must not change the database.

## P2 rollback: Worker `/api/crm` migration

During the first Worker phase, preserve the existing same-origin `/api/crm` contract.

If Worker API behavior is incorrect:

1. Disable/remove the Cloudflare Worker route serving the CRM API or route CRM traffic back to Vercel.
2. Restore the Vercel origin as the active application/API path.
3. Do not revoke transitional Supabase `anon` RPC grants until Worker Preview has passed acceptance; this preserves the Vercel BFF rollback path.
4. Verify login, cookie session restore, state load/save, account summary, credential unlock/reveal, and logout.

## P5 rollback: Supabase RPC privilege tightening

After Cloudflare Worker begins using a privileged server-side Supabase identity, RPC grants will be reduced in small forward migrations.

Rules:

- Revoke one logical group at a time.
- Commit every privilege change as migration SQL.
- Validate Cloudflare Preview before the next revoke.
- If rollback to Vercel is still required after a revoke, use an explicit reviewed forward migration to restore only the minimum execution grant needed by the frozen Vercel BFF.
- Do not casually restore broad v3/v4/full credential reveal access.

## Access/WAF rollback

If Cloudflare Access, WAF, or rate limiting blocks legitimate CRM use:

1. Roll back or disable the specific Cloudflare policy/rule first.
2. Keep CRM/Supabase data unchanged.
3. Confirm the origin application still works before changing any application code.
4. Never solve an Access/WAF issue by weakening Vault, Session, RLS, or credential RPC controls.

## Production cutover rollback

If Cloudflare Production fails after DNS/hostname cutover:

1. Disable conflicting Worker/Access routing as needed.
2. Route the CRM hostname back to the preserved Vercel origin using the previously verified DNS configuration.
3. Confirm HTTPS resolves correctly.
4. Run the smoke checks below.
5. Inspect Worker/Supabase errors before attempting another cutover.

Exact DNS record values must be recorded when the production domain is actually configured. Do not invent them in advance.

## Mandatory smoke checks after rollback

- Homepage and static assets load.
- Login succeeds for an authorized CRM user.
- Refresh preserves the HttpOnly session.
- `GET /api/crm` is rejected safely rather than executing an API action.
- State loads and saves normally.
- “All clients” and single-client navigation work.
- Credential unlock requires ADMIN reauthentication.
- Reveal returns only the requested field and hides again on schedule/backgrounding.
- OPS cannot reveal password/2FA.
- Logout clears the session.
- Workspace sensitive-key scan remains `0`.
- Audit sensitive payload-value scan remains `0`.
- Vault secret count has not changed because of hosting rollback.

## Vault rule

Vault is not migrated to Cloudflare ordinary storage. Hosting/API rollback must never involve exporting customer passwords/2FA into Pages, Workers KV, D1, R2, logs, GitHub, or normal CRM backups.
