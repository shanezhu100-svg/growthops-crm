-- Cover foreign keys reported by Supabase performance advisor.

create index if not exists crm_credential_unlocks_user_idx
  on public.crm_credential_unlocks(user_id);
create index if not exists crm_credential_unlocks_workspace_idx
  on public.crm_credential_unlocks(workspace_id);
create index if not exists crm_sessions_workspace_idx
  on public.crm_sessions(workspace_id);
create index if not exists crm_workspace_members_user_idx
  on public.crm_workspace_members(user_id);
create index if not exists crm_workspace_secret_vault_updated_by_idx
  on public.crm_workspace_secret_vault(updated_by);
create index if not exists crm_workspace_state_updated_by_idx
  on public.crm_workspace_state(updated_by);
