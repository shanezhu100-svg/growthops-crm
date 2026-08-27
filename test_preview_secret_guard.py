#!/usr/bin/env python3
"""Unit tests for Preview/production Supabase server-secret isolation."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "preview_secret_guard.py"
PROD_URL = "https://avahcwyxparbcjdfglzx.supabase.co"
SAFE_SECRET = "sb_secret_test_preview_boundary"
LEAK_SECRET = "sb_secret_DO_NOT_LEAK_PREVIEW_BOUNDARY_20260823"

CURRENT_STATE = (ROOT / "docs/cloudflare-migration/CURRENT_STATE.md").read_text(encoding="utf-8")
ROLLBACK = (ROOT / "docs/cloudflare-migration/ROLLBACK.md").read_text(encoding="utf-8")
CURRENT_RECOVERY = (ROOT / "docs/cloudflare-migration/CURRENT_RECOVERY_VERIFICATION.md").read_text(encoding="utf-8")
PREVIEW_BOUNDARY = (ROOT / "docs/cloudflare-migration/POST_P5_PREVIEW_SECRET_BOUNDARY.md").read_text(encoding="utf-8")
CONCURRENCY_ACCEPTANCE = (ROOT / "docs/cloudflare-migration/POST_P5_RATE_LIMIT_CONCURRENCY.md").read_text(encoding="utf-8")

CONTROLLED = {
    "CF_PAGES",
    "CF_PAGES_BRANCH",
    "VERCEL_ENV",
    "GROWTHOPS_SUPABASE_URL",
    "GROWTHOPS_SUPABASE_SECRET_KEY",
}


def run(extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in CONTROLLED}
    env.update(extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def expect_ok(extra: dict[str, str], needle: str) -> None:
    result = run(extra)
    assert result.returncode == 0, result.stderr
    assert needle in result.stdout, result.stdout


def expect_fail(extra: dict[str, str], needle: str) -> None:
    result = run(extra)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert needle in result.stderr, result.stderr


expect_ok({}, "platform=production-or-local")
expect_ok(
    {"CF_PAGES": "1", "CF_PAGES_BRANCH": "main", "GROWTHOPS_SUPABASE_SECRET_KEY": SAFE_SECRET},
    "platform=production-or-local",
)
expect_ok(
    {"VERCEL_ENV": "production", "GROWTHOPS_SUPABASE_SECRET_KEY": SAFE_SECRET},
    "platform=production-or-local",
)
expect_ok(
    {"CF_PAGES": "1", "CF_PAGES_BRANCH": "feature-safe"},
    "backend=disabled",
)
expect_ok({"VERCEL_ENV": "preview"}, "backend=disabled")
expect_ok({"CF_PAGES": "1"}, "platform=cloudflare-unknown")
expect_fail(
    {
        "CF_PAGES": "1",
        "CF_PAGES_BRANCH": "feature-unsafe",
        "GROWTHOPS_SUPABASE_SECRET_KEY": SAFE_SECRET,
    },
    "would default to production",
)
expect_fail(
    {
        "CF_PAGES": "1",
        "GROWTHOPS_SUPABASE_SECRET_KEY": SAFE_SECRET,
    },
    "would default to production",
)
expect_fail(
    {
        "CF_PAGES": "1",
        "CF_PAGES_BRANCH": "feature-unsafe",
        "GROWTHOPS_SUPABASE_SECRET_KEY": SAFE_SECRET,
        "GROWTHOPS_SUPABASE_URL": PROD_URL,
    },
    "cannot target the production Supabase project",
)
expect_fail(
    {
        "VERCEL_ENV": "preview",
        "GROWTHOPS_SUPABASE_SECRET_KEY": SAFE_SECRET,
        "GROWTHOPS_SUPABASE_URL": PROD_URL + "/",
    },
    "cannot target the production Supabase project",
)
expect_ok(
    {
        "CF_PAGES": "1",
        "CF_PAGES_BRANCH": "feature-staging",
        "GROWTHOPS_SUPABASE_SECRET_KEY": SAFE_SECRET,
        "GROWTHOPS_SUPABASE_URL": "https://stagingref123.supabase.co",
    },
    "backend=isolated",
)
expect_ok(
    {
        "VERCEL_ENV": "preview",
        "GROWTHOPS_SUPABASE_SECRET_KEY": SAFE_SECRET,
        "GROWTHOPS_SUPABASE_URL": "https://stagingref456.supabase.co/",
    },
    "target=stagingref456.supabase.co",
)
for bad_url in (
    "http://stagingref.supabase.co",
    "https://example.com",
    "not-a-url",
    "https://user:pass@stagingref.supabase.co",
    "https://stagingref.supabase.co:8443",
    "https://stagingref.supabase.co:notaport",
    "https://stagingref.supabase.co/rest/v1",
    "https://stagingref.supabase.co/?query=1",
    "https://stagingref.supabase.co/#fragment",
):
    expect_fail(
        {
            "VERCEL_ENV": "preview",
            "GROWTHOPS_SUPABASE_SECRET_KEY": SAFE_SECRET,
            "GROWTHOPS_SUPABASE_URL": bad_url,
        },
        "Preview",
    )

leak = run(
    {
        "CF_PAGES": "1",
        "CF_PAGES_BRANCH": "feature-leak-check",
        "GROWTHOPS_SUPABASE_SECRET_KEY": LEAK_SECRET,
        "GROWTHOPS_SUPABASE_URL": PROD_URL,
    }
)
assert leak.returncode == 1
assert LEAK_SECRET not in leak.stdout
assert LEAK_SECRET not in leak.stderr

# Preserve the historical 2026-08-25 fail-closed evidence. It proves the guard
# worked while a Production secret was still present in Preview; it is no longer
# evidence that cleanup is currently open.
vercel_preview_evidence = "dpl_HfSpEkWs9D34A1a28WLiaCMrCnKY"
for text, label in (
    (CURRENT_STATE, "CURRENT_STATE"),
    (ROLLBACK, "ROLLBACK"),
    (CURRENT_RECOVERY, "CURRENT_RECOVERY_VERIFICATION"),
    (PREVIEW_BOUNDARY, "POST_P5_PREVIEW_SECRET_BOUNDARY"),
    (CONCURRENCY_ACCEPTANCE, "POST_P5_RATE_LIMIT_CONCURRENCY"),
):
    assert vercel_preview_evidence in text, f"{label} missing historical Vercel Preview fail-closed evidence"
    assert "PREVIEW_SECRET_BOUNDARY_FAILED" in text, f"{label} missing historical fail-closed Vercel Preview evidence"

for text, label in (
    (CURRENT_STATE, "CURRENT_STATE"),
    (ROLLBACK, "ROLLBACK"),
    (CURRENT_RECOVERY, "CURRENT_RECOVERY_VERIFICATION"),
    (CONCURRENCY_ACCEPTANCE, "POST_P5_RATE_LIMIT_CONCURRENCY"),
):
    assert "Vercel Preview secret isolation remains unverified" not in text, f"{label} regressed Vercel Preview to unverified"
    assert "Vercel Preview secret scope remains **unverified**" not in text, f"{label} regressed Vercel Preview to unverified"
    assert "Vercel Preview environment-variable scope was not independently inspectable" not in text, f"{label} contains stale Vercel Preview evidence"

# The moving current authorities must now record the independently verified
# platform cleanup accepted on 2026-08-27. Historical phase/rollback docs may
# retain their point-in-time open-state evidence.
cleanup_marker = "Preview Production-secret cleanup accepted on 2026-08-27"
for text, label in (
    (CURRENT_STATE, "CURRENT_STATE"),
    (CURRENT_RECOVERY, "CURRENT_RECOVERY_VERIFICATION"),
):
    assert cleanup_marker in text, f"{label} missing accepted Preview cleanup marker"
    assert "Vercel Preview: no project environment variables" in text, f"{label} missing Vercel Preview cleanup evidence"
    assert "Cloudflare Preview: `GROWTHOPS_SUPABASE_SECRET_KEY` removed" in text, f"{label} missing Cloudflare Preview cleanup evidence"
    assert "Issue #92: closed / completed" in text, f"{label} must record #92 closure"

for stale in (
    "platform cleanup remains required because the Preview-scoped secret itself has not been proven removed",
    "Platform cleanup remains open and is tracked by issue #92",
    "both platform Preview secret scopes were confirmed as still requiring cleanup",
    "Complete platform acceptance still requires removing the Production secret from Preview scope",
    "Vercel and Cloudflare Preview cleanup are both currently confirmed outstanding",
    "Keep issue #92 open until Preview Production-secret cleanup is independently verified",
):
    assert stale not in CURRENT_STATE, f"CURRENT_STATE contains stale Preview-open claim: {stale}"
    assert stale not in CURRENT_RECOVERY, f"CURRENT_RECOVERY_VERIFICATION contains stale Preview-open claim: {stale}"

# Keep the accepted PR #86 globstar/main policy checkpoint as historical evidence
# without forcing its then-current Production deployment to remain the forever
# current deployment in CURRENT_STATE.
accepted_globstar_commit = "91c0edcb24b79d282faa72d7d83435a1e1265d30"
accepted_globstar_deployment = "dpl_HiGGTxc4zYJM9zq1s13CV5Pv2tW6"
for text, label in (
    (CURRENT_STATE, "CURRENT_STATE"),
    (ROLLBACK, "ROLLBACK"),
    (CURRENT_RECOVERY, "CURRENT_RECOVERY_VERIFICATION"),
    (PREVIEW_BOUNDARY, "POST_P5_PREVIEW_SECRET_BOUNDARY"),
    (CONCURRENCY_ACCEPTANCE, "POST_P5_RATE_LIMIT_CONCURRENCY"),
):
    assert accepted_globstar_commit in text, f"{label} missing accepted globstar/main checkpoint"

for text, label in (
    (ROLLBACK, "ROLLBACK"),
    (CURRENT_RECOVERY, "CURRENT_RECOVERY_VERIFICATION"),
    (PREVIEW_BOUNDARY, "POST_P5_PREVIEW_SECRET_BOUNDARY"),
    (CONCURRENCY_ACCEPTANCE, "POST_P5_RATE_LIMIT_CONCURRENCY"),
):
    assert accepted_globstar_deployment in text, f"{label} missing accepted PR #86 Production deployment evidence"

# CURRENT_STATE is intentionally a moving authority. Verify that its validated
# runtime/security checkpoint has the required evidence shape instead of pinning
# a forever-current deployment/SHA here.
current_vercel_section = re.search(
    r"Current validated runtime/security checkpoint deployment:\s*\n\s*"
    r"- deployment: `(dpl_[A-Za-z0-9]+)`;\s*\n"
    r"- state: `READY`;\s*\n"
    r"- Git commit: `([0-9a-f]{40})`;\s*\n"
    r"- merged-main CRM Build Gate #(\d+): completed / success;\s*\n"
    r"- stable alias assigned successfully\.",
    CURRENT_STATE,
)
assert current_vercel_section, "CURRENT_STATE missing structurally complete validated Vercel runtime/security checkpoint"
current_deployment, current_commit, current_gate = current_vercel_section.groups()
assert current_deployment != vercel_preview_evidence, "CURRENT_STATE runtime checkpoint cannot be Preview evidence"
assert current_commit != accepted_globstar_commit or current_deployment != accepted_globstar_deployment, (
    "CURRENT_STATE runtime checkpoint must be independently advanceable beyond historical PR #86 evidence"
)
assert int(current_gate) > 0, "CURRENT_STATE current merged-main Gate number must be positive"
assert "documentation/test-only may exist without superseding this checkpoint" in CURRENT_STATE, (
    "CURRENT_STATE must prevent documentation-only deployment self-reference"
)

assert '"**": false' in PREVIEW_BOUNDARY, "Preview boundary docs missing slash-safe Vercel deny rule"
assert '"main": true' in PREVIEW_BOUNDARY, "Preview boundary docs missing Vercel main allow rule"

print(
    "PREVIEW_SECRET_BOUNDARY_TESTS_OK: production=unchanged; preview-no-secret=disabled; "
    "preview-production-target=blocked; preview-staging=allowed; malformed-target=blocked; "
    "secret-output=none; historical-open-evidence=retained; platform-cleanup=accepted-20260827; "
    "vercel-git-preview=main-only; current-vercel-checkpoint=dynamic-runtime-evidence-shape"
)
