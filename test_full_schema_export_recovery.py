from pathlib import Path

root = Path(__file__).resolve().parent

for test_name in (
    'test_full_schema_export_recovery_v2.py',
    'test_recovery_bundle_v3.py',
    'test_recovery_sql_editor_acceptance.py',
):
    test_path = root / test_name
    scope = {
        '__name__': '__main__',
        '__file__': str(test_path),
    }
    exec(compile(test_path.read_text(encoding='utf-8'), str(test_path), 'exec'), scope)
