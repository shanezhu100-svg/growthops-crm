# P0 Isolated Cloud Recovery Rehearsal

Rehearsal date: 2026-08-21 (America/Phoenix)

## Scope

This rehearsal validates CRM schema/security recovery without a paid Supabase Preview Branch, without a local Docker/Supabase setup, and without copying production customer data or production Vault plaintext.

- Production project: `avahcwyxparbcjdfglzx`
- Isolated recovery project: `jptlclzrbkotpvkjbbge` (`growthops-p0-recovery-test`)
- Region: `ap-southeast-1`
- Recovery project price reported by Supabase at creation: `$0/month`
- Production data copied: **none**
- Production Vault plaintext selected/decrypted/copied: **none**

The recovery project started with zero CRM users, workspaces, state rows, sessions, unlock rows, audit rows, Vault mappings, and Vault secrets.

## Recovery source

The recovery target was rebuilt from the live Production CRM schema/security definitions and verified against the deterministic P0 fingerprint.

During the rehearsal, `supabase_migrations.schema_migrations` was also inspected read-only. The previously missing eleven 2026-08-13/14 migration versions still retain their executed `statements[]` in the Production migration ledger. One early bootstrap migration contains a historical setup-code hash seed; that literal was deliberately not copied or exposed. The isolated test instead used runtime-generated synthetic setup credentials.

This document does not claim that a raw `pg_dump` file was produced. The adopted zero-download recovery gate is an isolated Supabase schema clone whose complete CRM structural/security fingerprint is identical to Production and whose credential flows passed synthetic recovery acceptance.

## Structural/security acceptance

Before synthetic data testing, the isolated target produced:

- Inventory lines: `258`
- SHA-256: `d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729`

This exactly matched Production and covers the same P0 inventory dimensions:

- CRM columns and defaults
- constraints
- indexes
- triggers
- all `crm_*` function definitions
- function EXECUTE privileges for `anon`, `authenticated`, and `service_role`
- direct CRM table grants
- RLS flags
- RLS policies

## Synthetic functional acceptance

Only generated test values were used in the isolated project.

Passed checks:

- Synthetic ADMIN bootstrap succeeds.
- Session expiration is capped at 7 days.
- Synthetic OPS user creation and login succeed.
- ADMIN `crm_save_state` stores credential material in the isolated Supabase Vault instead of ordinary workspace state.
- Ordinary `crm_workspace_state` contains no synthetic client password, account password, or supported 2FA secret value.
- `crm_load_state_v3` is secret-redacted for both ADMIN and OPS.
- OPS `crm_client_account_safe_summary` returns presence metadata (`hasPassword` / `has2FA`) without credential values.
- ADMIN secondary re-auth through `crm_unlock_credentials_v1` succeeds.
- ADMIN `crm_reveal_client_secret_value_v5` returns the expected synthetic account password as a single scalar field.
- ADMIN `crm_reveal_client_secret_value_v5(..., 'twofa')` returns the expected synthetic 2FA value when the stored secret key is a supported key such as `twoFactor`.
- OPS credential unlock is rejected with `FORBIDDEN`.
- OPS scalar credential reveal is rejected with `FORBIDDEN`.
- CRM audit payloads contain zero matches for the synthetic passwords/2FA values.

### 2FA test-key correction

An initial test intentionally used the literal JSON storage key `twofa`. That key is not one of the storage-secret aliases recognized by `crm_is_secret_key`; the API field selector `twofa` is not itself the canonical stored JSON key. The corrected acceptance uses the supported storage key `twoFactor`, which is redacted into Vault and is successfully returned through the v5 API selector `twofa`.

Production `crm_workspace_state` was checked read-only for keys containing `twofa`, `2fa`, `factor`, `totp`, or `secret`; no matching keys were present. No Production Vault plaintext was queried. The unsupported `twofa` storage alias should remain an explicit P3/P4 attack-regression case; it is not changed during P0 so the frozen Production fingerprint remains stable.

## Cleanup acceptance

After the synthetic rehearsal, all synthetic data was removed from the isolated project.

Post-cleanup counts:

- CRM users: `0`
- CRM workspaces: `0`
- CRM workspace state rows: `0`
- CRM Vault mappings: `0`
- CRM sessions: `0`
- CRM unlock rows: `0`
- CRM audit rows: `0`
- Vault secrets: `0`

The isolated project fingerprint after cleanup remained:

- `258`
- `d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729`

Production was then fingerprinted again and remained exactly:

- `258`
- `d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729`

Therefore the rehearsal caused no Production schema/security drift.

## Gate result

**P0 isolated cloud recovery gate: PASS.**

For this migration, the free isolated Supabase recovery clone is the accepted zero-download recovery proof. A separate offline `pg_dump` artifact may still be added later as portability hardening, but it is not represented here as already completed.

Next migration step remains P1 Cloudflare Pages Preview. P1 must not change Supabase schema, grants, Vault behavior, authentication, or CRM business behavior.
