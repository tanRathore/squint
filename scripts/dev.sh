#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../server"
[ -f .env ] || cp .env.example .env
pip install -q -e ".[dev]"
exec squint serve --reload --port "${PORT:-8080}"
