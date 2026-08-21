# Cloudflare Migration P0 Baseline

Checkpoint date: 2026-08-21

This file freezes the known-good CRM state before any Cloudflare Pages/Workers migration. P1 must not change database behavior, authentication behavior, Vault contents, or CRM business behavior.

## Application checkpoint

- Repository: `shanezhu100-svg/growthops-crm`
- Stable branch: `main`
- Stable commit: `78fa37c34501302ed7cd27cc5804cb055d90a932`
- Canonical source bytes: `643031`
- Canonical source SHA-256: `51ca745531e98d1799d0ac181e97e29a1fdd6ea2eb77587b41051d9519103e43`

### Frozen Vercel production

- Deployment: `dpl_GrqUWZuHikcp2LX5PTpyozLC8skH`
- Deployment URL: `https://growthops-gkume1n0z-shanezhu100-svgs-projects.vercel.app`
- Production alias: `https://growthops-crm.vercel.app`
- State at checkpoint: `READY`
- Git commit built: `78fa37c34501302ed7cd27cc5804cb055d90a932`

### Frozen validated preview

- Deployment: `dpl_9bep7ksS55U1F4zu2HTyvcMBsqBj`
- Deployment URL: `https://growthops-1tbvyfmty-shanezhu100-svgs-projects.vercel.app`
- Branch alias: `https://growthops-crm-git-refactor-cre-e28e6f-shanezhu100-svgs-projects.vercel.app`
- State at checkpoint: `READY`
- Source branch: `refactor-credential-ui-pipeline-20260821`
- Source commit: `3e372e0b07854c6ccd74f36009b823533a96150e`
- Pull request: `#13`

## Production output integrity checkpoints

The values below were re-read directly from the build log of production deployment `dpl_GrqUWZuHikcp2LX5PTpyozLC8skH`. They supersede older pre-merge/intermediate hash notes. P1 must reproduce these current production outputs unless a deliberate, separately reviewed build change is made.

- Credential controller index: `3fb5874a43264d74e55222be7c19fa2a0abaa516a0b3fe480e6bcf327cdbe11e`
- Credential controller security: `c47e0ebc7c5c09fdee1f542974ec4e560e5d46987f523d1995f2a4d34d51976c`
- Credential runtime index: `14bcf8c660fbd7dc8721237af00e100fea1584f3193fe6fa4a0b584454ea03f2`
- Credential runtime security: `366c4c2dd3e649efc2c153382eac5009a593ffd00e4b24c20d8de799d48d8cba`
- HttpOnly index: `29c83f4c9d9e98ae4c84a801f3db99194340cad086480b9872367d7596ccf53c`
- HttpOnly adapter: `2a5b5da0f94ba66a2b58ed64b923e0167e7723eb7ccccd3c6384dfbeb471a2a6`
- HttpOnly security: `ebe0cc3fe1ff4d40481973b188a799700b786a958ef492a36b5b6ed541617a25`
- HttpOnly P1 override: `e50e05322a0d56e78bf112a52be08ff54263f4ce88cb0b9b91f6613722b8ccab`
- HttpOnly UI bridge: `c9ce3c3474fd0c623eb4c15ace8fc8d2ce90134b4d99c06d2d82d430a03de090`
- Client-detail final index: `b965f8f637a5c6a4dcb9e9f7b6d41d396a0fa696a691126e227fe682f2b245cd`
- Client-detail final bridge: `b15e0b792e2f0ba6e99bef53fea96dde78b647b5528ae199311c4be9b37027a7`
- Final module-home index: `941be51fcaf60acd0bb350c1822260f24555340fb2d719effe0f339c3b69a1e5`

## Supabase checkpoint

- Project ID: `avahcwyxparbcjdfglzx`
- Vault secret rows at checkpoint: `1`
- `crm_workspace_state` sensitive-key matches: `0`
- `crm_server_audit_logs` sensitive payload-value matches: `0`
- Schema/security inventory lines: `258`
- Schema/security composite SHA-256: `d78c430cdd33757f50a5286b66c0095e3ff322d64f364eb4b61f1a517fd3d729`
- Fingerprint query: `supabase/baseline/p0_schema_security_fingerprint.sql`
- Detailed structural snapshot: `P0_SCHEMA_MANIFEST.md`
- Audit metadata may contain non-secret booleans such as `passwordChanged`; these do not count as credential payload values.
- CRM business tables observed at checkpoint have RLS enabled.
- No RLS policies were present on the `crm_*` business tables at checkpoint; direct table access therefore remains default-deny and application access is mediated through controlled functions.
- Session expiry, active-session cap, credential-unlock revocation, and workspace secret-guard triggers were present at checkpoint.

## Existing browser/server security boundary

Do not rebuild these mechanisms during P1. Preserve them byte-for-byte where possible.

- CRM bearer token is not stored in browser `localStorage`.
- Browser transport is same-origin `/api/crm`, not direct Supabase REST/RPC transport.
- Session cookie: `__Host-growthops_crm`; `HttpOnly`; `Secure`; `SameSite=Strict`; maximum application session lifetime 7 days.
- Maximum active CRM sessions per user: 4.
- `/api/crm` has an explicit RPC allowlist and injects the cookie-backed session token server-side.
- Login token is stripped before response data reaches browser JavaScript.
- Credential reveal uses only `crm_reveal_client_secret_value_v5` in the browser-facing path.
- Legacy full-client/v3/v4 credential reveal functions are not browser-executable.
- Credential values remain in Supabase Vault and are never migrated into ordinary Cloudflare storage.

## Remaining anon RPC execution at checkpoint

These grants are intentionally retained until the Cloudflare Worker can call Supabase with a privileged server-side identity and has passed Preview acceptance. Do **not** revoke them during P0 or P1.

- `crm_client_account_safe_summary`
- `crm_client_credential_status`
- `crm_delete_user`
- `crm_list_users`
- `crm_load_state_v3`
- `crm_login_v3`
- `crm_logout`
- `crm_public_status`
- `crm_reveal_client_secret_value_v5`
- `crm_save_state`
- `crm_unlock_credentials_v1`
- `crm_upsert_user`

`authenticated` remains denied for these functions; `service_role` remains executable.

## Migration-history gap

The live Supabase migration ledger starts on 2026-08-13, while the current repository does not contain the original SQL files for eleven 2026-08-13/14 migrations. Their names and exact remote ledger versions are preserved in `P0_MIGRATION_LEDGER.md`.

Do not fabricate reconstructed files and present them as original migrations. Recovery is based on the verified current schema/security inventory plus the genuine repository migrations that do exist.

## P1 invariants

Cloudflare Pages Preview must initially change only the hosting/build location.

P1 must keep:

- `sh build.sh`
- output directory `dist`
- all current build/security gates
- current Supabase project and data
- current HttpOnly session design
- current `/api/crm` behavior on Vercel until Worker migration begins
- current Vault storage and reveal semantics
- current production Vercel deployment available for rollback

P1 must not revoke RPCs, alter database schema, split APIs, tighten CSP, or cut the production domain.

## Rollback checkpoint

Until Cloudflare Production cutover is explicitly accepted, Vercel remains the recovery origin.

If a Cloudflare Preview or later Cloudflare route is faulty:

1. Remove/disable the Cloudflare route or DNS path carrying CRM traffic.
2. Route the CRM hostname back to the frozen Vercel production origin/alias.
3. Do not restore or mutate Supabase merely to roll back hosting; P0/P1 make no database changes.
4. Verify homepage load, login/session restore, state load/save, account summary, credential unlock/reveal, and logout.
5. Confirm Vault values were never moved or copied into Cloudflare ordinary storage.

See `ROLLBACK.md` for the phase-by-phase rollback procedure.
