# Evaluation methodology

The headline claim — decision accuracy rises across sessions because evidence
accumulates — is measured, not asserted. This document describes exactly how.

## Dataset (synthetic, clearly labeled)

`backend/evals/dataset.py` generates 20 weekly work sessions for one persona
across five origins (calendar, email, note, task, chat). It is **fully
seeded**: the same seed always yields the same events, timestamps, and noise.

- **12 preference/behavior keys** with known ground truth (meeting time,
  meeting mode, report format, notification channel, …).
- **Two genuine preference changes**: `meeting_mode` flips remote→office at
  session 8; `notification_channel` flips email→slack at session 12. Ground
  truth at each session reflects the flip — a memory that cannot update is
  scored wrong.
- **Noise**: each session has a 30% chance of one misleading one-off event
  asserting the *currently wrong* value for a random key (e.g. a one-off
  afternoon meeting for a morning-preferring user).
- **Pattern raw material**: sessions 4, 9, 14, 17 open with a calendar
  reschedule right after a ≥3-day gap — no assertions attached; only the
  pattern layer can turn these into knowledge.
- Sessions are anchored to real weekly timestamps ending "now", so decay
  behaves exactly as it would on live data.

The dataset deliberately produces the three situations a memory system must
survive: **sparse early evidence, noisy exceptions, and true preference
change**. The confidence policy (`backend/config/confidence_policy.yaml`)
was written before the dataset and was not tuned per-seed.

## Tasks and scoring

After ingesting each session, the harness (`backend/evals/harness.py`) asks
the **same 12 decision tasks** — one per key ("Which value holds for X?") —
against two systems over identical data:

- **MemoryOS**: `decide()` returns its best value plus a gate
  (act / show_sources / ask) from the confidence policy.
- **Baseline (last-assertion-wins)**: the most recent stored claim wins; no
  corroboration, no decay, no contradiction handling, and it always acts.
  This is what a plain retrieval memory effectively does.

Metrics per session:

- **accuracy** — fraction of the 12 tasks whose best answer matches ground
  truth at that session (asked-instead-of-acted still counts by its value;
  "no memory yet" counts wrong).
- **precision when acting** — of the tasks where MemoryOS's gate allowed
  acting (confidence ≥ 0.80, unambiguous), the fraction answered correctly.
  This is the trust metric: *when it acts, is it right?*
- **act rate / ask rate** — how often confidence cleared the acting gate.

## Results

Seed 42 (reproduce: `python -m evals.run_eval --sessions 20 --seed 42`):

| Session | MemoryOS | Baseline |
|---|---|---|
| 1 | 41.7% | 41.7% |
| 5 | 91.7% | 91.7% |
| 10 | 100% | 91.7% |
| 16 | 100% | **75.0%** |
| 20 | 100% | 100% |

Act rate grows 0% → 75%; precision-when-acting is 1.00 in every session.

Seed sweep (`python -m evals.seed_sweep`, seeds 1, 2, 3, 7, 42, 99):

| Seed | MemoryOS s1 | MemoryOS s20 | MemoryOS min (s6+) | Baseline s20 | Baseline min (s6+) | Precision acting |
|---|---|---|---|---|---|---|
| 1 | 42% | 100% | 92% | 83% | 83% | 1.00 |
| 2 | 33% | 100% | 83% | 92% | 75% | 1.00 |
| 3 | 42% | 100% | 100% | 100% | 83% | 1.00 |
| 7 | 42% | 100% | 100% | 100% | 92% | 1.00 |
| 42 | 42% | 100% | 100% | 100% | 75% | 1.00 |
| 99 | 42% | 100% | 92% | 92% | 92% | 1.00 |

Reading: the early climb is evidence coverage (both systems see the same
events); the separation after warm-up is **noise robustness and contradiction
handling** — the baseline trusts whatever came last, so a single misleading
event flips it, while MemoryOS demands corroboration. On two seeds the
baseline *ends the run wrong*; MemoryOS never does. And MemoryOS's acting
gate never fired on a wrong answer in 120 evaluated sessions across 6 seeds.

## Determinism

The harness makes **zero LLM calls** — dataset events carry structured
assertions, so the eval measures memory dynamics, not extraction quality.
Extraction quality is exercised separately through the live ingest path
(`POST /api/events` without `assertions`), where Qwen extracts claims from
raw text with a rules-only fallback that extracts nothing rather than
guessing.

## Threats to validity (read this before trusting the numbers)

1. **Synthetic data.** The generator and the memory system were written by
   the same authors. Mitigations: the policy file predates the dataset, no
   per-seed tuning, all generator parameters are visible in
   `dataset.py`, and the mechanism producing the separation (recency-only
   trust vs corroborated trust) is structural, not fitted.
2. **The baseline is simple.** Last-assertion-wins is the honest lower bound
   of "vector DB attached to a chatbot" behavior, not a tuned RAG stack.
   Stronger baselines (recency-weighted voting, frequency-weighted retrieval)
   are future work.
3. **Small task set.** 12 tasks × 20 sessions × 6 seeds = 1,440 decisions —
   enough to show the structural effect, not a benchmark-grade sample.
4. **Verification is intra-corpus.** A fact "verifies" when independent
   origins across ≥2 sessions agree; there is no external ground-truth oracle
   in the loop beyond the eval's own scoring.
