-- Roll back only the internal composition change. Post-P5 ACLs remain closed.
create or replace function public.crm_reveal_client_secret_value_v5(
  p_token text,
  p_unlock_token text,
  p_client_id text,
  p_platform text,
  p_account_id text default null,
  p_field text default null
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
  v_field text := lower(btrim(coalesce(p_field,'')));
  v_bundle jsonb := '{}'::jsonb;
  v_value text;
begin
  select * into c from public.crm_session_context(p_token);
  if c.role <> 'ADMIN' then
    raise exception 'FORBIDDEN' using errcode='P0001';
  end if;

  if v_field not in ('password','twofa') then
    raise exception 'INVALID_CREDENTIAL_FIELD' using errcode='P0001';
  end if;

  if not exists (
    select 1
    from public.crm_credential_unlocks u
    where u.unlock_hash = v_unlock_hash
      and u.session_token_hash = v_session_hash
      and u.user_id = c.user_id
      and u.workspace_id = c.workspace_id
      and u.expires_at > now()
  ) then
    raise exception 'CREDENTIAL_UNLOCK_REQUIRED' using errcode='P0001';
  end if;

  v_bundle := public.crm_reveal_client_secret_field_v3(
    p_token,
    p_client_id,
    p_platform,
    p_account_id
  );

  if v_field = 'password' then
    v_value := public.crm_secret_value_text_v5(v_bundle->'accountSecrets','password');
    if coalesce(btrim(v_value),'') = ''
       and public.crm_secret_value_nonempty(v_bundle->'loginPassword') then
      v_value := v_bundle->>'loginPassword';
    end if;
  else
    v_value := public.crm_secret_value_text_v5(v_bundle->'accountSecrets','twofa');
  end if;

  v_bundle := '{}'::jsonb;
  if coalesce(btrim(v_value),'') = '' then
    return '{}'::jsonb;
  end if;
  return jsonb_build_object('value', v_value);
end
$$;

revoke all on function public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text)
  from public, anon, authenticated;
grant execute on function public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text)
  to service_role;

comment on function public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text) is
  'ADMIN + session-bound unlock credential reveal. Returns only {value} for one requested password/twofa field; broader v3/v4 bundles are server-only.';
