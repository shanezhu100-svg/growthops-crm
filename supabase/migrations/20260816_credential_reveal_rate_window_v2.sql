-- Rate-limit v2: only count credential reveal events produced by this limiter version.
-- Older Preview/testing reveal audit rows must not throttle the first reveal after rollout.

create or replace function public.crm_reveal_client_secrets(p_token text, p_client_id text)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions, pg_catalog
as $$
declare
  c record;
  v_tree jsonb;
  v_client jsonb := '{}'::jsonb;
  v_session_created timestamptz;
  v_recent_5m integer := 0;
  v_recent_1h integer := 0;
  v_limit_version text := 'v2';
begin
  select * into c from public.crm_session_context(p_token);
  if c.role <> 'ADMIN' then
    raise exception 'FORBIDDEN' using errcode='P0001';
  end if;

  select s.created_at
    into v_session_created
  from public.crm_sessions s
  where s.token_hash = public.crm_token_hash(p_token)
    and s.user_id = c.user_id
    and s.workspace_id = c.workspace_id
    and s.expires_at > now()
  limit 1;

  if v_session_created is null or v_session_created < now() - interval '12 hours' then
    if not exists (
      select 1
      from public.crm_server_audit_logs l
      where l.user_id = c.user_id
        and l.workspace_id = c.workspace_id
        and l.action = 'REVEAL_CLIENT_SECRETS_REAUTH_REQUIRED'
        and l.detail->>'rateLimitVersion' = v_limit_version
        and l.created_at >= now() - interval '1 minute'
    ) then
      insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
      values(
        c.workspace_id,
        c.user_id,
        'REVEAL_CLIENT_SECRETS_REAUTH_REQUIRED',
        jsonb_build_object(
          'clientId',coalesce(p_client_id,''),
          'reason','SESSION_NOT_FRESH',
          'rateLimitVersion',v_limit_version
        )
      );
    end if;
    raise exception 'CREDENTIAL_REAUTH_REQUIRED' using errcode='P0001';
  end if;

  select count(*) into v_recent_5m
  from public.crm_server_audit_logs l
  where l.workspace_id = c.workspace_id
    and l.user_id = c.user_id
    and l.action = 'REVEAL_CLIENT_SECRETS'
    and l.detail->>'rateLimitVersion' = v_limit_version
    and l.created_at >= now() - interval '5 minutes';

  select count(*) into v_recent_1h
  from public.crm_server_audit_logs l
  where l.workspace_id = c.workspace_id
    and l.user_id = c.user_id
    and l.action = 'REVEAL_CLIENT_SECRETS'
    and l.detail->>'rateLimitVersion' = v_limit_version
    and l.created_at >= now() - interval '1 hour';

  if v_recent_5m >= 5 or v_recent_1h >= 20 then
    if not exists (
      select 1
      from public.crm_server_audit_logs l
      where l.user_id = c.user_id
        and l.workspace_id = c.workspace_id
        and l.action = 'REVEAL_CLIENT_SECRETS_THROTTLED'
        and l.detail->>'rateLimitVersion' = v_limit_version
        and l.created_at >= now() - interval '1 minute'
    ) then
      insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
      values(
        c.workspace_id,
        c.user_id,
        'REVEAL_CLIENT_SECRETS_THROTTLED',
        jsonb_build_object(
          'clientId',coalesce(p_client_id,''),
          'window5m',v_recent_5m,
          'window1h',v_recent_1h,
          'rateLimitVersion',v_limit_version
        )
      );
    end if;
    raise exception 'CREDENTIAL_REVEAL_THROTTLED' using errcode='P0001';
  end if;

  v_tree := public.crm_read_workspace_secrets(c.workspace_id);

  select e.value into v_client
  from jsonb_array_elements(coalesce(v_tree->'clients','[]'::jsonb)) e(value)
  where jsonb_typeof(e.value)='object'
    and e.value->>'id'=coalesce(p_client_id,'')
  limit 1;

  insert into public.crm_server_audit_logs(workspace_id,user_id,action,detail)
  values(
    c.workspace_id,
    c.user_id,
    'REVEAL_CLIENT_SECRETS',
    jsonb_build_object(
      'clientId',coalesce(p_client_id,''),
      'rateLimitVersion',v_limit_version
    )
  );

  return coalesce(v_client,'{}'::jsonb);
end
$$;

revoke all on function public.crm_reveal_client_secrets(text,text) from public;
grant execute on function public.crm_reveal_client_secrets(text,text) to anon, authenticated, service_role;
