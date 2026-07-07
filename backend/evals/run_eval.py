"""CLI: python -m evals.run_eval [--sessions 20] [--seed 42]

Prints the accuracy curve as a table. Reproducible: same seed → same numbers.
"""

from __future__ import annotations

import argparse
import json

from .harness import run_eval


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", action="store_true", help="dump full results as JSON")
    args = parser.parse_args()

    results = run_eval(sessions=args.sessions, seed=args.seed)["results"]
    if args.json:
        print(json.dumps(results, default=str, indent=2))
        return

    print(f"\nDataset: {results['dataset']}\n")
    header = (
        f"{'S':>3} {'MemoryOS':>9} {'Baseline':>9} {'ActPrec':>8} "
        f"{'Act%':>6} {'Ask%':>6} {'Facts':>6} {'Contr(o/r)':>10} {'Patterns':>8}"
    )
    print(header)
    print("-" * len(header))
    for row in results["sessions"]:
        has_prec = row["precision_when_acting"] is not None
        prec = f"{row['precision_when_acting']:.2f}" if has_prec else "  — "
        print(
            f"{row['session']:>3} {row['memoryos_accuracy']:>9.2%} "
            f"{row['baseline_accuracy']:>9.2%} "
            f"{prec:>8} {row['act_rate']:>6.0%} {row['ask_rate']:>6.0%} {row['facts_active']:>6} "
            f"{row['contradictions_open']:>4}/{row['contradictions_resolved']:<5} "
            f"{row['patterns_promoted']:>8}"
        )
    print("\nSummary:", json.dumps(results["summary"], indent=2))


if __name__ == "__main__":
    main()
