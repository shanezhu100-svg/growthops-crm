# Post-P5 v5 Direct Scalar Reveal

Status: **Production accepted** on 2026-08-24 UTC.

## Why

The browser/BFF credential surface was already restricted to `crm_reveal_client_secret_value_v5`, and v5 returned only one `value`. However, the original v5 implementation internally called the server-only v3 helper, which decrypted the workspace Vault tree and constructed a broader `{loginPassword, accountSecrets}` JSON bundle before v5 selected one scalar.

That bundle never crossed the browser boundary and v3/v4 had no browser or service-role EXECUTE after P5, so this was not an external exposure. This hardening reduces internal plaintext copies and lifetime.

## Accepted behavior

The replacement keeps the v5 signature and browser contract unchanged while removing the v3/v4/full-client dependency. It:

- requires ADMIN;
- requires the exact password-verified 10-minute unlock token bound to the same live session, user and workspace;
- validates only password/twofa and facebook/tiktok/google/instagram;
- preserves the existing `field-v1` rate-limit namespace (10 per 5 minutes, 40 per hour);
- preserves `REVEAL_CLIENT_SECRET_FIELD` and throttle audit metadata without adding secret values;
- reads the encrypted workspace Vault document once, selects one client/platform/account, strips login identifiers from the selected account, and asks the existing scalar helper only for the requested password/twofa value;
- preserves Facebook/TikTok platform-login-password fallback semantics for password only;
- clears non-returned JSON references before serializing the result;
- keeps v5 executable only by `service_role`; browser roles remain at zero direct database EXECUTE after P5.

The 12-hour v3 session-freshness branch does not need a second check in v5: v5 already requires the exact unexpired unlock token, and that token can only be created by re-entering the current ADMIN password. The 2026-08-23 re-auth bridge intentionally treats that valid unlock as the fresh re-auth signal.

## Storage granularity limit

Vault currently stores one encrypted secret JSON document per workspace, so a database function still has to decrypt that workspace document before selecting a field. Eliminating that would require a separate storage-model migration (for example, one Vault item per account/field) and is intentionally out of scope.

## Production acceptance

- Read-only preflight: `POST_P5_V5_DIRECT_SCALAR_PREFLIGHT_OK`.
- Tracked Supabase migration: `20260824005806 post_p5_v5_direct_scalar`.
- Read-only post-check: `POST_P5_V5_DIRECT_SCALAR_OK`.
- Live function fingerprint (MD5 of `pg_get_functiondef`): `d5825feb1a40aad7d9b65fe6e7491b7d`.
- Live v5 properties: SECURITY DEFINER, `search_path=public, pg_catalog`, direct `crm_read_workspace_secrets` present, v3 dependency absent.
- Live function ACL after migration: v5 `service_role=true`, `anon=false`, `authenticated=false`.
- Whole CRM function EXECUTE totals after migration: anon `0`, authenticated `0`, service_role `12`.
- Pure synthetic helper semantics: direct password, direct 2FA, nested password, nested TOTP, backup-code array and login-identifier exclusion all passed.
- Supabase Security Advisor after migration: unchanged; only nine intentional `RLS enabled / no policy` INFO findings.
- Supabase Performance Advisor after migration: unchanged; only five unused-index INFO findings.
- Both BFFs remain allowlisted for v5 only; v3/v4/full-client reveal are not browser-facing RPCs.

A transaction-style synthetic workspace/session/unlock/Vault end-to-end probe was intentionally **not executed** because the tool safety layer rejected construction of credential-like test material. The rejected call did not reach PostgreSQL and created no records. Production acceptance therefore relies on the read-only pre/post checks, live function/ACL catalog evidence, synthetic scalar-helper tests, and the existing BFF/P5 regression suite.

## Rollback

`supabase/rollback/20260824_post_p5_v5_direct_scalar_rollback.sql` restores only v5's previous internal v3 composition. It intentionally preserves the Post-P5 execution boundary: PUBLIC/anon/authenticated stay revoked and only `service_role` remains executable.

## Repository/deployment follow-through

After this acceptance record is committed, merge the candidate branch so the canonical repository contains the already-applied migration. Production application builds must then pass `test_post_p5_v5_direct_scalar.py` in addition to the existing Preview-secret, P2/P3/P4/P5 and Post-P5 gates.
