"""One-command end-to-end demo of MemoryOS.

Prints the whole thesis against a live backend in about 30 seconds:

  1. Reset memory + counters.
  2. Seed the 20-session synthetic evidence dataset.
  3. Reproduce the deterministic accuracy curve (42% → 100%,
     precision-when-acting 1.00).
  4. Ask a tracked-fact question (shows the confidence-gated answer path).
  5. Ask a hybrid-retrieval question (shows the retrieval + cite fallback).
  6. Ask a question with a low-corroboration key (shows the abstention).
  7. Print discovered patterns.
  8. Print the fast-path counter.

Usage:
  python -m evals.demo                                  # localhost:8000
  python -m evals.demo --api http://8.219.249.248       # any deployed URL
  python -m evals.demo --skip-reset                     # keep existing state
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx


def _hr(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def _bold(s: str) -> str:
    return f"\033[1m{s}\033[0m"


def _green(s: str) -> str:
    return f"\033[32m{s}\033[0m"


def _cyan(s: str) -> str:
    return f"\033[36m{s}\033[0m"


def _grey(s: str) -> str:
    return f"\033[90m{s}\033[0m"


def _ask(client: httpx.Client, api: str, question: str, label: str) -> None:
    print(f"\n{_bold('Q')}: {question}")
    r = client.post(f"{api}/api/ask", json={"question": question, "compare": True}, timeout=60)
    r.raise_for_status()
    body = r.json()
    path = body.get("path", "?")
    ans = body.get("answer", "")
    print(f"{_bold('A')}: {ans}")
    tag = f"[path={path}"
    if body.get("decision", {}).get("gate"):
        tag += f", gate={body['decision']['gate']}"
    if body.get("decision", {}).get("confidence") is not None:
        tag += f", conf={body['decision']['confidence']:.2f}"
    tag += "]"
    print(_grey(tag))
    if body.get("baseline"):
        print(_grey(f"[baseline (last-wins) says: {body['baseline'].get('answer','?')}]"))
    print(_grey(f"[scene: {label}]"))


def run_demo(api: str, skip_reset: bool) -> int:
    client = httpx.Client()

    _hr(_cyan("MemoryOS demo"))
    print(f"Target: {api}")
    t0 = time.time()

    r = client.get(f"{api}/health", timeout=10)
    r.raise_for_status()
    health = r.json()
    if not health.get("qwen_available"):
        print(_grey("Warning: DASHSCOPE_API_KEY not configured; rules-only fallback in use."))

    if not skip_reset:
        client.post(f"{api}/api/demo/reset", timeout=15).raise_for_status()

    _hr("1. Seed the 20-session synthetic evidence dataset")
    r = client.post(f"{api}/api/demo/seed", json={"sessions": 20}, timeout=60)
    r.raise_for_status()
    seed = r.json()
    print(
        f"  events={seed['events']}  facts={seed['facts_active']}"
        f"  notifications={seed['notifications_emitted']}"
    )

    _hr("2. Reproduce the deterministic 20-session accuracy curve (zero-LLM)")
    r = client.post(
        f"{api}/api/eval/run",
        json={"label": "demo", "sessions": 20, "seed": 42},
        timeout=120,
    )
    r.raise_for_status()
    results = r.json()
    s = results["summary"]
    mos_first = f"{s['memoryos_first']:.0%}"
    mos_last = f"{s['memoryos_last']:.0%}"
    base_first = f"{s['baseline_first']:.0%}"
    base_last = f"{s['baseline_last']:.0%}"
    print(f"  MemoryOS s1: {mos_first}  ->  s20: {_green(mos_last)}")
    print(f"  Baseline s1: {base_first}  ->  s20: {base_last}")
    prec = s.get("mean_precision_when_acting")
    if prec is not None:
        prec_s = f"{prec:.0%}"
        print(f"  Precision when acting: {_green(prec_s)}")
    print(f"  Final act rate: {s['final_act_rate']:.0%}")

    _hr("3. Ask panel — the three demo scenes")
    _ask(client, api, "When does the user prefer to have meetings?", "tracked-fact path")
    _ask(
        client,
        api,
        "Are there any calendar reschedule events in memory?",
        "hybrid-retrieval fallback",
    )
    _ask(
        client,
        api,
        "What is the user's favorite dessert?",
        "abstain (no evidence)",
    )

    _hr("4. Unprogrammed discoveries — pattern layer")
    patterns = client.get(f"{api}/api/patterns", timeout=15).json()
    promoted = [p for p in patterns if p.get("promoted")]
    if not promoted:
        print("  no patterns promoted yet — need more sessions")
    for p in promoted:
        print(f"  * {_cyan(p['name'])}: {p['description']}")
        print(f"      support: {p['support']} events, sessions {p['sessions']}")

    _hr("5. The 80/20 that isn't a slogan — fast-path counter")
    stats = client.get(f"{api}/api/stats", timeout=15).json()
    cost = stats.get("cost", {})
    fast_pct = cost.get("fast_path_pct", 0) * 100
    fast_s = f"{fast_pct:.1f}%"
    print(f"  Fast-path share:      {_green(fast_s)}")
    print(f"  Deterministic ops:    {cost.get('deterministic_ops', 0):,}")
    print(f"  Qwen calls:           {cost.get('qwen_calls', 0)}")
    print(f"  Est. input tokens:    {cost.get('qwen_input_tokens_est', 0):,}")
    by_model = cost.get("qwen_by_model", {})
    if by_model:
        print(f"  Calls by model:       {by_model}")

    elapsed = time.time() - t0
    print(_grey(f"\nElapsed: {elapsed:.1f}s"))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api",
        default=os.getenv("MEMORYOS_API", "http://localhost:8000"),
        help="MemoryOS backend URL (default: env MEMORYOS_API or localhost:8000)",
    )
    parser.add_argument(
        "--skip-reset",
        action="store_true",
        help="don't reset memory before seeding",
    )
    args = parser.parse_args()
    try:
        sys.exit(run_demo(args.api, args.skip_reset))
    except httpx.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
