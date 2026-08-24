-- Repository mirror of Production migration 20260824031539
-- post_p5_single_workspace_membership_invariant.
--
-- The current CRM product has no workspace-switch or existing-user membership
-- assignment RPC. User identity fields (enabled/name/username/password) are
-- global, and login selects a single membership. Make that application invariant
-- explicit at the database layer so future/manual writes cannot create a state in
-- which one workspace admin action affects another workspace through one user.

DO $preflight$
BEGIN
  IF EXISTS (
    SELECT 1 FROM public.crm_workspace_members
    GROUP BY user_id HAVING count(*) > 1
  ) THEN
    RAISE EXCEPTION 'SINGLE_WORKSPACE_MEMBERSHIP_PREFLIGHT_DUPLICATES';
  END IF;
  IF EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid=c.conrelid
    JOIN pg_namespace n ON n.oid=t.relnamespace
    WHERE n.nspname='public'
      AND t.relname='crm_workspace_members'
      AND c.conname='crm_workspace_members_user_id_key'
  ) THEN
    RAISE EXCEPTION 'SINGLE_WORKSPACE_MEMBERSHIP_PREFLIGHT_ALREADY_APPLIED';
  END IF;
END;
$preflight$;

ALTER TABLE public.crm_workspace_members
  ADD CONSTRAINT crm_workspace_members_user_id_key UNIQUE (user_id);

DO $postcheck$
DECLARE
  v_def text;
BEGIN
  SELECT pg_get_constraintdef(c.oid)
    INTO v_def
  FROM pg_constraint c
  JOIN pg_class t ON t.oid=c.conrelid
  JOIN pg_namespace n ON n.oid=t.relnamespace
  WHERE n.nspname='public'
    AND t.relname='crm_workspace_members'
    AND c.conname='crm_workspace_members_user_id_key';

  IF v_def IS DISTINCT FROM 'UNIQUE (user_id)' THEN
    RAISE EXCEPTION 'SINGLE_WORKSPACE_MEMBERSHIP_POSTCHECK_CONSTRAINT:%', v_def;
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.crm_workspace_members
    GROUP BY user_id HAVING count(*) > 1
  ) THEN
    RAISE EXCEPTION 'SINGLE_WORKSPACE_MEMBERSHIP_POSTCHECK_DUPLICATES';
  END IF;
END;
$postcheck$;
