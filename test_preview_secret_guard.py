#!/usr/bin/env python3
"""Unit tests for Preview/production Supabase server-secret isolation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "preview_secret_guard.py"
PROD_URL = "https://avahcwyxparbcjdfglzx.supabase.co"
SAFE_SECRET = "sb_secret_test_preview_boundary"
LEAK_SECRET = "sb_secret_DO_NOT_LEAK_PREVIEW_BOUNDARY_20260823"

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

print(
    "PREVIEW_SECRET_BOUNDARY_TESTS_OK: production=unchanged; preview-no-secret=disabled; "
    "preview-production-target=blocked; preview-staging=allowed; malformed-target=blocked; secret-output=none"
)
