-- Credential reveal v5: least-privilege transport for password / 2FA.
--
-- v3 remains the server-side authority for ADMIN checks, fresh-session enforcement,
-- rate limiting, Vault reads and audit metadata. v5 additionally requires the
-- session-bound 10-minute unlock token, then reduces the v3 bundle to exactly one
-- requested secret value before anything crosses the browser boundary.

create or replace function public.crm_secret_value_text_v5(
  p_value jsonb,
  p_field text
)
returns text
language plpgsql
immutable
set search_path = public, pg_catalog
as $$
declare
  v_field text := lower(btrim(coalesce(p_field,'')));
  v_key text;
  v_child jsonb;
  v_target text;
  v_text text;
  v_targets text[];
begin
  if p_value is null then
    return null;
  end if;

  if v_field = 'password' then
    v_targets := array[
      'loginpassword','login_password','fbloginpassword','tkloginpassword',
      'password','passwd','pwd'
    ];
  elsif v_field = 'twofa' then
    v_targets := array[
      'twofactor','two_factor','twofactorsecret','two_factor_secret',
      'twofakey','two_fa_key','2fa','2fakey','2fa_key',
      'totpsecret','totp_secret','secretkey','secret_key',
      'backupcodes','backup_codes','recoverycodes','recovery_codes'
    ];
  else
    return null;
  end if;

  if jsonb_typeof(p_value) = 'object' then
    -- Prefer an exact secret key at the current object level before recursing.
    foreach v_target in array v_targets loop
      select e.key, e.value
        into v_key, v_child
      from jsonb_each(p_value) e(key,value)
      where lower(e.key) = v_target
      limit 1;

      if found and public.crm_secret_value_nonempty(v_child) then
        if jsonb_typeof(v_child) = 'string' then
          return v_child #>> '{}';
        elsif jsonb_typeof(v_child) = 'array' then
          select string_agg(
                   case
                     when jsonb_typeof(a.value) = 'string' then a.value #>> '{}'
                     else a.value::text
                   end,
                   E'\n'
                 )
            into v_text
          from jsonb_array_elements(v_child) a(value)
          where public.crm_secret_value_nonempty(a.value);
          if coalesce(btrim(v_text),'') <> '' then
            return v_text;
          end if;
        else
          return v_child::text;
        end if;
      end if;
    end loop;

    for v_key, v_child in select * from jsonb_each(p_value) loop
      if lower(coalesce(v_key,'')) = 'id' then
        continue;
      end if;
      v_text := public.crm_secret_value_text_v5(v_child, v_field);
      if coalesce(btrim(v_text),'') <> '' then
        return v_text;
      end if;
    end loop;
    return null;
  end if;

  if jsonb_typeof(p_value) = 'array' then
    for v_child in select value from jsonb_array_elements(p_value) loop
      v_text := public.crm_secret_value_text_v5(v_child, v_field);
      if coalesce(btrim(v_text),'') <> '' then
        return v_text;
      end if;
    end loop;
  end if;

  return null;
end
$$;

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

  -- v3 is intentionally server-only. It retains the existing fresh-session,
  -- rate-limit and audit controls; its broader bundle never leaves this function.
  v_bundle := public.crm_reveal_client_secret_field_v3(
    p_token,
    p_client_id,
    p_platform,
    p_account_id
  );

  if v_field = 'password' then
    -- Prefer a password on the selected account. Fall back to the platform-level
    -- login password only when that account does not contain its own password.
    v_value := public.crm_secret_value_text_v5(v_bundle->'accountSecrets','password');
    if coalesce(btrim(v_value),'') = ''
       and public.crm_secret_value_nonempty(v_bundle->'loginPassword') then
      v_value := v_bundle->>'loginPassword';
    end if;
  else
    v_value := public.crm_secret_value_text_v5(v_bundle->'accountSecrets','twofa');
  end if;

  -- Drop the bundle before returning. Browser-visible output is either {} or one
  -- scalar field only; accountSecrets / loginPassword can never be serialized out.
  v_bundle := '{}'::jsonb;
  if coalesce(btrim(v_value),'') = '' then
    return '{}'::jsonb;
  end if;
  return jsonb_build_object('value', v_value);
end
$$;

revoke all on function public.crm_secret_value_text_v5(jsonb,text) from public, anon, authenticated;
grant execute on function public.crm_secret_value_text_v5(jsonb,text) to service_role;

revoke all on function public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text) from public, anon, authenticated;
grant execute on function public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text) to anon, service_role;

-- Retire broader browser reveal surfaces. They remain available only to privileged
-- server-side code for compatibility/internal composition.
revoke execute on function public.crm_reveal_client_secret_field_v4(text,text,text,text,text) from public, anon, authenticated;
grant execute on function public.crm_reveal_client_secret_field_v4(text,text,text,text,text) to service_role;
revoke execute on function public.crm_reveal_client_secret_field_v3(text,text,text,text) from public, anon, authenticated;
grant execute on function public.crm_reveal_client_secret_field_v3(text,text,text,text) to service_role;

comment on function public.crm_reveal_client_secret_value_v5(text,text,text,text,text,text) is
  'ADMIN + session-bound unlock credential reveal. Returns only {value} for one requested password/twofa field; broader v3/v4 bundles are server-only.';
