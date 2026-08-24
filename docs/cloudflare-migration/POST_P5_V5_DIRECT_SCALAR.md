# Post-P5 v5 Direct Scalar Reveal

Status: candidate prepared; production migration not yet accepted.

## Why

The browser/BFF credential surface is already restricted to `crm_reveal_client_secret_value_v5`, and v5 returns only one `value`. However, the original v5 implementation internally called the server-only v3 helper, which decrypted the workspace Vault tree and constructed a broader `{loginPassword, accountSecrets}` JSON bundle before v5 selected one scalar.

That bundle never crossed the browser boundary and v3/v4 have no browser or service-role EXECUTE after P5, so this is not a current external exposure. It is an internal least-data/lifetime improvement.

## Candidate behavior

The replacement keeps the v5 signature and browser contract unchanged while removing the v3/v4/full-client dependency. It:

- requires ADMIN;
- requires the exact password-verified 10-minute unlock token bound to the same live session, user and workspace;
- validates only password/twofa and facebook/tiktok/google/instagram;
- preserves the existing `field-v1` rate-limit namespace (10 per 5 minutes, 40 per hour);
- preserves `REVEAL_CLIENT_SECRET_FIELD` and throttle audit metadata without adding secret values;
- reads the encrypted workspace Vault document once, selects one client/platform/account, strips login identifiers from the selected account, and asks the existing scalar helper only for the requested password/twofa value;
- preserves Facebook/TikTok platform-login-password fallback semantics for password only;
- clears non-returned JSON references before serializing the result;
- keeps v5 executable only by `service_role`; browser roles still have zero direct database EXECUTE after P5.

The 12-hour v3 session-freshness branch does not need a second check in v5: v5 already requires the exact unexpired unlock token, and that token can only be created by re-entering the current ADMIN password. The 2026-08-23 re-auth bridge intentionally treats that valid unlock as the fresh re-auth signal.

## Storage granularity limit

Vault currently stores one encrypted secret JSON document per workspace, so a database function still has to decrypt that workspace document before selecting a field. Eliminating that would require a separate storage-model migration (for example, one Vault item per account/field) and is intentionally out of scope.

## Acceptance sequence

1. Run `post_p5_v5_direct_scalar_preflight.sql` read-only against Production.
2. Run repository build/static gates including `test_post_p5_v5_direct_scalar.py`.
3. Apply `20260824_post_p5_v5_direct_scalar.sql` as a tracked Supabase migration.
4. Run `post_p5_v5_direct_scalar_check.sql` read-only.
5. Re-run P5/Post-P5 ACL checks and advisors.
6. Confirm v5 still has service-role EXECUTE only and v3/v4 remain unreachable through both BFF allowlists.
7. Record the production migration version and live function fingerprint before merging the candidate branch.

Rollback is `supabase/rollback/20260824_post_p5_v5_direct_scalar_rollback.sql`; it restores only v5's previous internal v3 composition and intentionally does not reopen any P5 browser grants.
