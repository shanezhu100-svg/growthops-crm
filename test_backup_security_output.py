from pathlib import Path

adapter = (Path(__file__).resolve().parent / 'dist' / 'cloud-adapter.js').read_text(encoding='utf-8')

required = {
    'backup secret key set': 'const BACKUP_SECRET_KEYS=new Set([',
    'recursive redactor': 'function redactBackupSecrets(value)',
    'redacted export version': "growth-ops-cloud-backup-v4-redacted",
    'redaction marker': "behavior:'credential keys removed recursively before backup export'",
    'redacted filename': 'growth-ops-backup-redacted-',
    'import strips secrets before apply': "const raw=JSON.parse(String(reader.result||'')),p=redactBackupSecrets(raw)",
    'import warning': '不会覆盖 Vault 凭证',
    'password key protected': "'loginpassword'",
    '2fa key protected': "'twofactorsecret'",
    'recovery codes protected': "'recoverycodes'",
    'login account protected in backups': "'loginaccount'",
}

missing = [name for name, marker in required.items() if marker not in adapter]
if missing:
    raise SystemExit('BACKUP_SECURITY_OUTPUT_TESTS_FAILED missing: ' + ', '.join(missing))

for forbidden in (
    "const p=JSON.parse(String(reader.result||''));if(!Array.isArray(p.clients))",
    "p.version='growth-ops-cloud-backup-v2'",
    "a.download=`growth-ops-backup-${vm.localDateKey()}.json`",
):
    if forbidden in adapter:
        raise SystemExit('BACKUP_SECURITY_OUTPUT_TESTS_FAILED legacy unsafe path remains: ' + forbidden)

print('BACKUP_SECURITY_OUTPUT_TESTS_OK')
