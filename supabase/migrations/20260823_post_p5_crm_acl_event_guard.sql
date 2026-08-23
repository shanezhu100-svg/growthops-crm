-- Post-P5: fail-closed ACL guard for future public.crm_* DDL.
--
-- Scope is deliberately prefix-specific. We do NOT alter PostgreSQL global
-- default privileges because that would affect non-CRM schemas/extension DDL.
-- Instead, ddl_command_end immediately normalizes ACLs for CRM functions,
-- procedures, relations and sequences after CREATE/ALTER operations.

create or replace function public.growthops_crm_acl_guard_ddl()
returns event_trigger
language plpgsql
security definer
set search_path to 'pg_catalog'
as $guard$
declare
  cmd record;
  v_name text;
  v_args text;
  v_allowed boolean;
  v_kind "char";
begin
  for cmd in
    select * from pg_event_trigger_ddl_commands()
    where schema_name = 'public'
  loop
    if cmd.object_type in ('function','procedure') then
      select p.proname, pg_get_function_identity_arguments(p.oid), p.prokind
        into v_name, v_args, v_kind
      from pg_proc p
      where p.oid = cmd.objid;

      if coalesce(v_name,'') like 'crm\_%' escape '\' then
        if v_kind = 'p' then
          -- CRM procedures are not part of the approved PostgREST/BFF surface.
          execute format(
            'revoke execute on procedure %s from public, anon, authenticated, service_role',
            cmd.object_identity
          );
        else
          -- Browser roles never execute CRM functions directly.
          execute format(
            'revoke execute on function %s from public, anon, authenticated',
            cmd.object_identity
          );

          -- Exact service_role allowlist: 11 BFF RPCs + bootstrap_admin.
          v_allowed :=
            (v_name='crm_bootstrap_admin' and v_args='p_setup_code text, p_name text, p_username text, p_password text') or
            (v_name='crm_client_account_safe_summary' and v_args='p_token text, p_client_id text') or
            (v_name='crm_delete_user' and v_args='p_token text, p_user_id uuid') or
            (v_name='crm_list_users' and v_args='p_token text') or
            (v_name='crm_load_state_v3' and v_args='p_token text') or
            (v_name='crm_login_v3' and v_args='p_username text, p_password text') or
            (v_name='crm_logout' and v_args='p_token text') or
            (v_name='crm_public_status' and v_args='') or
            (v_name='crm_reveal_client_secret_value_v5' and v_args='p_token text, p_unlock_token text, p_client_id text, p_platform text, p_account_id text, p_field text') or
            (v_name='crm_save_state' and v_args='p_token text, p_state jsonb, p_expected_revision bigint') or
            (v_name='crm_unlock_credentials_v1' and v_args='p_token text, p_password text') or
            (v_name='crm_upsert_user' and v_args='p_token text, p_user_id uuid, p_name text, p_username text, p_password text, p_role text, p_enabled boolean');

          if v_allowed then
            execute format('grant execute on function %s to service_role', cmd.object_identity);
          else
            execute format('revoke execute on function %s from service_role', cmd.object_identity);
          end if;
        end if;
      end if;

    elsif cmd.object_type in ('table','partitioned table','view','materialized view','foreign table') then
      select c.relname into v_name from pg_class c where c.oid = cmd.objid;
      if coalesce(v_name,'') like 'crm\_%' escape '\' then
        execute format(
          'revoke all privileges on table %s from public, anon, authenticated, service_role',
          cmd.object_identity
        );
      end if;

    elsif cmd.object_type = 'sequence' then
      select c.relname into v_name from pg_class c where c.oid = cmd.objid;
      if coalesce(v_name,'') like 'crm\_%' escape '\' then
        execute format(
          'revoke all privileges on sequence %s from public, anon, authenticated, service_role',
          cmd.object_identity
        );
      end if;
    end if;
  end loop;
end;
$guard$;

-- The event-trigger function itself is infrastructure, not an RPC.
revoke execute on function public.growthops_crm_acl_guard_ddl()
from public, anon, authenticated, service_role;

drop event trigger if exists growthops_crm_acl_guard_ddl;
create event trigger growthops_crm_acl_guard_ddl
on ddl_command_end
when tag in (
  'CREATE FUNCTION','ALTER FUNCTION',
  'CREATE PROCEDURE','ALTER PROCEDURE',
  'CREATE TABLE','ALTER TABLE','CREATE TABLE AS','SELECT INTO',
  'CREATE SEQUENCE','ALTER SEQUENCE',
  'CREATE VIEW','ALTER VIEW',
  'CREATE MATERIALIZED VIEW','ALTER MATERIALIZED VIEW',
  'CREATE FOREIGN TABLE','ALTER FOREIGN TABLE'
)
execute function public.growthops_crm_acl_guard_ddl();
