# MemoryOS internals — one event's journey

This doc traces a single event from the moment it hits the API to the moment
it either becomes a promoted fact or is deferred to the user. Reading it
end-to-end is the fastest way to build a mental model of the system before
diving into code.

References throughout are to `backend/` — every file exists in the repo.

## The scenario

A calendar entry arrives:

```json
POST /api/events
{
  "type": "calendar",
  "content": "Weekly 1:1 with Sarah, 9am Monday, Zoom link in description",
  "occurred_at": "2026-04-06T09:00:00Z",
  "meta": {"source": "google-calendar"}
}
```

## Step 1 — the API layer receives it

Entry point: [`app/api/routes.py:96`](../backend/app/api/routes.py) —
`create_event()` accepts the payload as an `EventIn` pydantic model
([`app/schemas.py:15`](../backend/app/schemas.py)).

Because the payload has no `assertions` field, the API knows this is *raw*
text — it needs Qwen to extract structured claims. It calls
`extract_assertions()`.

## Step 2 — slow path: Qwen extracts assertions

[`app/extraction.py:36`](../backend/app/extraction.py) formats the extraction
prompt (system message pinned in `EXTRACTION_SYSTEM`), passes it through
the fallback chain, and gets back structured JSON. For this event, Qwen
might return:

```json
{"assertions": [
  {"subject": "user", "key": "meeting_mode", "value": "Zoom",
   "statement": "The user attends 1:1s over Zoom."},
  {"subject": "user", "key": "meeting_time_preference", "value": "9am",
   "statement": "The user schedules 1:1s at 9am."}
]}
```

The fallback chain
([`app/fallback_chain.py:20`](../backend/app/fallback_chain.py)) tries
`qwen-plus` first, then `qwen-turbo`, then a deterministic rules fallback
which returns an empty assertion list. That last step is deliberate: when
we can't reason, we record the event episodically and refuse to invent
assertions.

The API constructs a `MemoryEvent`
([`app/memory/core.py`](../backend/app/memory/core.py) has the dataclasses)
with a fresh UUID, the extracted assertions, the timestamp, and the raw
content. Then it calls `ingest_event()`.

## Step 3 — the deterministic engine (six-step fold)

[`app/engine.py:21`](../backend/app/engine.py) is where everything
interesting happens. The order matters and is locked in by
[`tests/test_engine_fold.py`](../backend/tests/test_engine_fold.py).

### 3.1 Episodic — record, never interpret

[`app/memory/episodic.py`](../backend/app/memory/episodic.py) —
`record_event(state, event)` appends the event to `state.events`. Nothing
else. This is the ground truth from which every derived structure is
regenerated.

### 3.2 Semantic — merge and corroborate

[`app/memory/semantic.py`](../backend/app/memory/semantic.py) —
`integrate_assertion(state, event, assertion)` runs once per assertion.

- If no fact for `(subject, key)` exists yet, create one with this event
  as its first source.
- If a fact exists with the *same value*, add this event to its sources —
  that's corroboration.
- If a fact exists with a *different value*, do NOT overwrite. Create
  a second fact for the new value and let it coexist. The auditor
  decides later.

The invariant: two disagreeing facts always live side by side. Nothing is
ever silently overwritten. The Memory browser in the dashboard shows both,
each with its own sources.

### 3.3 Decay — recompute all confidences with fresh timestamps

[`app/memory/decay.py`](../backend/app/memory/decay.py) — `apply_decay()`
walks every fact and recomputes its confidence via the documented formula
([`app/confidence.py`](../backend/app/confidence.py)):

```
confidence = 0.40 · corroboration      (independent origins, diminishing repeats)
           + 0.30 · recency            (half-life set by corroboration)
           + 0.20 · verification
           + 0.10 · user_confirmation
```

Single-source facts have a 6-month half-life; multi-source facts get
18 months. A fact whose confidence just dropped below the acting
threshold emits a `stale_memory` notification.

### 3.4 Auditor — resolve what evidence can decide

[`app/evidence_auditor.py`](../backend/app/evidence_auditor.py) —
`detect_contradictions()` scans for `(subject, key)` pairs with more than
one active fact. For each pair, it inspects both:

- **How many independent origins support each?**
- **What is the confidence gap?** (≥ 0.25 with the incumbent losing → the
  challenger is a *sustained preference change*, not a stray claim.)
- **When was the last support for each?** (Timeline-aware rule: a
  challenger whose latest supporting event is newer than the incumbent's
  latest supporting event is considered a preference change.)

If evidence can decide, the loser is marked superseded (not deleted — the
sources stay so the ledger is auditable). If evidence can't decide, a
`clarification_needed` notification is emitted and the user is asked on
the Auditor page.

The synthetic dataset intentionally includes two preference flips (the
user changes their meeting mode at session 8, notification channel at
session 12). Reproducing the eval shows those flips flowing through this
step:
[`docs/eval-methodology.md`](eval-methodology.md).

### 3.5 Verifier — promote what the world kept saying

[`app/verification.py`](../backend/app/verification.py) — a fact with
enough distinct-origin corroboration crosses from `unverified` to
`verified`. Verification is one term in the confidence formula, so
crossing this threshold visibly raises the fact's confidence bar in the UI.

### 3.6 Pattern — unprogrammed discovery

[`app/memory/pattern.py`](../backend/app/memory/pattern.py) has 5
deterministic detectors:

1. `post_break_reschedules` — reschedules after a 3+ day gap
2. `monday_reschedules` — reschedules that cluster on Mondays
3. `late_night_activity` — regular activity at 21:00–04:59
4. `weekend_avoidance` — Mon–Fri only for multiple weeks
5. `peak_hour_cluster` — one time-of-day band dominates the last 20 events

Each detector emits hits per supporting event. Patterns are only
*promoted* to trusted knowledge once they earn `min_support` events across
`min_sessions` (from
[`backend/config/confidence_policy.yaml`](../backend/config/confidence_policy.yaml)).
Nobody told MemoryOS that meetings tend to get rescheduled after long
weekends — but the pattern layer proves it structurally.

## Step 4 — persistence

Back in [`app/api/routes.py`](../backend/app/api/routes.py), after
`ingest_event()` returns, `_persist(request)` writes the whole state
snapshot to PostgreSQL through
[`app/store.py`](../backend/app/store.py). This is deliberately
snapshot-based, not incremental: at hackathon scale it's a few hundred
rows and it keeps the system simple. A production version would move to
an event-sourced write path.

## Step 5 — SSE broadcast

Every notification produced by the engine (a contradiction detected, a
pattern promoted, a fact verified) is published on the event bus
([`app/events.py`](../backend/app/events.py)). Any subscriber to
`/api/stream` receives it as an SSE `notification` event — that's how the
dashboard shows real-time toasts without polling.

## Ask time — the same fold, in reverse

`POST /api/ask` mirrors the ingest flow.

1. `map_question_to_key()` (Qwen slow-path with rules fallback) picks the
   most likely memory key from the ones tracked.
2. If a key is found, `decide()`
   ([`app/decision.py`](../backend/app/decision.py)) picks the best
   active fact, records the confidence gate reason, and includes the
   evidence chain.
3. `phrase_answer()` turns the decision JSON into a natural-language
   answer that cites its sources.
4. If no key matches, the API falls through to `hybrid_answer()`
   ([`app/retrieval.py`](../backend/app/retrieval.py)): semantic search
   over event embeddings, top-k retrieval, Qwen answer with citations —
   the RAG fallback for open-ended questions.

The response payload's `path` field says which route was taken:
`tracked-fact`, `hybrid-retrieval`, or `abstain`. The dashboard renders it
so viewers can see how each answer was arrived at.

## The load-bearing invariants

If you're skimming the code, these are the design opinions that hold
everything else up:

1. **Episodic events are the ground truth.** Every derived structure —
   facts, patterns, decay, confidence — is recomputable from
   `state.events`. Rebuilding is safe; there is no hidden mutable state
   outside the fold.

2. **Facts are never silently overwritten.** Disagreeing values coexist
   until the auditor decides or the user resolves. Losers are superseded,
   never deleted; the audit log preserves the whole chain.

3. **Confidence is a formula, not a vibe.** Every term is observable in
   the evidence chain, and every score in the UI can be recomputed by
   hand from the four terms.

4. **Slow path never invents.** Every Qwen call has a documented rules
   fallback. When the slow path fails, extraction returns no assertions
   rather than guessing. With zero API keys the deterministic fast path
   still runs the four-layer memory correctly.

5. **80/20 is a measured claim, not a slogan.** The cost tile on the
   dashboard counts every deterministic op vs every Qwen call.
   Standard demo state: 725 deterministic vs 2 Qwen = 99.6% fast-path.

## Where to go from here

- Reading [`docs/eval-methodology.md`](eval-methodology.md) after this
  gives you the numbers and how they're generated.
- [`docs/comparison.md`](comparison.md) explains why the design is
  distinct from RAG / Mem0 / LangGraph.
- [`docs/security.md`](security.md) is the honest write-up of what the
  prototype does and doesn't defend against.
