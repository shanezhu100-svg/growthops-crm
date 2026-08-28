-- Supabase SQL Editor-compatible derivative of p0_cloud_recovery_acceptance.sql.
-- Do not edit the acceptance body independently; canonical Gate enforces equivalence.
-- Run only against the named empty disposable recovery target, never Production.

-- Run only against a disposable isolated Supabase recovery project.
-- This script uses generated synthetic values only and rolls back all test data.

BEGIN;

DO $p0$
DECLARE
  v_setup_code text := repeat(chr(83), 32);
  v_admin_password text := repeat(chr(65), 32);
  v_ops_password text := repeat(chr(79), 32);
  v_client_password text := repeat(chr(67), 32);
  v_account_password text := repeat(chr(80), 32);
  v_twofactor text := repeat(chr(84), 16);
  v_client_id text := 'p0-recovery-client';
  v_account_id text := 'p0-recovery-fb-account';
  v_admin jsonb;
  v_ops jsonb;
  v_ops_login jsonb;
  v_unlock jsonb;
  v_reveal jsonb;
  v_summary jsonb;
  v_load jsonb;
  v_admin_token text;
  v_ops_token text;
  v_unlock_token text;
  v_before_vault bigint;
  v_count bigint;
BEGIN
  IF EXISTS (SELECT 1 FROM public.crm_users)
     OR EXISTS (SELECT 1 FROM public.crm_workspaces) THEN
    RAISE EXCEPTION 'P0_RECOVERY_TARGET_NOT_EMPTY';
  END IF;

  SELECT count(*) INTO v_before_vault FROM vault.secrets;

  INSERT INTO public.crm_setup_guard(id, secret_hash)
  VALUES (true, extensions.crypt(v_setup_code, extensions.gen_salt('bf', 10)));

  v_admin := public.crm_bootstrap_admin(
    v_setup_code,
    'P0 Recovery Admin',
    'p0_recovery_admin',
    v_admin_password
  );
  v_admin_token := v_admin->>'token';

  IF coalesce(length(v_admin_token), 0) < 32 THEN
    RAISE EXCEPTION 'P0_ADMIN_BOOTSTRAP_FAILED';
  END IF;

  SELECT count(*) INTO v_count
  FROM public.crm_sessions
  WHERE expires_at > now() + interval '7 days 1 minute';
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'P0_SESSION_CAP_FAILED';
  END IF;

  v_ops := public.crm_upsert_user(
    v_admin_token,
    NULL,
    'P0 Recovery OPS',
    'p0_recovery_ops',
    v_ops_password,
    'OPS',
    true
  );
  IF coalesce(v_ops->>'role', '') <> 'OPS' THEN
    RAISE EXCEPTION 'P0_OPS_CREATE_FAILED';
  END IF;

  v_ops_login := public.crm_login_v3('p0_recovery_ops', v_ops_password);
  IF coalesce(v_ops_login->>'error', '') <> '' THEN
    RAISE EXCEPTION 'P0_OPS_LOGIN_FAILED';
  END IF;
  v_ops_token := v_ops_login->>'token';

  PERFORM public.crm_save_state(
    v_admin_token,
    jsonb_build_object(
      'clients', jsonb_build_array(
        jsonb_build_object(
          'id', v_client_id,
          'name', 'Synthetic Recovery Client',
          'fbLoginAccount', 'synthetic@example.invalid',
          'fbLoginPassword', v_client_password,
          'fbAccounts', jsonb_build_array(
            jsonb_build_object(
              'id', v_account_id,
              'loginAccount', 'synthetic-account@example.invalid',
              'password', v_account_password,
              'twoFactor', v_twofactor
            )
          )
        )
      )
    ),
    0
  );

  SELECT count(*) INTO v_count FROM vault.secrets;
  IF v_count <> v_before_vault + 1 THEN
    RAISE EXCEPTION 'P0_VAULT_WRITE_FAILED';
  END IF;

  SELECT count(*) INTO v_count
  FROM public.crm_workspace_state
  WHERE data::text LIKE '%' || v_client_password || '%'
     OR data::text LIKE '%' || v_account_password || '%'
     OR data::text LIKE '%' || v_twofactor || '%';
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'P0_SECRET_LEAK_IN_WORKSPACE_STATE';
  END IF;

  v_load := public.crm_load_state_v3(v_admin_token);
  IF v_load::text LIKE '%' || v_client_password || '%'
     OR v_load::text LIKE '%' || v_account_password || '%'
     OR v_load::text LIKE '%' || v_twofactor || '%' THEN
    RAISE EXCEPTION 'P0_SECRET_LEAK_IN_ADMIN_LOAD';
  END IF;

  v_load := public.crm_load_state_v3(v_ops_token);
  IF v_load::text LIKE '%' || v_client_password || '%'
     OR v_load::text LIKE '%' || v_account_password || '%'
     OR v_load::text LIKE '%' || v_twofactor || '%' THEN
    RAISE EXCEPTION 'P0_SECRET_LEAK_IN_OPS_LOAD';
  END IF;

  v_summary := public.crm_client_account_safe_summary(v_ops_token, v_client_id);
  IF coalesce((v_summary->'facebook'->>'hasPassword')::boolean, false) IS NOT TRUE
     OR coalesce((v_summary->'facebook'->>'has2FA')::boolean, false) IS NOT TRUE THEN
    RAISE EXCEPTION 'P0_SAFE_SUMMARY_FAILED';
  END IF;
  IF v_summary::text LIKE '%' || v_client_password || '%'
     OR v_summary::text LIKE '%' || v_account_password || '%'
     OR v_summary::text LIKE '%' || v_twofactor || '%' THEN
    RAISE EXCEPTION 'P0_SAFE_SUMMARY_VALUE_LEAK';
  END IF;

  v_unlock := public.crm_unlock_credentials_v1(v_admin_token, v_admin_password);
  v_unlock_token := v_unlock->>'unlockToken';
  IF coalesce(length(v_unlock_token), 0) < 32 THEN
    RAISE EXCEPTION 'P0_ADMIN_UNLOCK_FAILED';
  END IF;

  v_reveal := public.crm_reveal_client_secret_value_v5(
    v_admin_token, v_unlock_token, v_client_id,
    'facebook', v_account_id, 'password'
  );
  IF coalesce(v_reveal->>'value', '') <> v_account_password THEN
    RAISE EXCEPTION 'P0_ADMIN_PASSWORD_REVEAL_FAILED';
  END IF;

  v_reveal := public.crm_reveal_client_secret_value_v5(
    v_admin_token, v_unlock_token, v_client_id,
    'facebook', v_account_id, 'twofa'
  );
  IF coalesce(v_reveal->>'value', '') <> v_twofactor THEN
    RAISE EXCEPTION 'P0_ADMIN_2FA_REVEAL_FAILED';
  END IF;

  BEGIN
    PERFORM public.crm_unlock_credentials_v1(v_ops_token, v_ops_password);
    RAISE EXCEPTION USING MESSAGE='P0_OPS_UNLOCK_UNEXPECTEDLY_ALLOWED', ERRCODE='ZZ001';
  EXCEPTION WHEN SQLSTATE 'P0001' THEN
    IF SQLERRM <> 'FORBIDDEN' THEN
      RAISE EXCEPTION 'P0_OPS_UNLOCK_WRONG_ERROR:%', SQLERRM;
    END IF;
  END;

  BEGIN
    PERFORM public.crm_reveal_client_secret_value_v5(
      v_ops_token, repeat(chr(48), 64), v_client_id,
      'facebook', v_account_id, 'password'
    );
    RAISE EXCEPTION USING MESSAGE='P0_OPS_REVEAL_UNEXPECTEDLY_ALLOWED', ERRCODE='ZZ002';
  EXCEPTION WHEN SQLSTATE 'P0001' THEN
    IF SQLERRM <> 'FORBIDDEN' THEN
      RAISE EXCEPTION 'P0_OPS_REVEAL_WRONG_ERROR:%', SQLERRM;
    END IF;
  END;

  SELECT count(*) INTO v_count
  FROM public.crm_server_audit_logs
  WHERE detail::text LIKE '%' || v_admin_password || '%'
     OR detail::text LIKE '%' || v_ops_password || '%'
     OR detail::text LIKE '%' || v_client_password || '%'
     OR detail::text LIKE '%' || v_account_password || '%'
     OR detail::text LIKE '%' || v_twofactor || '%';
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'P0_SECRET_LEAK_IN_AUDIT';
  END IF;

  RAISE NOTICE 'P0_CLOUD_RECOVERY_ACCEPTANCE_OK';
END
$p0$;

ROLLBACK;

SELECT 'P0_CLOUD_RECOVERY_ACCEPTANCE_OK'::text AS recovery_acceptance;
