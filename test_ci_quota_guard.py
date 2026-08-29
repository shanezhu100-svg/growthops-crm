from pathlib import Path
import json

root = Path(__file__).resolve().parent
vercel = json.loads((root / 'vercel.json').read_text(encoding='utf-8'))
workflow = (root / '.github/workflows/crm-build.yml').read_text(encoding='utf-8')
build = (root / 'build.sh').read_text(encoding='utf-8')
ignore_script = (root / 'vercel-ignore-build.sh').read_text(encoding='utf-8')


def require(ok, message):
    if not ok:
        raise SystemExit(message)

rules = vercel.get('git', {}).get('deploymentEnabled')
require(
    rules == {'**': False, 'main': True},
    'Vercel Git deployment policy must deny slash-containing/non-main branch names with globstar and explicitly allow main',
)
require(
    '*' not in rules,
    'Vercel bare-star deny is insufficient for slash-containing branch names; use globstar',
)
require(
    vercel.get('ignoreCommand') == 'sh vercel-ignore-build.sh',
    'Vercel ignored-build policy must use the reviewed conservative classifier',
)
for marker in (
    'VERCEL_GIT_PREVIOUS_SHA',
    'git merge-base --is-ancestor',
    '.github/*|test_*.py|test_*.js|test_*.mjs|*.md',
    'runtime-relevant change',
    'previous deployment SHA unavailable; continue build',
):
    require(marker in ignore_script, f'Vercel ignored-build classifier missing fail-safe marker: {marker}')
require(
    'api/*' not in ignore_script and 'functions/*' not in ignore_script and 'supabase/*' not in ignore_script,
    'runtime/API/Supabase paths must never be allowlisted as non-runtime Vercel changes',
)

require('name: CRM Build Gate' in workflow, 'missing CRM Build Gate workflow')
require('pull_request:' in workflow and 'branches: [main]' in workflow, 'PR workflow must target main')
require('push:' in workflow, 'main push verification missing')
require('permissions:\n  contents: read' in workflow, 'workflow permissions must be contents:read only')
require('runs-on: ubuntu-24.04' in workflow, 'canonical CRM CI runner must remain pinned to Ubuntu 24.04')
require('runs-on: ubuntu-latest' not in workflow, 'canonical CRM CI runner must not drift through ubuntu-latest')
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
require(build.count('python3 test_vercel_ignore_build.py') == 1, 'canonical build must run Vercel ignored-build regression exactly once')

# The browser-liveness gate needs Chromium, which GitHub's pinned Ubuntu runner
# provides but Vercel/Cloudflare build images are not required to provide. Keep
# the deployable build portable while making the required GitHub check prove the
# exact final dist mounts successfully before the final pinned-output verifier.
browser_call = 'python3 test_browser_mount_smoke.py'
cloudflare_verify = 'python3 cloudflare_p1_verify.py'
require(workflow.count(browser_call) == 1, 'GitHub required build must run browser mount smoke exactly once')
require(build.count(browser_call) == 0, 'portable build.sh must not require Chromium')
require(workflow.count(cloudflare_verify) == 1, 'GitHub required build must run Cloudflare final verifier exactly once')
require(workflow.index('sh build.sh') < workflow.index(browser_call) < workflow.index(cloudflare_verify), 'CI order must be build -> browser mount -> final verifier')

print('CI_QUOTA_GUARD_OK: vercel-git=main-only; non-main=globstar-deployment-disabled; nonruntime-main=ignored-conservatively; slash-branches=covered; pr-ci=github-actions; runner=ubuntu-24.04; secrets=none; permissions=contents-read; actions=sha-pinned; node=24.x; canonical-build=sh-build.sh; browser-mount=github-only')
