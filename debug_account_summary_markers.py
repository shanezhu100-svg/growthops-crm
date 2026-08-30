from pathlib import Path

security = (Path(__file__).resolve().parent / 'dist' / 'cloud-security-hotfix.js').read_text(encoding='utf-8')
terms = ('summaryFor', 'AccountSafeSummary', 'accountSafeSummary', 'ExternalAssetAccount', 'credentialClient')
lines = []
for line in security.splitlines():
    stripped = line.strip()
    if any(term in stripped for term in terms):
        lines.append(stripped[:360])
print('ACCOUNT_SUMMARY_MARKER_INVENTORY_START')
for line in lines:
    print(line)
print('ACCOUNT_SUMMARY_MARKER_INVENTORY_END count=' + str(len(lines)))
