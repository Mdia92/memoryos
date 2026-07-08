# Demo script — 3 minutes

Target: one continuous screen recording of the dashboard (plus a separate,
shorter Alibaba Cloud deployment proof recording — see deploy-alibaba.md).

Prep before recording (against the live ECS instance at
`http://8.219.249.248` or a local backend):

```bash
export API=http://8.219.249.248
curl -X POST $API/api/demo/reset
curl -X POST $API/api/demo/seed -H "Content-Type: application/json" \
     -d '{"sessions":20}'
curl -X POST $API/api/eval/run -H "Content-Type: application/json" \
     -d '{"label":"demo","sessions":20,"seed":42}'
```

Keep the Ask page open in one tab, Auditor in another, Dashboard in a third.

---

**0:00 – 0:15 — The problem (Ask page).**
Ask: *"Does the user prefer remote or office meetings?"*
Point at the left card: traditional memory answers instantly, fluently,
with **no sources, no confidence** — "You prefer office."
Point at the right card: MemoryOS refuses to bluff — holds conflicting
evidence ("office" 85% vs "remote" 79%, margin too small) and **asks**.
Line: *"One of these answers is a guess. The other one knows it doesn't know."*

**0:15 – 0:45 — Memory as evidence (Memory page).**
Open the memory browser. Expand *"User prefers morning meetings"*:
the evidence chain (11 events across chat, task, note, email from Feb–Jun 2026)
and the confidence breakdown — **40% corroboration, 30% recency, 20% verification,
10% user confirmation**. Line: *"Every score on this screen can be recomputed
by hand from the sources. Nothing is invented."*

**0:45 – 1:15 — The Evidence Auditor (Auditor page).**
Show the open contradiction (remote vs office) with both evidence sides.
Click **"This is correct"** on office. The toast fires live (SSE), the
contradiction moves to resolved-by-user, the audit trail logs the user as
actor. Line: *"When evidence can't decide, it asks — and my answer becomes
the strongest evidence it has."*
Return to Ask, re-ask the same question: now a confident, cited answer.

**1:15 – 1:35 — Hybrid retrieval — questions with no tracked key (Ask page).**
Ask a question the system was never told to track:
*"Are there any calendar reschedule events in the memory?"*
Point at the response: **no tracked fact, but four calendar events retrieved
by semantic similarity**, each with an event id, timestamp, and similarity
score. The answer cites them explicitly.
Line: *"When we can't answer from a tracked fact, we fall back to retrieval
over the raw event store — with citations. No hallucination surface."*

**1:35 – 2:05 — The structural proof (Dashboard).**
The accuracy chart: MemoryOS climbs **42% → 100%** and never dips after warm-up;
the baseline whipsaws on noise (down to 75%) because it trusts whatever came
last. Below it, the act-rate: 0% → 75%. Point at **"Precision when acting:
100%"**: *"In 120 sessions across six seeds, the acting gate never once fired
on a wrong answer. The model never changed — only the evidence accumulated."*

**2:05 – 2:20 — The 80/20 that isn't a slogan (KPI row).**
Point at the second KPI row: **Fast-path share 99.6%**, Qwen calls 2,
deterministic ops 485 — *for a live 20-session state*.
Line: *"The hybrid architecture isn't a marketing claim — it's a counter.
Every call MemoryOS avoids is a token judges aren't paying for."*

**2:20 – 2:40 — Unprogrammed discovery (Dashboard, patterns panel).**
Read a promoted pattern: *"Meetings are frequently rescheduled right after
long weekends"* — 4 supporting episodes across sessions 4, 9, 14, 17.
Line: *"Nobody ever told it that. It was promoted only after enough sourced
episodes agreed — that's the pattern layer's evidence bar, in the policy
file."*

**2:40 – 3:00 — Close (Ask page, side-by-side still on screen).**
Line: *"Traditional AI memory guesses — fluently. MemoryOS knows: every fact
traced, every confidence earned, every contradiction surfaced. Built on Qwen
through Alibaba Cloud, running now at http://8.219.249.248. AI shouldn't
remember more. It should remember correctly."*
Show the repo README + architecture diagram for the final two seconds.

---

## Bonus scene: real ingestion (record separately if time permits)

Position: Alongside the main video or as a follow-up short.

```bash
# 1) Markdown notes vault (Obsidian, Bear, .md folder)
python -m evals.ingest_markdown \
  --path ~/my-notes --api http://8.219.249.248

# 2) Calendar file (Google Calendar → export → .ics)
python -m evals.ingest_ics \
  --path ~/my-calendar.ics --api http://8.219.249.248
```

On screen: watch each file post to the backend, Qwen extract structured
assertions live (`primary_language=Rust`, `meeting_time_preference=morning`),
confidence scores climb. Real calendars with `RECURRENCE-ID` reschedule
events flow into the pattern layer — the `weekend_avoidance` and
`late_night_activity` detectors fire on live data. If the notes mention
conflicting things, the Auditor page pops up a new open contradiction in
real time.

Line: *"This isn't a rehearsed dataset. This is my own notes folder and my
own calendar. MemoryOS just built the evidence chain from scratch."*

---

Fallback notes:

- If Qwen keys are unset the answers render from the deterministic fallback
  and the provider chip shows `rules-only` — the demo still works; mention
  the fallback chain as a feature if it happens.
- All demo state is reproducible: reset + eval + seed (commands above).
- The live URL `http://8.219.249.248` is the running Alibaba Cloud ECS
  instance — same code, same UI, same data. Recording against it is fine
  and doubles as deployment proof.
