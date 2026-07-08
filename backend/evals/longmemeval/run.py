"""CLI: run MemoryOS against LongMemEval (or a subset).

Examples:
  python -m evals.longmemeval.run --n 10 --seed 42
  python -m evals.longmemeval.run --categories knowledge-update,temporal-reasoning --n 20
  python -m evals.longmemeval.run --all              # full 500 (expensive)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from collections import defaultdict
from pathlib import Path

from .adapter import replay_and_answer, result_to_dict
from .judge import grade

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_PATHS = {
    "oracle": DATA_DIR / "longmemeval_oracle.json",
    "small": DATA_DIR / "longmemeval_s.json",
}


def load_dataset(variant: str = "oracle") -> list[dict]:
    with open(DATA_PATHS[variant], encoding="utf-8") as f:
        return json.load(f)


def stratified_sample(
    data: list[dict], n: int, seed: int, categories: list[str] | None
) -> list[dict]:
    rng = random.Random(seed)
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for inst in data:
        if categories and inst["question_type"] not in categories:
            continue
        by_cat[inst["question_type"]].append(inst)
    cats = list(by_cat.keys())
    per_cat = max(1, n // len(cats))
    picked = []
    for c in cats:
        pool = by_cat[c][:]
        rng.shuffle(pool)
        picked.extend(pool[:per_cat])
    rng.shuffle(picked)
    return picked[:n]


async def _run_one(inst: dict, max_sessions: int | None, compare_rag: bool) -> dict:
    t0 = time.time()
    r = await replay_and_answer(inst, max_sessions=max_sessions, compare_rag=compare_rag)
    mos_correct, mos_reason, judge_provider = await grade(
        r.question, r.memoryos_answer, r.gold_answer
    )
    out = result_to_dict(r)
    out["correct"] = mos_correct
    out["judge_reason"] = mos_reason
    out["judge_provider"] = judge_provider
    if compare_rag and r.rag_answer is not None:
        rag_correct, rag_reason, _ = await grade(r.question, r.rag_answer, r.gold_answer)
        out["rag_correct"] = rag_correct
        out["rag_reason"] = rag_reason
    out["elapsed_s"] = round(time.time() - t0, 2)
    return out


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10, help="stratified sample size")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--categories", type=str, default=None, help="comma-separated types")
    parser.add_argument("--max-sessions", type=int, default=None, help="cap sessions per instance")
    parser.add_argument("--all", action="store_true", help="use every instance (expensive)")
    parser.add_argument("--out", type=str, default=None, help="write JSONL results here")
    parser.add_argument("--variant", type=str, default="oracle", choices=["oracle", "small"])
    parser.add_argument("--rag", action="store_true", help="also run vanilla RAG baseline")
    args = parser.parse_args()

    data = load_dataset(args.variant)
    categories = args.categories.split(",") if args.categories else None
    if args.all:
        sample = [x for x in data if not categories or x["question_type"] in categories]
    else:
        sample = stratified_sample(data, args.n, args.seed, categories)

    print(f"Running {len(sample)} instances")
    print(f"Categories: {sorted({x['question_type'] for x in sample})}")
    print(f"Max sessions/instance: {args.max_sessions or 'all'}")
    print("-" * 60)

    results: list[dict] = []
    out_fh = open(args.out, "w", encoding="utf-8") if args.out else None
    try:
        for i, inst in enumerate(sample, start=1):
            try:
                out = await _run_one(inst, args.max_sessions, args.rag)
            except Exception as exc:
                out = {
                    "question_id": inst["question_id"],
                    "question_type": inst["question_type"],
                    "correct": False,
                    "error": str(exc)[:200],
                }
            results.append(out)
            if out_fh:
                out_fh.write(json.dumps(out, ensure_ascii=False) + "\n")
                out_fh.flush()
            mark = "OK  " if out.get("correct") else "MISS"
            rag_mark = ""
            if args.rag:
                rag_mark = f" rag={'OK' if out.get('rag_correct') else 'MISS'}"
            print(
                f"[{i}/{len(sample)}] {out['question_type']:>28}  {mark}{rag_mark}  "
                f"gate={out.get('memoryos_gate','?'):<12} "
                f"path={out.get('memoryos_path','?'):<16} "
                f"qwen={out.get('qwen_calls',0):<3} "
                f"t={out.get('elapsed_s',0):.1f}s"
            )
    finally:
        if out_fh:
            out_fh.close()

    total = len(results)
    correct = sum(1 for r in results if r.get("correct"))
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_cat[r["question_type"]].append(r)

    print("-" * 60)
    print(f"MemoryOS: {correct}/{total} = {correct / max(total, 1):.1%}")
    if args.rag:
        rag_correct = sum(1 for r in results if r.get("rag_correct"))
        print(f"RAG baseline: {rag_correct}/{total} = {rag_correct / max(total, 1):.1%}")
    for cat in sorted(by_cat):
        c_correct = sum(1 for r in by_cat[cat] if r.get("correct"))
        cn = len(by_cat[cat])
        line = f"  {cat:>28}: MemoryOS {c_correct}/{cn} = {c_correct / cn:.1%}"
        if args.rag:
            rag_c = sum(1 for r in by_cat[cat] if r.get("rag_correct"))
            line += f"  |  RAG {rag_c}/{cn} = {rag_c / cn:.1%}"
        print(line)

    acting = [r for r in results if r.get("memoryos_gate") == "act"]
    if acting:
        prec = sum(1 for r in acting if r.get("correct")) / len(acting)
        print(f"\nPrecision when acting: {prec:.2%} ({len(acting)} decisions)")


if __name__ == "__main__":
    asyncio.run(main())
