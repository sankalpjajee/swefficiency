#!/bin/bash
# Dump all failure details from a harbor job into a markdown file
# Usage: bash scripts/eval/dump_failures.sh [JOB_DIR] [OUTPUT_FILE]

JOB_DIR="${1:-$HOME/harbor/adapters/swefficiency/jobs/2026-03-28__08-21-49}"
OUTPUT="${2:-failure_report.md}"

echo "Scanning $JOB_DIR ..."

{
echo "# Oracle Run Failure Report"
echo ""
echo "Job: \`$JOB_DIR\`"
echo "Generated: $(date)"
echo ""

PASSED=$(grep -rl '^1$' "$JOB_DIR"/*/verifier/reward.txt 2>/dev/null | wc -l)
FAILED=$(grep -rl '^0$' "$JOB_DIR"/*/verifier/reward.txt 2>/dev/null | wc -l)
TOTAL=$((PASSED + FAILED))
echo "## Summary"
echo ""
echo "- **Passed:** $PASSED"
echo "- **Failed:** $FAILED"
echo "- **Total completed:** $TOTAL"
echo ""

# Category 1: No test results available
echo "## Category 1: No Test Results Available"
echo ""
echo "These instances failed because the test framework produced no parseable results."
echo ""

grep -rl '^0$' "$JOB_DIR"/*/verifier/reward.txt 2>/dev/null | sort | while read f; do
  dir=$(dirname "$f")
  task=$(basename "$(dirname "$dir")")
  output=$(cat "$dir/test_output.txt" 2>/dev/null)
  if echo "$output" | grep -q "No test results available"; then
    echo "### $task"
    echo ""
    echo "**test_output.txt:**"
    echo '```'
    cat "$dir/test_output.txt" 2>/dev/null
    echo '```'
    echo ""
    echo "**test-stdout.txt (last 50 lines):**"
    echo '```'
    tail -50 "$dir/test-stdout.txt" 2>/dev/null
    echo '```'
    echo ""
    # Also check for exception.txt
    if [ -f "$(dirname "$dir")/exception.txt" ]; then
      echo "**exception.txt:**"
      echo '```'
      cat "$(dirname "$dir")/exception.txt" 2>/dev/null
      echo '```'
      echo ""
    fi
    # Check trial.log
    if [ -f "$(dirname "$dir")/trial.log" ]; then
      echo "**trial.log (last 30 lines):**"
      echo '```'
      tail -30 "$(dirname "$dir")/trial.log" 2>/dev/null
      echo '```'
      echo ""
    fi
    echo "---"
    echo ""
  fi
done

# Category 2: Real regressions
echo "## Category 2: Real Regressions (Gold Patch Breaks Tests)"
echo ""
echo "These instances failed because applying the gold/oracle patch caused test regressions."
echo ""

grep -rl '^0$' "$JOB_DIR"/*/verifier/reward.txt 2>/dev/null | sort | while read f; do
  dir=$(dirname "$f")
  task=$(basename "$(dirname "$dir")")
  output=$(cat "$dir/test_output.txt" 2>/dev/null)
  if echo "$output" | grep -q "Real regressions"; then
    echo "### $task"
    echo ""
    echo "**test_output.txt:**"
    echo '```'
    cat "$dir/test_output.txt" 2>/dev/null
    echo '```'
    echo ""
    echo "**test-stdout.txt (last 50 lines):**"
    echo '```'
    tail -50 "$dir/test-stdout.txt" 2>/dev/null
    echo '```'
    echo ""
    echo "---"
    echo ""
  fi
done

# Category 3: Other failures
echo "## Category 3: Other Failures"
echo ""

grep -rl '^0$' "$JOB_DIR"/*/verifier/reward.txt 2>/dev/null | sort | while read f; do
  dir=$(dirname "$f")
  task=$(basename "$(dirname "$dir")")
  output=$(cat "$dir/test_output.txt" 2>/dev/null)
  if ! echo "$output" | grep -q "No test results available" && ! echo "$output" | grep -q "Real regressions"; then
    echo "### $task"
    echo ""
    echo "**test_output.txt:**"
    echo '```'
    cat "$dir/test_output.txt" 2>/dev/null
    echo '```'
    echo ""
    echo "**test-stdout.txt (last 50 lines):**"
    echo '```'
    tail -50 "$dir/test-stdout.txt" 2>/dev/null
    echo '```'
    echo ""
    echo "---"
    echo ""
  fi
done

} > "$OUTPUT"

echo "Report written to $OUTPUT ($(wc -l < "$OUTPUT") lines)"
