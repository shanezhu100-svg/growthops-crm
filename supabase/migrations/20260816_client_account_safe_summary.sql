-- Safe account-asset summary for authenticated ADMIN/OPS users.
-- Returns login identifiers plus boolean credential-presence flags only.
-- Password / 2FA values are never returned by this RPC.

create or replace function public.crm_client_account_safe_summary(p_token text, p_client_id text)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  c record;
  v_tree jsonb;
  v_client jsonb := '{}'::jsonb;
  v_google jsonb := '[]'::jsonb;
  v_instagram jsonb := '[]'::jsonb;
  v_fb_has_extra_secret boolean := false;
  v_tk_has_extra_secret boolean := false;
begin
  select * into c from public.crm_session_context(p_token);
  if c.role not in ('ADMIN','OPS') then
    raise exception 'FORBIDDEN' using errcode='P0001';
  end if;

  v_tree := public.crm_read_workspace_secrets(c.workspace_id);

  select e.value into v_client
  from jsonb_array_elements(coalesce(v_tree->'clients','[]'::jsonb)) e(value)
  where jsonb_typeof(e.value)='object'
    and e.value->>'id'=coalesce(p_client_id,'')
  limit 1;

  if v_client is null then
    v_client := '{}'::jsonb;
  end if;

  v_fb_has_extra_secret := public.crm_secret_tree_nonempty(
    public.crm_extract_secrets(coalesce(v_client->'fbAccounts','[]'::jsonb))
  );
  v_tk_has_extra_secret := public.crm_secret_tree_nonempty(
    public.crm_extract_secrets(coalesce(v_client->'tkAccounts','[]'::jsonb))
  );

  select coalesce(jsonb_agg(
    jsonb_build_object(
      'id',coalesce(e.value->>'id',''),
      'loginAccount',coalesce(e.value->>'loginAccount',''),
      'hasPassword',public.crm_secret_value_nonempty(e.value->'loginPassword'),
      'has2FA',public.crm_secret_tree_nonempty(
        (((((public.crm_extract_secrets(e.value) - 'id') - 'loginAccount') - 'login_account') - 'loginPassword') - 'login_password')
      )
    ) order by e.ord
  ),'[]'::jsonb)
  into v_google
  from jsonb_array_elements(coalesce(v_client->'googleAccounts','[]'::jsonb)) with ordinality e(value,ord)
  where jsonb_typeof(e.value)='object';

  select coalesce(jsonb_agg(
    jsonb_build_object(
      'id',coalesce(e.value->>'id',''),
      'loginAccount',coalesce(e.value->>'loginAccount',''),
      'hasPassword',public.crm_secret_value_nonempty(e.value->'loginPassword'),
      'has2FA',public.crm_secret_tree_nonempty(
        (((((public.crm_extract_secrets(e.value) - 'id') - 'loginAccount') - 'login_account') - 'loginPassword') - 'login_password')
      )
    ) order by e.ord
  ),'[]'::jsonb)
  into v_instagram
  from jsonb_array_elements(coalesce(v_client->'instagramAccounts','[]'::jsonb)) with ordinality e(value,ord)
  where jsonb_typeof(e.value)='object';

  return jsonb_build_object(
    'clientId',coalesce(p_client_id,''),
    'facebook',jsonb_build_object(
      'loginAccount',coalesce(v_client->>'fbLoginAccount',''),
      'hasPassword',public.crm_secret_value_nonempty(v_client->'fbLoginPassword'),
      'has2FA',v_fb_has_extra_secret
    ),
    'tiktok',jsonb_build_object(
      'loginAccount',coalesce(v_client->>'tkLoginAccount',''),
      'hasPassword',public.crm_secret_value_nonempty(v_client->'tkLoginPassword'),
      'has2FA',v_tk_has_extra_secret
    ),
    'googleAccounts',v_google,
    'instagramAccounts',v_instagram
  );
end
$$;

revoke all on function public.crm_client_account_safe_summary(text,text) from public;
grant execute on function public.crm_client_account_safe_summary(text,text) to anon, authenticated, service_role;

comment on function public.crm_client_account_safe_summary(text,text) is
  'Authenticated ADMIN/OPS account-asset view: returns login identifiers and credential-presence booleans only; never password or 2FA values.';
