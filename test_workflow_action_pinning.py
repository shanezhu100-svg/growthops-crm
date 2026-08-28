from pathlib import Path
import re

root = Path(__file__).resolve().parent
workflows = root / '.github' / 'workflows'
sha_ref = re.compile(r'^[^@\s]+@[0-9a-f]{40}$')
uses_line = re.compile(r'^\s*-?\s*uses:\s*([^\s#]+)')

checked = 0
for path in sorted((*workflows.glob('*.yml'), *workflows.glob('*.yaml'))):
    text = path.read_text(encoding='utf-8')
    if path.name.startswith('recovery-'):
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

if checked == 0:
    raise SystemExit('No external GitHub Action references were found; pinning gate may be misconfigured')

print(f'WORKFLOW_ACTION_PINNING_OK: external_action_refs={checked}; all=40-hex-sha; recovery-cli=2.116.0')
