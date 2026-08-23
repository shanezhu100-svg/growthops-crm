-- Post-P5: keep RLS enabled when a crm_* table enters public through ALTER TABLE.
-- Existing ensure_rls already covers CREATE TABLE / CREATE TABLE AS / SELECT INTO.
-- This guard closes the ALTER/rename/SET SCHEMA gap without changing global defaults.

create or replace function public.growthops_crm_rls_guard_ddl()
returns event_trigger
language plpgsql
security definer
set search_path to 'pg_catalog'
as $guard$
declare
  cmd record;
  v_name text;
  v_rls boolean;
begin
  for cmd in
    select * from pg_event_trigger_ddl_commands()
    where schema_name='public'
      and object_type in ('table','partitioned table')
  loop
    select c.relname,c.relrowsecurity
      into v_name,v_rls
    from pg_class c
    where c.oid=cmd.objid;

    if coalesce(v_name,'') like 'crm\_%' escape '\'
       and not coalesce(v_rls,false) then
      execute format('alter table %s enable row level security',cmd.object_identity);
    end if;
  end loop;
end;
$guard$;

revoke execute on function public.growthops_crm_rls_guard_ddl()
from public, anon, authenticated, service_role;

drop event trigger if exists growthops_crm_rls_guard_ddl;
create event trigger growthops_crm_rls_guard_ddl
on ddl_command_end
when tag in ('ALTER TABLE')
execute function public.growthops_crm_rls_guard_ddl();
