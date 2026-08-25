# Post-P5 Rate-Limit Concurrency Acceptance

Acceptance date: 2026-08-25

This document records the Production acceptance checkpoint for the Post-P5 rate-limit concurrency hardening. It is additive evidence for the current-state and recovery documents; it does not weaken the existing BFF, RPC ACL, RLS, Vault, or Preview fail-closed boundaries.

## Scope

Production migration:

- remote version: `20260825075808`
- migration name: `post_p5_rate_limit_concurrency`
- repository migration: `supabase/migrations/20260825_post_p5_rate_limit_concurrency.sql`
- exact rollback: `supabase/rollback/20260825_post_p5_rate_limit_concurrency.sql`
- preflight: `supabase/baseline/post_p5_rate_limit_concurrency_preflight.sql`
- read-only post-check: `supabase/baseline/post_p5_rate_limit_concurrency_check.sql`
- canonical regression test: `test_post_p5_rate_limit_concurrency.py`

The migration is intentionally limited to:

- `crm_login(text,text)`;
- `crm_unlock_credentials_v1(text,text)`;
- `crm_reveal_client_secret_value_v5(text,text,text,text,text,text)`.

Thresholds, authentication order, Vault scalar reveal semantics, and the accepted Post-P5 EXECUTE surface are unchanged.

## Accepted behavior

The three security-sensitive rate-limit subjects are serialized with transaction-level PostgreSQL advisory locks before their corresponding window counters are evaluated:

- login trusted-source/user bucket: namespace `90813011`;
- credential unlock per workspace/user: namespace `90813012`;
- credential reveal per workspace/user: namespace `90813013`.

This prevents concurrent requests for the same security subject from independently observing the same pre-limit state and overshooting the intended threshold.

Unlock/reveal rejection audit outcomes that must persist are returned as bounded safe JSON envelopes rather than being raised as transaction-aborting exceptions:

- `CREDENTIAL_UNLOCK_INVALID`;
- `CREDENTIAL_UNLOCK_THROTTLED`;
- `CREDENTIAL_REVEAL_THROTTLED`.

Both supported BFF implementations preserve the established HTTP contract by translating these known envelopes to the reviewed 400/429 responses and treating unknown envelopes as upstream contract failures. The browser still does not receive a Supabase secret or direct RPC access.

## Production database verification

A fresh read-only Production verification on 2026-08-25 confirmed:

- migration `20260825075808 / post_p5_rate_limit_concurrency` is present in `supabase_migrations.schema_migrations`;
- each of the three target functions contains exactly the intended transaction advisory-lock boundary and namespace;
- unlock invalid/throttled and reveal throttled committable envelopes are present;
- effective EXECUTE across the 40 current `crm_*` functions remains `anon / authenticated / service_role = 0 / 0 / 12`;
- the reviewed Post-P5 application-role ACL boundary was not broadened.

The primary deterministic CRM catalog/security fingerprint was refreshed because this migration changes three `crm_*` function definitions:

- inventory lines: `200`;
- SHA-256: `77ba3a7c646cf2ea04f41d20ceb1dd02aa9f041db7cbd2a0ad0386ddedbfba65`.

The supplemental repository-managed DDL-guard fingerprint is unchanged:

- guard inventory lines: `9`;
- guard SHA-256: `2a6c96fe5c2290cd30ee5b29800dcb47d9f1686d48b51344486c2c7780030140`.

The old primary `200 / bffaf123...` checkpoint is historical evidence for the pre-concurrency function definitions and must not be used as the current Production comparison anchor.

## Build and merge acceptance

PR #83, `Serialize security rate limits and persist rejection audits`, passed the canonical `CRM Build Gate` before merge.

- PR head: `775bd321b8f09c36609da7e10afa274662582bc4`;
- PR gate: run #68, completed / success;
- merged `main`: `0eefbe383d7ea8ecd7a874e7a8f7c4c9621763e6`;
- merged-main gate: run #69, push-triggered, completed / success.

The canonical repository build/security gate therefore accepted both the reviewed PR head and the resulting `main` commit.

## Production hosting alignment

The application/database drift that existed while Production Supabase had already advanced past the old BFF commit is closed.

Vercel Production:

- deployment: `dpl_FNtV2oBQWPYZrm8BaShVybUm57fF`;
- Git commit: `0eefbe383d7ea8ecd7a874e7a8f7c4c9621763e6`;
- state: `READY`;
- stable alias: `https://growthops-crm.vercel.app`.

Cloudflare Pages Production:

- deployment: `49a23f7f-5fbe-4894-9b8e-ad7b25005d70`;
- branch/commit: `main@0eefbe3`;
- state: `success`;
- observed build duration: 46 seconds.

At this checkpoint, Supabase Production, GitHub `main`, Vercel Production, and Cloudflare Pages Production are aligned on the accepted concurrency hardening.

## Preview secret boundary remains an operational item

The concurrency hardening is Production-accepted, but the previously documented Preview secret-boundary work is not fully closed at the platform layer.

Cloudflare Dashboard verification on 2026-08-25 showed that the Preview environment still has a `GROWTHOPS_SUPABASE_SECRET_KEY` binding. No secret value is recorded here. The repository guard correctly fails Preview closed when that server secret is present without an explicit isolated staging `GROWTHOPS_SUPABASE_URL`; this behavior must not be weakened to make Preview builds pass.

The correct Cloudflare platform remediation is either:

1. remove the Production server secret from Preview when Preview has no backend; or
2. configure an explicitly isolated staging Supabase URL and matching staging secret.

Vercel Production was independently verified, but the available connected Vercel interface did not expose environment-variable scope inspection and the browser session did not provide authenticated Vercel Dashboard access. Therefore the Vercel Preview secret scope remains **unverified**, not accepted or assumed clean.

## Rollback rule

Do not roll this migration back for a generic hosting, UI, Preview, Access, or routing problem. A database rollback is justified only for a diagnosed regression caused by the concurrency migration itself.

If such a regression is proven:

1. use only `supabase/rollback/20260825_post_p5_rate_limit_concurrency.sql`;
2. preserve the current Post-P5 EXECUTE and relation/sequence ACL boundaries;
3. re-run the corresponding read-only post-check and full canonical repository gate;
4. refresh the primary CRM fingerprint after the rollback because the three function definitions will change;
5. record the resulting hosting/database compatibility checkpoint before restoring normal traffic.

The rollback intentionally restores the accepted predecessor exception-based unlock/reveal rejection semantics; it is an exact predecessor restoration, not a privilege rollback.

## Acceptance result

Production concurrency hardening: **accepted**.

Production application/database alignment: **accepted**.

Cloudflare Preview platform secret isolation: **open operational item; runtime remains fail-closed**.

Vercel Preview platform secret isolation: **unverified operational item**.
