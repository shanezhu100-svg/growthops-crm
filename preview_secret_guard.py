#!/usr/bin/env python3
"""Fail closed if a Preview build can reach the production Supabase project with a server secret."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
PUBLIC_CONFIG = ROOT / "public-runtime-config.json"
SECRET_ENV = "GROWTHOPS_SUPABASE_SECRET_KEY"
URL_ENV = "GROWTHOPS_SUPABASE_URL"
PRODUCTION_BRANCH = "main"


def fail(message: str) -> "NoReturn":
    print(f"PREVIEW_SECRET_BOUNDARY_FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def canonical_supabase_host() -> str:
    try:
        config = json.loads(PUBLIC_CONFIG.read_text(encoding="utf-8"))
        value = str(config.get("supabaseUrl") or "").strip()
    except Exception:
        fail("canonical public-runtime-config.json is unreadable")
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host.endswith(".supabase.co"):
        fail("canonical production Supabase URL is invalid")
    return host


def preview_platforms() -> list[str]:
    platforms: list[str] = []
    if os.getenv("CF_PAGES", "").strip() == "1":
        branch = os.getenv("CF_PAGES_BRANCH", "").strip()
        if branch and branch != PRODUCTION_BRANCH:
            platforms.append("cloudflare-preview")
    if os.getenv("VERCEL_ENV", "").strip().lower() == "preview":
        platforms.append("vercel-preview")
    return platforms


def validate_preview_target(raw_url: str, production_host: str) -> str:
    if not raw_url:
        fail("Preview server secret is set but GROWTHOPS_SUPABASE_URL is absent; runtime would default to production")
    parsed = urlparse(raw_url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host.endswith(".supabase.co"):
        fail("Preview server secret requires an explicit HTTPS *.supabase.co staging URL")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        fail("Preview Supabase URL contains unsupported credentials or port")
    if host == production_host:
        fail("Preview server secret cannot target the production Supabase project")
    return host


def main() -> None:
    platforms = preview_platforms()
    if not platforms:
        print("PREVIEW_SECRET_BOUNDARY_OK: platform=production-or-local; enforcement=inactive")
        return

    label = "+".join(platforms)
    secret_present = bool(os.getenv(SECRET_ENV, "").strip())
    if not secret_present:
        print(
            f"PREVIEW_SECRET_BOUNDARY_OK: platform={label}; backend=disabled; "
            "server-secret=absent"
        )
        return

    production_host = canonical_supabase_host()
    target_host = validate_preview_target(os.getenv(URL_ENV, "").strip(), production_host)
    print(
        f"PREVIEW_SECRET_BOUNDARY_OK: platform={label}; backend=isolated; "
        f"target={target_host}"
    )


if __name__ == "__main__":
    main()
