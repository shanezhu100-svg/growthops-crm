#!/bin/sh
set -eu
# This must run before any build/finalizer code so Preview branch code cannot
# silently inherit the production Supabase server identity.
python3 preview_secret_guard.py
# Validate CI/quota policy before any expensive build/finalizer work.
python3 test_ci_quota_guard.py
python3 test_vercel_ignore_build.py
# Keep the full-schema recovery procedure pinned to current Production truth.
python3 test_full_schema_export_recovery.py
# Keep the consolidated remote migration ledger pinned to current Production truth.
python3 test_migration_ledger_recovery.py
python3 verify_final_source.py
python3 runtime_config_compat.py
trap 'rm -f index.html' 0
python3 build_final.py
rm -f index.html
trap - 0
python3 p2_finalize.py
python3 test_p2_output.py
python3 security_finalize.py
python3 backup_security_finalize.py
python3 security_reveal_ui_finalize.py
# Canonical compatibility scaffolding. Legacy status/loading paths are retained
# only as build-time markers and are stripped from the shipped runtime by v6.
python3 credential_template_initial_finalize.py
python3 credential_status_ui_finalize.py
python3 account_asset_client_context_finalize.py
python3 assets_all_clients_finalize.py
python3 credential_status_loading_finalize.py
python3 account_asset_value_typography_finalize.py
python3 test_credential_status_ui_output.py
python3 test_account_asset_client_context_output.py
python3 test_credential_status_loading_output.py
python3 test_account_asset_value_typography_output.py
python3 account_login_identifier_v2_finalize.py
# Generate the final unlock + scalar-value credential reveal controller in one
# build stage. This replaces the historical persisted v3 -> v4 intermediate chain.
python3 credential_secure_reveal_finalize.py
python3 test_security_hotfix_output.py
python3 test_security_reveal_ui_output.py
python3 test_credential_template_initial_output.py
python3 test_account_login_identifier_output.py
python3 test_credential_unlock_v4_output.py
python3 credential_client_detail_v4_finalize.py
python3 test_credential_client_detail_v4_output.py
python3 test_assets_all_clients_output.py
python3 test_workspace_state_secret_hard_guard.py
python3 test_backup_security_output.py
python3 test_preview_secret_guard.py
python3 test_post_p5_v5_direct_scalar.py
python3 test_vercel_security_headers.py
python3 cloudflare_headers_finalize.py
python3 test_static_asset_cache_policy.py
python3 cloudflare_failopen_404_finalize.py
python3 test_cloudflare_failopen_404.py
python3 test_cloudflare_p1_verify_guard.py
node test_cloudflare_function_security_headers.mjs
python3 test_rpc_surface_hardening.py
python3 test_session_security_migrations.py
python3 cloud_save_queue_finalize.py
python3 test_cloud_save_queue_output.py
python3 ui_action_finalize.py
python3 test_ui_action_output.py
python3 remove_login_material_view_finalize.py
python3 test_remove_login_material_view_output.py
# Consolidated credential UI pipeline: controller includes memory-only safe-summary
# prefetch; runtime includes v6 cleanup, atomic placeholder gate, and event liveness.
python3 credential_ui_v5_finalize.py
python3 test_credential_ui_v5_output.py
python3 credential_ui_v6_finalize.py
python3 test_credential_ui_v6_output.py
python3 http_only_session_finalize.py
python3 test_http_only_session_output.py
# The HttpOnly/same-origin migration has removed every browser consumer of the
# legacy publishable Supabase transport globals. Strip those dead globals now.
python3 browser_supabase_config_scrub_finalize.py
python3 test_browser_supabase_config_scrub_output.py
python3 client_detail_return_finalize.py
python3 test_client_detail_return_output.py
python3 module_home_navigation_finalize.py
python3 test_module_home_navigation_output.py
# Final DOM-liveness repair: a reveal marker is valid only when the real per-field
# eye button still exists. This prevents placeholder scrubs from leaving stale
# markers that suppress the v5 scalar reveal control.
python3 credential_eye_self_heal_finalize.py
python3 test_credential_eye_self_heal_output.py
python3 admin_password_byte_cap_finalize.py
python3 test_admin_password_byte_cap_output.py
# Public deployment guidance must describe the actual server-authenticated runtime
# rather than the historical browser-local prototype.
python3 production_auth_copy_finalize.py
python3 test_production_auth_copy_output.py
# Convert browser dependencies to verified same-origin build artifacts.
python3 frontend_dependency_pin_finalize.py
python3 test_tailwind_static_policy.py
python3 tailwind_static_finalize.py
python3 test_frontend_vendor_static_policy.py
python3 frontend_vendor_static_finalize.py
python3 test_fontawesome_static_policy.py
python3 fontawesome_static_finalize.py
python3 test_inter_static_policy.py
python3 inter_static_finalize.py
python3 test_frontend_dependency_pin_output.py
# Prove the final HTML contains no real on*= DOM event attributes before the
# security header authority blocks script attributes explicitly.
python3 test_script_attr_csp_readiness.py
# Move application-owned inline JS into same-origin static files so script-src no
# longer needs unsafe-inline. Keep Vue compiler unsafe-eval as a separate boundary.
python3 test_inline_script_static_policy.py
python3 inline_script_static_finalize.py
python3 test_inline_script_static_output.py
python3 test_vue_runtime_csp_readiness.py
# Externalize static styles, then remove the remaining bound-style/CSSOM sinks so
# style-src-attr can be denied completely.
python3 test_style_csp_readiness.py
python3 test_inline_style_static_policy.py
python3 inline_style_static_finalize.py
python3 test_inline_style_static_output.py
python3 test_style_attr_cssom_policy.py
python3 style_attr_cssom_finalize.py
python3 test_style_attr_cssom_output.py
# Browser liveness is a required deployment invariant. The compiler-inclusive
# Vue asset is self-hosted and SHA-pinned; a real Chromium run must mount #app,
# consume the DOM template, and remove v-cloak before any release can merge.
python3 test_browser_mount_smoke.py
# Business-semantic regression gates execute the final shipped application logic,
# not a copied test implementation.
node test_business_ad_metrics.mjs
# Final server-side identity and input boundaries. Patch the two deployment BFFs
# before syntax/runtime tests so canonical builds and deployed handlers are aligned.
python3 preview_runtime_boundary_finalize.py
python3 production_supabase_origin_pin_finalize.py
python3 unlock_password_input_bounds_finalize.py
python3 user_identity_input_bounds_finalize.py
python3 session_token_input_bounds_finalize.py
python3 upstream_timeout_finalize.py
node test_bff_security_semantic_parity.mjs
node test_upstream_timeout.mjs
node --check api/crm.js
GROWTHOPS_SUPABASE_SECRET_KEY=sb_secret_test_http_only_ci node test_http_only_session_api.js
GROWTHOPS_SUPABASE_SECRET_KEY=sb_secret_test_cache_privacy_ci node test_vercel_cache_privacy.js
node test_cloudflare_p2b_api.mjs
node test_supabase_upstream_origin_guard.mjs
node test_preview_runtime_boundary.mjs
node test_production_supabase_origin_pin.mjs
node test_api_body_limit.mjs
node test_api_request_envelope.mjs
node test_login_input_bounds.mjs
node test_admin_password_input_bounds.mjs
node test_unlock_password_input_bounds.mjs
node test_user_identity_input_bounds.mjs
node test_session_token_input_bounds.mjs
python3 test_server_identity_sink_inventory.py
node test_cloudflare_p3p4_attack_regression.mjs
python3 test_p5_sensitive_rpc_revocation.py
python3 test_p5_group2_legacy_status_candidate.py
python3 test_p5_group2_legacy_status_revocation.py
python3 test_p5_group3_admin_user_mgmt_candidate.py
python3 test_p5_group3_admin_user_mgmt_revocation.py
python3 test_p5_group4_safe_summary_candidate.py
node test_p5_group4_safe_summary_bff.mjs
python3 test_p5_group4_safe_summary_revocation.py
python3 test_p5_group5_session_state_candidate.py
node test_p5_group5_session_state_bff.mjs
python3 test_p5_group5_session_state_revocation.py
python3 test_p5_group6_public_boundary_candidate.py
node test_p5_group6_public_boundary_bff.mjs
python3 test_p5_group6_public_boundary_revocation.py
python3 test_post_p5_audit_sequence_acl.py
python3 test_post_p5_service_role_rpc_minimization.py
python3 test_post_p5_public_function_exec_boundary.py
python3 test_post_p5_public_default_privilege_guard.py
python3 test_post_p5_all_app_default_acl_verification.py
python3 test_post_p5_service_role_relation_acl.py
node test_post_p5_login_trusted_source_bucket.mjs
python3 test_post_p5_login_trusted_source_bucket.py
python3 test_post_p5_crm_acl_event_guard.py
python3 test_post_p5_crm_rls_alter_guard.py
python3 test_post_p5_bcrypt_password_byte_cap.py
python3 test_post_p5_single_workspace_membership_invariant.py
python3 test_post_p5_bcrypt_verification_byte_caps.py
python3 test_post_p5_rate_limit_concurrency.py
python3 test_post_p5_user_identity_byte_caps.py
node --check dist/cloud-adapter.js
node --check dist/cloud-security-hotfix.js
node --check dist/cloud-ui-action-bridge.js
