-- Expose only credential-presence metadata for account asset cards.
-- Real login/password/2FA values remain in Vault and are never returned by this RPC.

create or replace function public.crm_client_credential_status(p_token text, p_client_id text)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_catalog
as $$
declare
  c record;
  v_tree jsonb;
  v_client jsonb := '{}'::jsonb;
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

  return jsonb_build_object(
    'clientId',coalesce(p_client_id,''),
    'facebook',jsonb_build_object(
      'hasLoginAccount',public.crm_secret_value_nonempty(v_client->'fbLoginAccount'),
      'hasPassword',public.crm_secret_value_nonempty(v_client->'fbLoginPassword'),
      'has2FA',v_fb_has_extra_secret
    ),
    'tiktok',jsonb_build_object(
      'hasLoginAccount',public.crm_secret_value_nonempty(v_client->'tkLoginAccount'),
      'hasPassword',public.crm_secret_value_nonempty(v_client->'tkLoginPassword'),
      'has2FA',v_tk_has_extra_secret
    )
  );
end
$$;

revoke all on function public.crm_client_credential_status(text,text) from public;
grant execute on function public.crm_client_credential_status(text,text) to anon, authenticated, service_role;
