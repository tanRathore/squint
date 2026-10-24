#!/usr/bin/env bash
set -euo pipefail
file="${1:?usage: check.sh <file> [server]}"
server="${2:-http://localhost:8080}"
curl -sS -X POST "$server/v1/check" \
  -H "X-Device: cli-$(hostname)" \
  -F "file=@$file" \
  -F "source_app=cli" \
  -F "trigger=share" | python3 -c '
import json,sys
v=json.load(sys.stdin)
print(v["headline"], "  p=%s  %s confidence" % (v["p"], v["confidence"]))
print("buzz:", v["haptic"]["label"])
print("says:", v["say"])
for e in v["evidence"]: print(" -", e)
'
