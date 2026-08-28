from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent
script = root / 'vercel-ignore-build.sh'


def run(*args, cwd, env=None, check=True):
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def commit(repo, message):
    run('git', 'add', '-A', cwd=repo)
    run('git', 'commit', '-m', message, cwd=repo)
    return run('git', 'rev-parse', 'HEAD', cwd=repo).stdout.strip()


if not script.is_file():
    raise SystemExit('missing vercel-ignore-build.sh')
if shutil.which('git') is None:
    raise SystemExit('git is required for Vercel ignored-build regression test')

with tempfile.TemporaryDirectory(prefix='growthops-vercel-ignore-') as tmp:
    repo = Path(tmp)
    run('git', 'init', cwd=repo)
    run('git', 'config', 'user.email', 'ci@example.invalid', cwd=repo)
    run('git', 'config', 'user.name', 'CRM CI', cwd=repo)

    (repo / 'api').mkdir()
    (repo / 'api' / 'crm.js').write_text('baseline runtime\n', encoding='utf-8')
    base = commit(repo, 'baseline')

    env = os.environ.copy()
    env['VERCEL_GIT_PREVIOUS_SHA'] = base

    # CI/workflow-only changes are intentionally non-runtime.
    (repo / '.github' / 'workflows').mkdir(parents=True)
    (repo / '.github' / 'workflows' / 'gate.yml').write_text('name: gate\n', encoding='utf-8')
    commit(repo, 'workflow only')
    result = run('sh', str(script), cwd=repo, env=env, check=False)
    if result.returncode != 0:
        raise SystemExit(f'workflow-only change should skip Vercel build: {result.stdout}')

    # Root test files and Markdown remain non-runtime as well.
    (repo / 'test_sample.py').write_text('print("test")\n', encoding='utf-8')
    (repo / 'notes.md').write_text('# notes\n', encoding='utf-8')
    commit(repo, 'tests and docs')
    result = run('sh', str(script), cwd=repo, env=env, check=False)
    if result.returncode != 0:
        raise SystemExit(f'test/Markdown-only changes should skip Vercel build: {result.stdout}')

    # Any runtime/config/finalizer-style file forces a Production build.
    (repo / 'api' / 'crm.js').write_text('runtime changed\n', encoding='utf-8')
    commit(repo, 'runtime change')
    result = run('sh', str(script), cwd=repo, env=env, check=False)
    if result.returncode != 1:
        raise SystemExit(f'runtime change must continue Vercel build: {result.stdout}')

    # Missing or invalid previous SHA must fail safe to a real build.
    missing = os.environ.copy()
    missing.pop('VERCEL_GIT_PREVIOUS_SHA', None)
    result = run('sh', str(script), cwd=repo, env=missing, check=False)
    if result.returncode != 1:
        raise SystemExit('missing previous SHA must continue Vercel build')

    invalid = os.environ.copy()
    invalid['VERCEL_GIT_PREVIOUS_SHA'] = '0' * 40
    result = run('sh', str(script), cwd=repo, env=invalid, check=False)
    if result.returncode != 1:
        raise SystemExit('invalid previous SHA must continue Vercel build')

print('VERCEL_IGNORE_BUILD_OK: ci/workflow+root-tests+markdown=skip; runtime/config/unknown-context=build')
