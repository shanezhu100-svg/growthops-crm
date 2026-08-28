from pathlib import Path
import re

root = Path(__file__).resolve().parent
workflows = root / '.github' / 'workflows'
sha_ref = re.compile(r'^[^@\s]+@[0-9a-f]{40}$')
uses_line = re.compile(r'^\s*-?\s*uses:\s*([^\s#]+)')

checked = 0
workflow_count = 0
for path in sorted((*workflows.glob('*.yml'), *workflows.glob('*.yaml'))):
    workflow_count += 1
    text = path.read_text(encoding='utf-8')

    if 'permissions:\n  contents: read' not in text:
        raise SystemExit(f'{path.relative_to(root)}: workflow must explicitly use top-level contents: read permissions')
    for forbidden in (
        'pull_request_target:',
        'permissions: write-all',
        'contents: write',
        'actions: write',
        'id-token: write',
    ):
        if forbidden in text:
            raise SystemExit(f'{path.relative_to(root)}: forbidden workflow privilege/trigger: {forbidden}')

    if path.name.startswith('recovery-'):
        for required in (
            'workflow_dispatch:',
            'cancel-in-progress: false',
            'timeout-minutes: 25',
            "if: inputs.confirm_project_ref == 'avahcwyxparbcjdfglzx'",
            'SUPABASE_DB_URL: ${{ secrets.SUPABASE_DB_URL }}',
        ):
            if required not in text:
                raise SystemExit(f'{path.relative_to(root)}: recovery workflow missing fail-closed control: {required}')
        if re.search(r'(?m)^\s{2}(?:push|pull_request|schedule):', text):
            raise SystemExit(f'{path.relative_to(root)}: recovery workflow must remain manual-only')
        if text.count('${{ secrets.') != 1:
            raise SystemExit(f'{path.relative_to(root)}: recovery workflow must reference exactly one repository secret')
        if 'version: latest' in text:
            raise SystemExit(f'{path.relative_to(root)}: recovery tooling must not use version: latest')
        if 'supabase/setup-cli@' in text and 'version: 2.116.0' not in text:
            raise SystemExit(f'{path.relative_to(root)}: recovery Supabase CLI must remain pinned to accepted 2.116.0')

    for lineno, line in enumerate(text.splitlines(), 1):
        match = uses_line.match(line)
        if not match:
            continue
        ref = match.group(1)
        if ref.startswith('./'):
            continue
        if not sha_ref.fullmatch(ref):
            raise SystemExit(
                f'{path.relative_to(root)}:{lineno}: external GitHub Action must use an immutable 40-hex commit SHA: {ref}'
            )
        checked += 1

if workflow_count == 0:
    raise SystemExit('No GitHub workflows were found; workflow security gate may be misconfigured')
if checked == 0:
    raise SystemExit('No external GitHub Action references were found; pinning gate may be misconfigured')

print(
    f'WORKFLOW_ACTION_PINNING_OK: workflows={workflow_count}; external_action_refs={checked}; '
    'permissions=contents-read; no-pr-target/write-all; recovery=manual-only+one-secret+25m; '
    'all-actions=40-hex-sha; recovery-cli=2.116.0'
)
