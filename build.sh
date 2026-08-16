#!/bin/sh
set -eu
python3 verify_final_source.py
python3 build_final.py
python3 p2_finalize.py
python3 test_p2_output.py
python3 security_finalize.py
python3 scroll_finalize.py
python3 test_security_hotfix_output.py
python3 test_scroll_output.py
