create or replace function public.crm_revoke_unlocks_on_user_security_change()
returns trigger
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
begin
  if old.password_hash is distinct from new.password_hash
     or old.enabled is distinct from new.enabled then
    delete from public.crm_credential_unlocks where user_id=new.id;
  end if;
  return new;
end
$$;

revoke all on function public.crm_revoke_unlocks_on_user_security_change() from public, anon, authenticated;

DROP TRIGGER IF EXISTS crm_revoke_unlocks_on_user_security_change_trg ON public.crm_users;
create trigger crm_revoke_unlocks_on_user_security_change_trg
after update of password_hash, enabled on public.crm_users
for each row execute function public.crm_revoke_unlocks_on_user_security_change();

create or replace function public.crm_revoke_unlocks_on_membership_security_change()
returns trigger
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
begin
  if old.role is distinct from new.role
     or old.enabled is distinct from new.enabled then
    delete from public.crm_credential_unlocks
     where user_id=new.user_id and workspace_id=new.workspace_id;
  end if;
  return new;
end
$$;

revoke all on function public.crm_revoke_unlocks_on_membership_security_change() from public, anon, authenticated;

DROP TRIGGER IF EXISTS crm_revoke_unlocks_on_membership_security_change_trg ON public.crm_workspace_members;
create trigger crm_revoke_unlocks_on_membership_security_change_trg
after update of role, enabled on public.crm_workspace_members
for each row execute function public.crm_revoke_unlocks_on_membership_security_change();

comment on function public.crm_revoke_unlocks_on_user_security_change() is
  'Revokes all temporary credential unlocks immediately when a user password or enabled state changes.';
comment on function public.crm_revoke_unlocks_on_membership_security_change() is
  'Revokes workspace credential unlocks immediately when a member role or enabled state changes.';
