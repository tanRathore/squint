#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
out="${1:-dist}"
mkdir -p "$out"
(cd server && python -m pytest -q)
(cd research && python -m pytest -q test_research.py)
git bundle create "$out/squint.bundle" --all
tar --exclude='squint/research/runs' --exclude='squint/research/*/runs' --exclude='squint/research/data*' --exclude='squint/server/*.db' --exclude='squint/demo.db' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='squint/.git' -czf "$out/squint-src.tar.gz" -C .. squint
ls -la "$out"
echo "clone with: git clone $out/squint.bundle squint"
