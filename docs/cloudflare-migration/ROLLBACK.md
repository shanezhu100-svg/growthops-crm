# Cloudflare Migration Rollback

Last reviewed: 2026-08-24

This runbook describes recovery for the **current server-boundary architecture** after P2-B, P5, and Post-P5 hardening. It preserves the validated Vercel same-origin BFF path as the primary hosting fallback without reopening browser/`anon` Supabase privileges.

## Current Vercel recovery principle

Use the most recent **READY Production deployment from `main` that corresponds to a commit already accepted by the complete canonical CRM Build Gate**. Do not permanently pin rollback to an old pre-P5 application release, because older code may assume database privileges that have since been intentionally removed.

Validated checkpoint at this review:

- Production deployment: `dpl_3zL8NYGHxmSZPixUdVtUWV5g551s`
- Production URL: `https://growthops-ec5gbp67e-shanezhu100-svgs-projects.vercel.app`
- Stable alias: `https://growthops-crm.vercel.app`
- Git commit: `ddcfe1ce48238c630364a5273185c47e1b0b36ed`
- Checkpoint state: `READY`
- Vercel rollback-candidate state: `true`
- 5xx runtime log check at review: no matching Production 5xx entries in the preceding 24-hour window.

This checkpoint is evidence, not an immutable forever-pin. Before an actual rollback, verify that the selected Vercel deployment is still `READY`, maps to the intended `main` commit, and remains compatible with the then-current Supabase privilege state.

## Current architecture invariants

A hosting rollback must preserve all of these controls:

- browser traffic uses the same-origin `/api/crm` BFF;
- CRM session material remains in the `__Host-growthops_crm` HttpOnly, Secure, SameSite=Strict cookie;
- browser Supabase URL/key globals and direct browser RPC access remain absent from the shipped application;
- both Vercel and Cloudflare BFFs use the server-only Supabase identity boundary;
- Production Supabase origin remains pinned to the canonical project;
- current P5 state keeps `anon` CRM RPC EXECUTE at zero;
- Post-P5 service-role minimization and direct relation ACL restrictions remain in force;
- credential reveal remains v5 single-scalar only and ADMIN reauthentication remains required.

Do not treat database privilege rollback as a normal hosting rollback step.

## P1 historical rollback: Pages/static hosting only

P1 did not change Supabase or authentication. Its original recovery action was simply to stop using the Cloudflare Preview URL and continue on Vercel.

No database rollback was required for P1.

## P2/P2-B hosting rollback: `/api/crm` server boundary

The Vercel and Cloudflare implementations now share the same server-only Supabase identity model. If the Cloudflare application/API path is unhealthy but Supabase itself is healthy:

1. Disable or bypass the affected Cloudflare route/policy as appropriate, or route the CRM hostname back to the validated Vercel Production origin.
2. Select a Vercel deployment that is `READY`, accepted by the canonical gate, and compatible with the current database privilege state.
3. Keep the server-only Supabase secret and canonical Production origin boundary intact.
4. **Do not restore `anon` RPC grants merely to make an older application build work.** Prefer the current compatible Vercel BFF path.
5. Verify login, cookie-session restore, state load/save, account summary, credential unlock/reveal, and logout.

If a candidate Vercel rollback build requires a privilege that current Post-P5 Production intentionally removed, stop and choose a compatible application deployment instead of broadening the database surface.

## P5/Post-P5 database rollback

P5 and Post-P5 changes are security migrations, not hosting toggles. Their rollback SQL is retained for narrowly diagnosed regressions and must be applied only to the exact affected migration/control.

Rules:

- never restore broad `anon` EXECUTE as a generic emergency measure;
- never restore pre-P5 browser/direct-RPC behavior;
- identify the exact failed migration or ACL control first;
- use only the matching reviewed rollback SQL under `supabase/rollback/`;
- preserve unaffected P5/Post-P5 revocations and ACL hardening;
- re-run the associated read-only post-check and the canonical repository gate immediately after any database rollback;
- record the resulting Production fingerprint/ACL state before resuming traffic changes.

The historical Group 1 rollback for the two sensitive credential RPCs remains documented in `P5_RPC_REVOCATION.md`, but its own trigger is narrow: a proven failure of the server-only identity path for those RPCs while the expected service-role privilege should exist. A UI-only defect is not a permission rollback trigger.

Later P5/Post-P5 controls have their own exact rollback artifacts. Do not combine them into one broad privilege restoration.

## Preview rollback / fail-closed rule

Preview environments must not silently target Production Supabase. If a Cloudflare or Vercel Preview has a server secret but no explicit isolated staging `GROWTHOPS_SUPABASE_URL`, the expected behavior is fail-closed.

Fix Preview by either:

1. configuring an explicit isolated staging Supabase URL compatible with the Preview secret; or
2. removing the Preview server secret when no Preview backend should be active.

Never bypass the Preview boundary by weakening Production origin checks or defaulting Preview to Production Supabase.

## Access/WAF rollback

If Cloudflare Access, WAF, or rate limiting blocks legitimate CRM use:

1. roll back or disable only the specific Cloudflare policy/rule causing the failure;
2. keep CRM/Supabase data and database privileges unchanged;
3. confirm the origin application still works before changing application code;
4. never solve an Access/WAF issue by weakening Vault, Session, RPC, origin, RLS, or credential controls.

## Production cutover rollback

If a Cloudflare Production hostname/routing cutover fails:

1. freeze further routing/security changes until the failure mode is identified;
2. disable only the conflicting Worker/Access/routing rule as needed;
3. route the CRM hostname back to the validated current Vercel Production origin using the previously verified DNS configuration;
4. confirm HTTPS and the stable application origin resolve correctly;
5. run the mandatory smoke checks below;
6. inspect Cloudflare/BFF/Supabase errors before attempting another cutover.

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
- Browser direct Supabase configuration/RPC material remains absent.
- Workspace sensitive-key scan remains `0`.
- Audit sensitive payload-value scan remains `0`.
- Current P5/Post-P5 privilege checks remain at their accepted state, including zero `anon` CRM RPC EXECUTE.
- Vault secret count has not changed because of hosting rollback.
- The canonical `sh build.sh && python3 cloudflare_p1_verify.py` gate remains green for the selected application commit.

## Vault rule

Vault is not migrated to Cloudflare ordinary storage. Hosting/API rollback must never involve exporting customer passwords/2FA into Pages, Workers KV, D1, R2, logs, GitHub, or normal CRM backups.
