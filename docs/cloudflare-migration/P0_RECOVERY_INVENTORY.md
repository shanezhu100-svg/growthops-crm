# P0 Recovery Inventory

Checkpoint date: 2026-08-21

This inventory defines what must remain true before and after the Cloudflare migration. It is a recovery/acceptance inventory, not a replacement for a full `pg_dump` schema export.

## Data-safety invariants

At the checkpoint:

- Supabase Vault contains `1` secret row.
- `crm_workspace_state` sensitive-key matches: `0`.
- `crm_server_audit_logs` sensitive payload-value matches: `0`.
- A boolean audit marker such as `passwordChanged` is allowed; secret payload values are not.
- Customer credential truth remains in Supabase Vault.
- Ordinary CRM backup/state data must not become a credential store.

## Database access invariants

Observed before migration:

- CRM business tables have RLS enabled.
- No RLS policies are present on the `crm_*` business tables.
- Therefore direct table access remains default-deny and controlled RPCs/functions form the application access path.
- `authenticated` is not the CRM application execution role for the browser-facing RPC set.
- Existing `anon` RPC grants are transitional and must remain until Cloudflare Worker privileged access is proven in Preview.
- Old full/v3/v4 credential reveal functions must remain unavailable to browser roles.
- v5 reveal must return only the requested credential field, never a client credential tree.

## Session/security invariants

The database must retain:

- maximum CRM session lifetime of 7 days;
- maximum 4 active sessions per user;
- old-session revocation behavior on identity/password security changes;
- credential unlock revocation on relevant user/membership security changes;
- workspace-state secret guard;
- credential reveal audit/rate-limit enforcement.

## Application invariants

The built browser application must retain:

- no CRM bearer token in `localStorage`;
- no direct Supabase `/rest/v1/rpc/` browser calls;
- same-origin API transport;
- `HttpOnly + Secure + SameSite=Strict` session cookie behavior;
- server-side session token injection;
- browser-facing reveal limited to `crm_reveal_client_secret_value_v5`;
- approximately 10-second credential display lifetime;
- credential/unlock clearing when the document is hidden;
- current “all clients”, client-detail return, account assets, and independent scroll-state behavior.

## Revalidation

Run `supabase/baseline/p0_recovery_inventory.sql` against the target Supabase project and compare results with `P0_BASELINE.md` before:

1. first Cloudflare Pages Preview;
2. first Worker API Preview;
3. first anon RPC privilege revocation;
4. Cloudflare Production cutover;
5. any rollback that includes database changes.

The inventory SQL is read-only and must not mutate production data.

## Full schema snapshot requirement

The current repository now records the live migration ledger gap and a repeatable security inventory, but a real full schema export is still a P0 recovery deliverable. When a trusted `pg_dump`/Supabase schema export is obtained, store it as a clearly dated snapshot or an approved external backup artifact. Do not attempt to recreate missing 2026-08-13/14 migration SQL by guessing from the current schema.

## Acceptance rule

A migration phase is not accepted if any of the following occurs unexpectedly:

- Vault count changes because of hosting migration;
- workspace sensitive-key count becomes nonzero;
- audit sensitive payload-value count becomes nonzero;
- browser-readable CRM token storage reappears;
- browser direct Supabase RPC transport reappears;
- old full/v3/v4 credential reveal becomes browser-executable;
- session lifetime or active-session cap weakens;
- Cloudflare ordinary storage receives customer password/2FA values.
