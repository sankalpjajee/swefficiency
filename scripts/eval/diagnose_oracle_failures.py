#!/usr/bin/env python3
"""
Diagnose why oracle/gold runs are failing in SWE-fficiency evaluation.

Usage:
    python scripts/eval/diagnose_oracle_failures.py <run_log_dir>

    where <run_log_dir> is the path to logs/run_evaluation/<run_id>/gold/
    (the directory containing per-instance subdirectories).

    If you only have a CSV report:
    python scripts/eval/diagnose_oracle_failures.py --csv <eval_report.csv>
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


def diagnose_from_csv(csv_path: str):
    """Analyze failures from an eval report CSV."""
    df = pd.read_csv(csv_path)
    total = len(df)

    print(f"\n{'='*70}")
    print(f"DIAGNOSIS REPORT: {Path(csv_path).name}")
    print(f"{'='*70}")
    print(f"Total instances: {total}")

    # Overall score (harmonic mean)
    floored = df["human_speedup_ratio"].clip(lower=0.001)
    overall_score = total / (1 / floored).sum()
    print(f"Overall score (harmonic mean of SR): {overall_score:.4f}")

    # Correctness breakdown
    incorrect = df[df["correctness"] < 1.0]
    correct = df[df["correctness"] == 1.0]
    print(f"\n--- Correctness Breakdown ---")
    print(f"  Correct:   {len(correct):>4} ({len(correct)/total*100:.1f}%)")
    print(f"  Incorrect: {len(incorrect):>4} ({len(incorrect)/total*100:.1f}%)")

    if "correctness_pct" in df.columns:
        partial = incorrect[incorrect["correctness_pct"] > 0]
        zero = incorrect[incorrect["correctness_pct"] == 0]
        print(f"    - Zero correctness (no tests passed):     {len(zero):>4}")
        print(f"    - Partial correctness (some tests passed): {len(partial):>4}")

        if len(partial) > 0:
            print(f"\n  Partial correctness distribution:")
            bins = [0, 0.25, 0.5, 0.75, 0.99, 1.0]
            for i in range(len(bins) - 1):
                count = ((partial["correctness_pct"] > bins[i]) & (partial["correctness_pct"] <= bins[i+1])).sum()
                print(f"    ({bins[i]:.0%}, {bins[i+1]:.0%}]: {count}")

    # Performance breakdown for correct instances
    if len(correct) > 0:
        print(f"\n--- Performance (Correct Instances Only) ---")
        beat_expert = correct[correct["human_speedup_ratio"] >= 1.0]
        has_speedup = correct[correct["raw_pred_speedup_ratio"] > 1.0]
        no_speedup = correct[correct["raw_pred_speedup_ratio"] <= 1.0]
        print(f"  Beat expert (SR >= 1.0):  {len(beat_expert):>4}")
        print(f"  Has speedup (>1x):        {len(has_speedup):>4}")
        print(f"  No speedup (<=1x):        {len(no_speedup):>4}")

        print(f"\n  Speedup ratio stats (correct instances):")
        print(f"    Mean SR:   {correct['human_speedup_ratio'].mean():.4f}")
        print(f"    Median SR: {correct['human_speedup_ratio'].median():.4f}")
        print(f"    Min SR:    {correct['human_speedup_ratio'].min():.4f}")
        print(f"    Max SR:    {correct['human_speedup_ratio'].max():.4f}")

    # Impact analysis: what would the score be with 100% correctness?
    if len(incorrect) > 0:
        print(f"\n--- Impact Analysis ---")
        # If all incorrect became correct with their raw speedup
        hypothetical = df.copy()
        hypothetical["pred_speedup_ratio"] = hypothetical["raw_pred_speedup_ratio"]
        hypothetical["human_speedup_ratio"] = hypothetical["pred_speedup_ratio"] / hypothetical["gold_speedup_ratio"]
        floored_hyp = hypothetical["human_speedup_ratio"].clip(lower=0.001)
        hyp_score = total / (1 / floored_hyp).sum()
        print(f"  Current score:                          {overall_score:.4f}")
        print(f"  Hypothetical (if all correct w/ raw):   {hyp_score:.4f}")

    # Repo-level breakdown
    if "instance_id" in df.columns:
        df["repo"] = df["instance_id"].apply(lambda x: "__".join(x.split("__")[:2]))
        print(f"\n--- Per-Repo Breakdown ---")
        repo_stats = df.groupby("repo").agg(
            total=("correctness", "count"),
            correct=("correctness", "sum"),
            mean_sr=("human_speedup_ratio", "mean"),
        )
        repo_stats["correct"] = repo_stats["correct"].astype(int)
        repo_stats["pct_correct"] = (repo_stats["correct"] / repo_stats["total"] * 100).round(1)
        repo_stats = repo_stats.sort_values("pct_correct")
        for repo, row in repo_stats.iterrows():
            print(f"  {repo:<45} {row['correct']:>3}/{row['total']:<3} correct ({row['pct_correct']:>5.1f}%)  mean_sr={row['mean_sr']:.4f}")

    # Worst failures (lowest human_speedup_ratio)
    print(f"\n--- Bottom 10 Instances (by human_speedup_ratio) ---")
    bottom = df.nsmallest(10, "human_speedup_ratio")
    for _, row in bottom.iterrows():
        print(f"  {row['instance_id']:<55} SR={row['human_speedup_ratio']:.6f}  correct={row['correctness']:.0f}  gold_speedup={row['gold_speedup_ratio']:.2f}")

    # No perf_summary (pred_speedup_ratio = 1.0 AND raw = 1.0)
    no_perf = df[(df["raw_pred_speedup_ratio"] == 1.0) & (df["correctness"] < 1.0)]
    print(f"\n--- Missing/Failed Runs ---")
    print(f"  No perf data + incorrect: {len(no_perf)} (likely patch apply failure, timeout, or docker error)")

    print()


def diagnose_from_logs(log_dir: str):
    """Analyze failures from the run log directory structure."""
    log_path = Path(log_dir)
    if not log_path.exists():
        print(f"Error: {log_dir} does not exist")
        sys.exit(1)

    instance_dirs = [d for d in log_path.iterdir() if d.is_dir()]
    print(f"\n{'='*70}")
    print(f"DIAGNOSIS REPORT (from logs): {log_path}")
    print(f"{'='*70}")
    print(f"Total instance directories: {len(instance_dirs)}")

    categories = Counter()
    error_types = Counter()
    repo_errors = defaultdict(list)
    details = []

    for idir in sorted(instance_dirs):
        instance_id = idir.name
        repo = "__".join(instance_id.split("__")[:2])
        log_file = idir / "run_instance.log"
        report_file = idir / "report.json"
        perf_summary = idir / "perf_summary.txt"
        correctness_status = idir / "covering_test_status.json"

        status = "unknown"
        error_detail = ""

        if report_file.exists():
            try:
                report = json.loads(report_file.read_text())
                if report.get("correctness_report"):
                    status = "completed_with_correctness"
                elif report.get("perf_report"):
                    status = "completed_perf_only"
                else:
                    status = "completed_empty_report"
            except Exception:
                status = "report_parse_error"

        elif log_file.exists():
            log_text = log_file.read_text()

            if "Evaluation error" in log_text or "EvaluationError" in log_text:
                status = "evaluation_error"
                # Extract error type
                if "Failed to apply patch" in log_text or "APPLY_PATCH_FAIL" in log_text:
                    error_detail = "patch_apply_failure"
                elif "timed out" in log_text.lower() or "Timeout error" in log_text:
                    error_detail = "timeout"
                elif "Failed to revert correctness tests" in log_text:
                    error_detail = "revert_failure"
                elif "introspection guard" in log_text.lower():
                    error_detail = "introspection_guard_failure"
                elif "Correctness tests not found" in log_text:
                    error_detail = "no_correctness_tests"
                else:
                    # Get last error line
                    for line in reversed(log_text.splitlines()):
                        if "error" in line.lower() or "Error" in line:
                            error_detail = line.strip()[:100]
                            break
                    if not error_detail:
                        error_detail = "unknown_eval_error"

            elif "BuildImageError" in log_text:
                status = "build_error"
                error_detail = "docker_build_failure"

            elif "Error in evaluating" in log_text:
                status = "runtime_error"
                for line in reversed(log_text.splitlines()):
                    if "Error" in line:
                        error_detail = line.strip()[:100]
                        break

            else:
                # Check what's present
                if perf_summary.exists() and correctness_status.exists():
                    status = "completed_no_report"
                elif perf_summary.exists():
                    status = "perf_done_no_correctness"
                elif correctness_status.exists():
                    status = "correctness_done_no_perf"
                else:
                    status = "incomplete"
        else:
            status = "no_log_file"

        categories[status] += 1
        if error_detail:
            error_types[error_detail] += 1
            repo_errors[repo].append((instance_id, error_detail))

        details.append({
            "instance_id": instance_id,
            "repo": repo,
            "status": status,
            "error": error_detail,
            "has_perf": perf_summary.exists(),
            "has_correctness": correctness_status.exists(),
        })

    # Print summary
    print(f"\n--- Status Breakdown ---")
    for status, count in categories.most_common():
        print(f"  {status:<40} {count:>4}")

    if error_types:
        print(f"\n--- Error Type Breakdown ---")
        for err, count in error_types.most_common():
            print(f"  {err:<50} {count:>4}")

    if repo_errors:
        print(f"\n--- Errors by Repo ---")
        for repo in sorted(repo_errors, key=lambda r: -len(repo_errors[r])):
            errs = repo_errors[repo]
            err_counts = Counter(e for _, e in errs)
            print(f"  {repo} ({len(errs)} errors):")
            for err, c in err_counts.most_common():
                print(f"    {err}: {c}")

    # Check for correctness failures in completed instances
    correctness_failures = []
    for d in details:
        if d["has_correctness"]:
            cfile = Path(log_dir) / d["instance_id"] / "covering_test_status.json"
            try:
                test_results = json.loads(cfile.read_text())
                failed = [t for t, s in test_results.items() if "PASS" not in s]
                if failed:
                    correctness_failures.append((d["instance_id"], len(failed), len(test_results)))
            except Exception:
                pass

    if correctness_failures:
        print(f"\n--- Correctness Test Failures (in completed instances) ---")
        print(f"  {len(correctness_failures)} instances have failing tests")
        for iid, n_fail, n_total in sorted(correctness_failures, key=lambda x: -x[1])[:20]:
            print(f"    {iid:<55} {n_fail}/{n_total} tests failed")

    # Still running (no report, no error in log)
    incomplete = [d for d in details if d["status"] in ("incomplete", "no_log_file")]
    if incomplete:
        print(f"\n--- Possibly Still Running / Incomplete ---")
        for d in incomplete[:20]:
            print(f"  {d['instance_id']}")
        if len(incomplete) > 20:
            print(f"  ... and {len(incomplete) - 20} more")

    print()


def main():
    parser = argparse.ArgumentParser(description="Diagnose oracle/gold run failures")
    parser.add_argument("path", nargs="?", help="Path to run log directory (logs/run_evaluation/<run_id>/gold/<instance_dirs>)")
    parser.add_argument("--csv", help="Path to eval report CSV file")
    args = parser.parse_args()

    if args.csv:
        diagnose_from_csv(args.csv)
    elif args.path:
        path = Path(args.path)
        # Check if this looks like a log dir or if we need to find the gold subdir
        if (path / "gold").is_dir():
            diagnose_from_logs(str(path / "gold"))
        else:
            diagnose_from_logs(args.path)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
