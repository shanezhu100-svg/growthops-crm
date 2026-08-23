# Post-P5 trusted login source bucket

Last updated: 2026-08-23

## Status

Production hardening is applied and verified. Accepted predecessor was `main@c803ccd5945d05434a592c2d3f1d2da9100d3db8` with:
- CRM functions: 40;
- direct function EXECUTE `PUBLIC/anon/authenticated/service_role = 0/0/0/12`;
- direct CRM table/sequence grants for browser and service roles: 0;
- RLS: `9/9`;
- migration `20260823123328 / post_p5_revoke_service_role_relation_acl`;
- canonical `195 / edfcd23e20985252ca529aaeeb8a2cb1d22821c70202888806c5773c20df516b`.

## Problem

`crm_login` already has conservative brute-force controls: within 10 minutes it throttles after 12 failed attempts for the same source bucket + username, or 50 failures for one source bucket. The database stores only a truncated SHA-256 `sourceBucket`, never a raw IP.

After the browser path moved behind the same-origin Vercel/Cloudflare BFF, the BFF stopped forwarding a trustworthy visitor identity to PostgREST. Supabase could therefore observe a platform/proxy egress source instead of the actual visitor, grouping unrelated visitors under the 12/50 source thresholds.

Observed 30-day audit before this hardening: 32 `LOGIN_FAILURE`, 4 distinct source buckets, 0 `LOGIN_THROTTLED`. No active lockout incident was found.

## Trust boundary

Vercel derives the login source from the platform-provided incoming `x-forwarded-for` value. Vercel documents that it overwrites this request header at the edge rather than accepting an arbitrary external value.

Cloudflare derives the login source from incoming `CF-Connecting-IP`, the Cloudflare edge-provided visitor address for the Pages Function request.

The BFF does not forward either raw address. It normalizes the trusted address, computes SHA-256 server-side, truncates to 24 lowercase hex characters, and sends only:

`x-growthops-source-bucket: <24-hex>`

A browser-supplied header with that name is ignored because outbound BFF headers are constructed from scratch. The bucket is sent only on the login RPC path.

## Database behavior

`crm_login` now prefers `x-growthops-source-bucket` only when it matches exactly `^[0-9a-f]{24}$`.

For compatibility with trusted direct server/PostgREST callers, if the custom bucket is absent or invalid the existing `x-forwarded-for` / `cf-connecting-ip` hashing fallback remains. Browser roles still cannot call CRM RPCs directly.

No threshold or login behavior changed:
- pair threshold: `12` failures / 10 minutes;
- source threshold: `50` failures / 10 minutes;
- invalid credentials and throttled attempts remain indistinguishable to the browser;
- `crm_login_v3` remains the BFF login entry;
- session/cookie behavior is unchanged;
- no raw IP is persisted.

## Deterministic DDL rehearsal

Before apply, a Production transaction temporarily replaced only `crm_login` with the proposed definition, computed the frozen schema/security fingerprint, and rolled back without invoking login or writing the audit table.

Predicted post-change canonical:

`195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`

Rollback was verified: Production returned to the predecessor definition before the real apply.

## Preparation evidence

Preparation head:
`02c25885bf5189b3b8a47c8d2d45aa65cbb2ee1b`

Vercel:
- deployment `dpl_8EsiEfJc8jrm1qHrWYu3KWLt9wQC`;
- READY;
- exact commit `02c25885...`;
- trusted-source JS and package gates PASS;
- P3/P4, session, P5 and prior post-P5 gates PASS.

Cloudflare:
- deployment `e9f38e2f-439d-4382-b5bd-6ca2c7e60f86`;
- exact URL `https://e9f38e2f.growthops-crm.pages.dev/`;
- success;
- exact commit `02c25885...`;
- trusted-source gates PASS;
- P1 output parity PASS;
- site deployed successfully.

Fresh Production freeze immediately before apply confirmed zero drift at 40 functions, function EXECUTE `0/0/0/12`, direct relation ACL 0, RLS `9/9`, no custom bucket marker, migration `20260823123328`, and canonical `195 / edfcd23e20985252ca529aaeeb8a2cb1d22821c70202888806c5773c20df516b`.

## Production result

Applied migration:

`20260823131002 / post_p5_login_trusted_source_bucket`

Verified after apply:
- CRM functions: 40;
- function EXECUTE `0/0/0/12`;
- direct CRM table grants: 0;
- direct audit-sequence privileges: 0;
- RLS `9/9`;
- `crm_login` owner: `postgres`;
- `crm_login` remains SECURITY DEFINER with `search_path=public, extensions`;
- custom source bucket marker: present;
- strict 24-hex validation: present;
- legacy source-header compatibility fallback: present;
- canonical exactly `195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`.

## Package

Forward migration:
`supabase/migrations/20260823_post_p5_login_trusted_source_bucket.sql`

Exact rollback:
`supabase/rollback/20260823_post_p5_login_trusted_source_bucket.sql`

Read-only checks:
- `supabase/baseline/post_p5_login_trusted_source_bucket_preflight.sql`
- `supabase/baseline/post_p5_login_trusted_source_bucket_check.sql`

Regression gates:
- `test_post_p5_login_trusted_source_bucket.mjs`
- `test_post_p5_login_trusted_source_bucket.py`

BFF files:
- `api/crm.js`
- `functions/api/crm.js`

## Final merge gate

The final evidence-only head must again pass Vercel and Cloudflare, including trusted-source gates, predecessor P3/P4/session/RPC gates and Cloudflare P1 parity. Immediately before merge, re-confirm Production at 40 functions, function EXECUTE `0/0/0/12`, direct CRM relation ACL 0, RLS `9/9`, migration `20260823131002`, and canonical `195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`.
