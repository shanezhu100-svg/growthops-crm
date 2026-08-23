# Post-P5 trusted login source bucket

Last updated: 2026-08-23

## Status

Preparation only. Production remains on accepted `main@c803ccd5945d05434a592c2d3f1d2da9100d3db8` with:
- CRM functions: 40;
- direct function EXECUTE `PUBLIC/anon/authenticated/service_role = 0/0/0/12`;
- direct CRM table grants for browser/service roles: 0;
- direct CRM audit-sequence privileges for browser/service roles: 0;
- RLS: `9/9`;
- latest migration: `20260823123328 / post_p5_revoke_service_role_relation_acl`;
- canonical: `195 / edfcd23e20985252ca529aaeeb8a2cb1d22821c70202888806c5773c20df516b`.

## Problem

`crm_login` already has conservative brute-force controls: within 10 minutes it throttles after 12 failed attempts for the same source bucket + username, or 50 failures for one source bucket. The database stores only a truncated SHA-256 `sourceBucket`, never a raw IP.

After the browser path moved behind the same-origin Vercel/Cloudflare BFF, the BFF stopped forwarding a trustworthy visitor identity to PostgREST. Supabase can therefore observe a platform/proxy egress source instead of the actual visitor, which can make the 12/50 source thresholds group unrelated users together.

Observed 30-day audit before this preparation: 32 `LOGIN_FAILURE`, 4 distinct source buckets, 0 `LOGIN_THROTTLED`. There is no current lockout incident, but the source granularity is not guaranteed to be visitor-specific.

## Trust boundary

Vercel derives the login source from the platform-provided incoming `x-forwarded-for` value. Vercel documents that it overwrites this request header at the edge rather than accepting an arbitrary external value.

Cloudflare derives the login source from incoming `CF-Connecting-IP`, which is the Cloudflare edge-provided visitor address for the Pages Function request.

The BFF does not forward either raw address. It normalizes the trusted address, computes SHA-256 server-side, truncates to 24 lowercase hex characters, and sends only:

`x-growthops-source-bucket: <24-hex>`

A browser-supplied header with that name is ignored because outbound BFF headers are constructed from scratch.

## Database behavior

The new `crm_login` definition prefers `x-growthops-source-bucket` only when it matches exactly `^[0-9a-f]{24}$`.

For compatibility with trusted direct server/PostgREST callers, if the custom bucket is absent or invalid the existing `x-forwarded-for` / `cf-connecting-ip` hashing fallback is retained. Browser roles still cannot call CRM RPCs directly.

No threshold or login behavior changes:
- pair threshold: `12` failures / 10 minutes;
- source threshold: `50` failures / 10 minutes;
- invalid credentials and throttled attempts remain indistinguishable to the browser;
- `crm_login_v3` remains the BFF login entry;
- session/cookie behavior is unchanged;
- no raw IP is persisted.

## Deterministic DDL rehearsal

A Production transaction temporarily replaced only `crm_login` with the proposed definition, computed the frozen schema/security fingerprint, and rolled back without invoking login or writing the audit table.

Expected post-change canonical:

`195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`

After rollback, Production was rechecked and the custom bucket marker was absent.

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

## Hard gate

No Production change until the exact preparation head passes Vercel and Cloudflare builds, predecessor attack/session/RPC gates remain green, Cloudflare P1 output parity remains green, and a fresh Production freeze confirms the accepted predecessor state above.

After apply, require:
- `crm_login` owner/security-definer/search-path unchanged;
- function boundary still `0/0/0/12`;
- CRM function count still 40;
- direct CRM relation grants still 0;
- RLS still `9/9`;
- custom bucket marker + strict 24-hex validation present;
- compatibility fallback present;
- canonical exactly `195 / a69eba751a24ffbc98e5f47628c09c7b271b89d55ee7518d89cf3620391bd56e`.
