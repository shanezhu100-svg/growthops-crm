-- Credential unlock v4: require a recent admin password verification before
-- per-field Vault reveal. The main CRM session lifetime is unchanged.
-- Unlock tokens are random, stored only as hashes, tied to the current CRM session,
-- expire after 10 minutes, and are never written into audit details.

create table if not exists public.crm_credential_unlocks (
  unlock_hash text primary key,
  session_token_hash text not null,
  user_id uuid not null references public.crm_users(id) on delete cascade,
  workspace_id uuid not null references public.crm_workspaces(id) on delete cascade,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);

create index if not exists crm_credential_unlocks_session_idx
  on public.crm_credential_unlocks(session_token_hash, user_id, workspace_id, expires_at desc);

alter table public.crm_credential_unlocks enable row level security;
revoke all on table public.crm_credential_unlocks from public, anon, authenticated;
grant select, insert, update, delete on table public.crm_credential_unlocks to service_role;

create index if not exists crm_server_audit_logs_unlock_user_created_idx
  on public.crm_server_audit_logs(user_id, created_at desc)
  where action in ('CREDENTIAL_UNLOCK','CREDENTIAL_UNLOCK_FAILURE','CREDENTIAL_UNLOCK_THROTTLED');

create or replace function public.crm_unlock_credentials_v1(
  p_token text,
  p_password text
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_catalog
as $$
declare
  c record;
  v_user public.crm_users%rowtype;
  v_session_hash text := public.crm_token_hash(p_token);
  v_unlock_token text;
  v_unlock_hash text;
  v_expires_at timestamptz;
  v_recent_failures integer := 0;
begin
  select * into c from public.crm_session_context(p_token);
  if c.role <> 'ADMIN' then
    raise exception 'FORBIDDEN' using errcode='P0001';
  end if;

  select * into v_user
  from public.crm_users u
  where u.id=c.user_id and u.enabled
  limit 1;

  if v_user.id is null then
    raise exception 'FORBIDDEN' using errcode='P0001';
  end if;

  select count(*) into v_recent_failures
  from public.crm_server_audit_logs l
  where l.workspace_id=c.workspace_id
    and l.user_id=c.user_id
    and l.action='CREDENTIAL_UNLOCK_FAILURE'
    and l.created_at >= now() - interval '10 minutes';

  if v_recent_failures >= 5 then
    if not exists (
      select 1 from public.crm_server_audit_logs l
      where l.workspace_id=c.workspace_id
        and l.user_id=c.user_id
        and l.action='CREDENTIAL_UNLOCK_THROTTLED'
        and l.created_at >= now() - interval '1 minute'
    ) then
      insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
      values(c.workspace_id,c.user_id,'CREDENTIAL_UNLOCK_THROTTLED',jsonb_build_object('reason','TOO_MANY_FAILURES'));
    end if;
    raise exception 'CREDENTIAL_UNLOCK_THROTTLED' using errcode='P0001';
  end if;

  if v_user.password_hash <> extensions.crypt(coalesce(p_password,''),v_user.password_hash) then
    insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
    values(c.workspace_id,c.user_id,'CREDENTIAL_UNLOCK_FAILURE',jsonb_build_object('reason','INVALID_PASSWORD'));
    raise exception 'CREDENTIAL_UNLOCK_INVALID' using errcode='P0001';
  end if;

  delete from public.crm_credential_unlocks
  where expires_at <= now()
     or (session_token_hash=v_session_hash and user_id=c.user_id and workspace_id=c.workspace_id);

  v_unlock_token := encode(extensions.gen_random_bytes(32),'hex');
  v_unlock_hash := public.crm_token_hash(v_unlock_token);
  v_expires_at := now() + interval '10 minutes';

  insert into public.crm_credential_unlocks(
    unlock_hash,session_token_hash,user_id,workspace_id,expires_at
  ) values(
    v_unlock_hash,v_session_hash,c.user_id,c.workspace_id,v_expires_at
  );

  insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
  values(c.workspace_id,c.user_id,'CREDENTIAL_UNLOCK',jsonb_build_object('expiresInSeconds',600));

  return jsonb_build_object(
    'unlockToken',v_unlock_token,
    'expiresAt',v_expires_at
  );
end
$$;

create or replace function public.crm_reveal_client_secret_field_v4(
  p_token text,
  p_unlock_token text,
  p_client_id text,
  p_platform text,
  p_account_id text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  c record;
  v_session_hash text := public.crm_token_hash(p_token);
  v_unlock_hash text := public.crm_token_hash(p_unlock_token);
begin
  select * into c from public.crm_session_context(p_token);
  if c.role <> 'ADMIN' then
    raise exception 'FORBIDDEN' using errcode='P0001';
  end if;

  if not exists (
    select 1
    from public.crm_credential_unlocks u
    where u.unlock_hash=v_unlock_hash
      and u.session_token_hash=v_session_hash
      and u.user_id=c.user_id
      and u.workspace_id=c.workspace_id
      and u.expires_at > now()
  ) then
    raise exception 'CREDENTIAL_UNLOCK_REQUIRED' using errcode='P0001';
  end if;

  return public.crm_reveal_client_secret_field_v3(
    p_token,
    p_client_id,
    p_platform,
    p_account_id
  );
end
$$;

revoke all on function public.crm_unlock_credentials_v1(text,text) from public;
grant execute on function public.crm_unlock_credentials_v1(text,text) to anon, authenticated, service_role;

revoke all on function public.crm_reveal_client_secret_field_v4(text,text,text,text,text) from public;
grant execute on function public.crm_reveal_client_secret_field_v4(text,text,text,text,text) to anon, authenticated, service_role;

-- v3 remains callable only by privileged server-side code once v4 is available.
revoke execute on function public.crm_reveal_client_secret_field_v3(text,text,text,text) from anon, authenticated, public;
grant execute on function public.crm_reveal_client_secret_field_v3(text,text,text,text) to service_role;

comment on function public.crm_unlock_credentials_v1(text,text) is
  'ADMIN password re-verification. Returns a session-bound 10-minute in-memory unlock token; password and token values are never audited.';
comment on function public.crm_reveal_client_secret_field_v4(text,text,text,text,text) is
  'ADMIN per-field Vault reveal requiring both the CRM session token and a valid 10-minute credential unlock token.';
