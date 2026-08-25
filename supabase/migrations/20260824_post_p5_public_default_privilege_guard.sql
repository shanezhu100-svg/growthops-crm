-- Post-P5: fail closed for future postgres-created objects in public.
--
-- Existing CRM objects are unchanged. The default-privilege revokes only affect
-- future tables/sequences/functions created by postgres in public, while the
-- event trigger closes PostgreSQL's hard-wired PUBLIC EXECUTE on future
-- non-CRM public functions/procedures without touching extensions/storage/etc.

alter default privileges for role postgres in schema public
  revoke all privileges on tables from service_role;

alter default privileges for role postgres in schema public
  revoke all privileges on sequences from service_role;

alter default privileges for role postgres in schema public
  revoke execute on functions from service_role;

create or replace function public.growthops_public_noncrm_function_acl_guard_ddl()
returns event_trigger
language plpgsql
security definer
set search_path to 'pg_catalog'
as $guard$
declare
  cmd record;
  v_name text;
  v_kind "char";
begin
  for cmd in
    select * from pg_event_trigger_ddl_commands()
    where schema_name = 'public'
  loop
    if cmd.object_type in ('function','procedure') then
      select p.proname, p.prokind
        into v_name, v_kind
      from pg_proc p
      where p.oid = cmd.objid;

      if coalesce(v_name,'') not like 'crm\_%' escape '\' then
        if v_kind = 'p' then
          execute format(
            'revoke execute on procedure %s from public, anon, authenticated, service_role',
            cmd.object_identity
          );
        else
          execute format(
            'revoke execute on function %s from public, anon, authenticated, service_role',
            cmd.object_identity
          );
        end if;
      end if;
    end if;
  end loop;
end;
$guard$;

-- The guard itself is infrastructure, never an RPC.
revoke execute on function public.growthops_public_noncrm_function_acl_guard_ddl()
from public, anon, authenticated, service_role;

drop event trigger if exists growthops_public_noncrm_function_acl_guard_ddl;
create event trigger growthops_public_noncrm_function_acl_guard_ddl
on ddl_command_end
when tag in (
  'CREATE FUNCTION','ALTER FUNCTION',
  'CREATE PROCEDURE','ALTER PROCEDURE'
)
execute function public.growthops_public_noncrm_function_acl_guard_ddl();
