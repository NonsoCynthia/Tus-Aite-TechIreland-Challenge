#!/usr/bin/env bash
# Confirms an install is good. Run after `make load`.
#
# Query 7 FAILING is the pass condition. If agent_rw can read eval.ground_truth,
# the held-out guarantee is not holding and the install is broken.
set -uo pipefail

cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

PSQL="docker exec triage_db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -tAc"
pass=0; fail=0

check() { # name, expected, actual
  if [ "$2" = "$3" ]; then echo "  PASS  $1"; pass=$((pass+1))
  else echo "  FAIL  $1 (expected $2, got $3)"; fail=$((fail+1)); fi
}

echo "1. Table counts per schema"
for s in core:18 agent:7 eval:1; do
  schema=${s%%:*}; want=${s##*:}
  got=$($PSQL "SELECT count(*) FROM information_schema.tables WHERE table_schema='$schema' AND table_type='BASE TABLE';")
  check "$schema has $want tables" "$want" "$got"
done

echo "2. Triage categories sort by severity, not by code"
got=$($PSQL "SELECT string_agg(description,'|' ORDER BY severity_rank NULLS LAST) FROM core.ref_codes WHERE code_table='triage_category';")
check "Urgent before Semi-Urgent before Routine" "Urgent|Semi-Urgent|Routine/Non-Urgent|Excluded" "$got"

echo "3. Leading zeros survived"
got=$($PSQL "SELECT count(*) FROM core.ref_specialty WHERE specialty_hipe='0601';")
check "specialty 0601 exists" "1" "$got"

echo "4. Every table has a primary key"
got=$($PSQL "SELECT count(*) FROM information_schema.tables t WHERE t.table_schema IN ('core','agent','eval') AND t.table_type='BASE TABLE' AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints c WHERE c.table_schema=t.table_schema AND c.table_name=t.table_name AND c.constraint_type='PRIMARY KEY');")
check "tables without a PK" "0" "$got"

echo "5. Private hospitals have capacity but no queue"
got=$($PSQL "SELECT count(*) FROM core.referrals r JOIN core.hospitals h USING (hospital_hipe) WHERE h.hospital_type='private';")
check "referrals at private sites" "0" "$got"

echo "6. agent_rw can read core"
# `SET ROLE` makes psql echo "SET" before the result, so take the last line only.
got=$($PSQL "SET ROLE agent_rw; SELECT count(*) FROM core.ref_rules;" 2>/dev/null | tail -1)
check "agent_rw reads core.ref_rules" "5" "$got"

echo "7. The answer key is unreachable  (FAILING HERE IS THE PASS CONDITION)"
if $PSQL "SET ROLE agent_rw; SELECT count(*) FROM eval.ground_truth;" >/dev/null 2>&1; then
  echo "  FAIL  agent_rw CAN read eval.ground_truth -- the held-out guarantee is broken"
  fail=$((fail+1))
else
  echo "  PASS  agent_rw denied on eval.ground_truth"
  pass=$((pass+1))
fi

echo
echo "  $pass passed, $fail failed"
[ "$fail" -eq 0 ] || exit 1
