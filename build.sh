#!/bin/sh
set -eu
python3 verify_final_source.py
python3 build_final.py
