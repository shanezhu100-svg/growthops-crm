-- Read-only verification for the post-P5 residual audit sequence ACL hardening.
select
  c.relname as sequence_name,
  has_sequence_privilege('public',c.oid,'SELECT') as public_select,
  has_sequence_privilege('public',c.oid,'UPDATE') as public_update,
  has_sequence_privilege('public',c.oid,'USAGE') as public_usage,
  has_sequence_privilege('anon',c.oid,'SELECT') as anon_select,
  has_sequence_privilege('anon',c.oid,'UPDATE') as anon_update,
  has_sequence_privilege('anon',c.oid,'USAGE') as anon_usage,
  has_sequence_privilege('authenticated',c.oid,'SELECT') as authenticated_select,
  has_sequence_privilege('authenticated',c.oid,'UPDATE') as authenticated_update,
  has_sequence_privilege('authenticated',c.oid,'USAGE') as authenticated_usage,
  has_sequence_privilege('service_role',c.oid,'SELECT') as service_select,
  has_sequence_privilege('service_role',c.oid,'UPDATE') as service_update,
  has_sequence_privilege('service_role',c.oid,'USAGE') as service_usage,
  pg_get_userbyid(c.relowner) as owner,
  (select count(*) from pg_class c2 join pg_namespace n2 on n2.oid=c2.relnamespace
    where n2.nspname='public' and c2.relkind='S' and c2.relname like 'crm_%')::int as total_crm_sequences
from pg_class c
join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public'
  and c.relkind='S'
  and c.relname='crm_server_audit_logs_id_seq';
