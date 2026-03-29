#!/bin/bash
# Slim failure report - only key error info, no full test stdout
# Usage: bash dump_failures_slim.sh [JOB_DIR] [OUTPUT_FILE]

JOB_DIR="${1:-$HOME/harbor/adapters/swefficiency/jobs/2026-03-28__08-21-49}"
OUTPUT="${2:-failure_report_slim.md}"

echo "Scanning $JOB_DIR ..."

{
echo "# Oracle Run Failure Report (Slim)"
echo ""
echo "Job: \`$JOB_DIR\`"
echo "Generated: $(date)"
echo ""

PASSED=$(grep -rl '^1$' "$JOB_DIR"/*/verifier/reward.txt 2>/dev/null | wc -l)
FAILED=$(grep -rl '^0$' "$JOB_DIR"/*/verifier/reward.txt 2>/dev/null | wc -l)
echo "## Summary"
echo ""
echo "- **Passed:** $PASSED"
echo "- **Failed:** $FAILED"
echo ""

echo "## Category 1: No Test Results Available"
echo ""

grep -rl '^0$' "$JOB_DIR"/*/verifier/reward.txt 2>/dev/null | sort | while read f; do
  dir=$(dirname "$f")
  task=$(basename "$(dirname "$dir")")
  output=$(cat "$dir/test_output.txt" 2>/dev/null)
  if echo "$output" | grep -q "No test results available"; then
    echo "### $task"
    echo '```'
    cat "$dir/test_output.txt" 2>/dev/null
    echo '```'
    # Only last 10 lines of test-stdout for context
    echo "**test-stdout.txt (last 10 lines):**"
    echo '```'
    tail -10 "$dir/test-stdout.txt" 2>/dev/null
    echo '```'
    echo ""
  fi
done

echo "## Category 2: Real Regressions"
echo ""

grep -rl '^0$' "$JOB_DIR"/*/verifier/reward.txt 2>/dev/null | sort | while read f; do
  dir=$(dirname "$f")
  task=$(basename "$(dirname "$dir")")
  output=$(cat "$dir/test_output.txt" 2>/dev/null)
  if echo "$output" | grep -q "Real regressions"; then
    echo "### $task"
    echo '```'
    cat "$dir/test_output.txt" 2>/dev/null
    echo '```'
    echo ""
  fi
done

echo "## Category 3: Other Failures"
echo ""

grep -rl '^0$' "$JOB_DIR"/*/verifier/reward.txt 2>/dev/null | sort | while read f; do
  dir=$(dirname "$f")
  task=$(basename "$(dirname "$dir")")
  output=$(cat "$dir/test_output.txt" 2>/dev/null)
  if ! echo "$output" | grep -q "No test results available" && ! echo "$output" | grep -q "Real regressions"; then
    echo "### $task"
    echo '```'
    cat "$dir/test_output.txt" 2>/dev/null
    echo '```'
    echo ""
  fi
done

} > "$OUTPUT"

echo "Report written to $OUTPUT ($(wc -l < "$OUTPUT") lines, $(du -h "$OUTPUT" | cut -f1))"
