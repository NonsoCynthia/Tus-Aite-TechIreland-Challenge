#!/usr/bin/env bash
# kg_loader must not be able to read the answer key.
# A permission error is the test passing.
cd "$(dirname "$0")/../../dataset"
if docker compose exec -T db psql -U kg_loader -d triage \
     -c "SELECT count(*) FROM eval.ground_truth;" 2>/dev/null; then
  echo "FAIL: kg_loader can read eval.ground_truth"; exit 1
else
  echo "PASS: eval.ground_truth is unreachable"; exit 0
fi
