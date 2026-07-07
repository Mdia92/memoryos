"""Robustness check: run the eval across several seeds and print a summary.

    python -m evals.seed_sweep
"""

from __future__ import annotations

from .harness import run_eval

SEEDS = [1, 2, 3, 7, 42, 99]


def main() -> None:
    for seed in SEEDS:
        r = run_eval(sessions=20, seed=seed)["results"]
        rows = r["sessions"]
        mos = [x["memoryos_accuracy"] for x in rows]
        base = [x["baseline_accuracy"] for x in rows]
        prec = r["summary"]["mean_precision_when_acting"]
        print(
            f"seed {seed:>3}: MOS s1={mos[0]:.0%} s5={mos[4]:.0%} s10={mos[9]:.0%} "
            f"s20={mos[-1]:.0%} min(s6+)={min(mos[5:]):.0%} | "
            f"BASE s20={base[-1]:.0%} min(s6+)={min(base[5:]):.0%} | actprec={prec}"
        )


if __name__ == "__main__":
    main()
