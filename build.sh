#!/bin/sh
set -eu
python3 verify_final_source.py
python3 build_final.py
python3 p2_finalize.py
python3 test_p2_output.py
python3 security_finalize.py
python3 security_reveal_ui_finalize.py
python3 test_security_hotfix_output.py
python3 test_security_reveal_ui_output.py
python3 cloud_save_queue_finalize.py
python3 test_cloud_save_queue_output.py
python3 ui_action_finalize.py
python3 test_ui_action_output.py
python3 ui_runtime_diagnostic_finalize.py
python3 test_ui_runtime_diagnostic_output.py
node --check dist/cloud-security-hotfix.js
node --check dist/cloud-ui-action-bridge.js
node --check dist/ui-runtime-diagnostic.js
