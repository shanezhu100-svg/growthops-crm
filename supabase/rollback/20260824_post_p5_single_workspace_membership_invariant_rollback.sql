-- Emergency rollback for 20260824031539
-- post_p5_single_workspace_membership_invariant.
-- WARNING: dropping this constraint re-allows a user to belong to multiple
-- workspaces while current user-management semantics remain global.

DO $preflight$
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
    RAISE EXCEPTION 'SINGLE_WORKSPACE_MEMBERSHIP_ROLLBACK_PREFLIGHT:%', v_def;
  END IF;
END;
$preflight$;

ALTER TABLE public.crm_workspace_members
  DROP CONSTRAINT crm_workspace_members_user_id_key;

DO $postcheck$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid=c.conrelid
    JOIN pg_namespace n ON n.oid=t.relnamespace
    WHERE n.nspname='public'
      AND t.relname='crm_workspace_members'
      AND c.conname='crm_workspace_members_user_id_key'
  ) THEN
    RAISE EXCEPTION 'SINGLE_WORKSPACE_MEMBERSHIP_ROLLBACK_POSTCHECK_CONSTRAINT';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.crm_workspace_members
    GROUP BY user_id HAVING count(*) > 1
  ) THEN
    RAISE EXCEPTION 'SINGLE_WORKSPACE_MEMBERSHIP_ROLLBACK_POSTCHECK_DUPLICATES';
  END IF;
END;
$postcheck$;
