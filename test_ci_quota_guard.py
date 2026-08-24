from pathlib import Path
import json

root = Path(__file__).resolve().parent
vercel = json.loads((root / 'vercel.json').read_text(encoding='utf-8'))
workflow = (root / '.github/workflows/crm-build.yml').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')


def require(ok, message):
    if not ok:
        raise SystemExit(message)

rules = vercel.get('git', {}).get('deploymentEnabled')
require(rules == {'*': False, 'main': True}, 'Vercel Git deployment policy must default-deny every branch and explicitly allow main')

require('name: CRM Build Gate' in workflow, 'missing CRM Build Gate workflow')
require('pull_request:' in workflow and 'branches: [main]' in workflow, 'PR workflow must target main')
require('push:' in workflow, 'main push verification missing')
require('permissions:\n  contents: read' in workflow, 'workflow permissions must be contents:read only')
require("GROWTHOPS_SUPABASE_SECRET_KEY: ''" in workflow and "GROWTHOPS_SUPABASE_URL: ''" in workflow, 'workflow must explicitly clear Supabase server identity')
require('${{ secrets.' not in workflow and 'secrets:' not in workflow, 'workflow must not consume repository secrets')
require('actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1' in workflow, 'checkout action must stay pinned to reviewed v7.0.1 SHA')
require('actions/setup-node@820762786026740c76f36085b0efc47a31fe5020' in workflow, 'setup-node action must stay pinned to reviewed v7 SHA')
require('persist-credentials: false' in workflow, 'checkout credentials must not persist')
require("node-version: '24.x'" in workflow, 'CI Node version must match Vercel 24.x runtime')
require('package-manager-cache: false' in workflow, 'unneeded package-manager cache must stay disabled')
require('run: sh build.sh' in workflow, 'PR CI must execute canonical build.sh')
require('cancel-in-progress: true' in workflow, 'stale PR CI must be cancelled')
require(build.count('python3 test_ci_quota_guard.py') == 1, 'canonical build must run quota/CI guard exactly once')

print('CI_QUOTA_GUARD_OK: vercel-git=main-only; non-main=deployment-disabled; pr-ci=github-actions; secrets=none; permissions=contents-read; actions=sha-pinned; node=24.x; canonical-build=sh-build.sh')
