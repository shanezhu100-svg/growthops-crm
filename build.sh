#!/bin/sh
set -eu
rm -rf dist
python3 .cloud/build_cloud.py
