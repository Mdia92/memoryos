# Demo script — 3 minutes

Target: one continuous screen recording of the dashboard (plus a separate,
shorter Alibaba Cloud deployment proof recording — see deploy-alibaba.md).

Prep before recording:

```bash
curl -X POST localhost:8000/api/demo/reset
curl -X POST localhost:8000/api/eval/run -H "Content-Type: application/json" -d '{"label":"demo","sessions":20,"seed":42}'
curl -X POST localhost:8000/api/demo/seed -H "Content-Type: application/json" -d '{"sessions":20}'
```

Keep the Ask page open in one tab, Auditor in another, Dashboard in a third.

---

**0:00–0:20 — The problem (Ask page).**
Ask: *"Does the user prefer remote or office meetings?"*
Point at the left card: the traditional memory answers instantly, fluently,
with **no sources, no confidence** — "You prefer office."
Point at the right card: MemoryOS refuses to bluff — it holds conflicting
evidence ("office" 85% vs "remote" 79%, margin too small) and **asks**.
Line: *"One of these answers is a guess. The other one knows it doesn't know."*

**0:20–0:50 — Why: memory as evidence (Memory page).**
Open the memory browser. Expand "User prefers morning meetings":
the evidence chain (calendar, email, note, chat entries with dates) and the
confidence breakdown — 40% corroboration, 30% recency, 20% verification,
10% user confirmation. Line: *"Every score on this screen can be recomputed
by hand from the sources. Nothing is invented."*

**0:50–1:25 — The Evidence Auditor (Auditor page).**
Show the open contradiction (remote vs office) with both evidence sides.
Click **"This is correct"** on office. The toast fires live (SSE), the
contradiction moves to resolved-by-user, the audit trail logs the user as
actor. Line: *"When evidence can't decide, it asks — and my answer becomes
the strongest evidence it has."*
Return to Ask, re-ask the same question: now a confident, cited answer.

**1:25–2:10 — The structural proof (Dashboard).**
The accuracy chart: MemoryOS climbs 42% → 100% and never dips after warm-up;
the baseline whipsaws on noise (down to 75%) because it trusts whatever came
last. Below it, the act-rate chart: 0% → 75% — *confidence is earned, session
by session*. Point at "Precision when acting: 100%": *"In 120 sessions across
six seeds, the acting gate never once fired on a wrong answer. The model
never changed — only the evidence accumulated."*

**2:10–2:35 — Unprogrammed discovery (Dashboard, patterns panel).**
Read the promoted pattern: *"Meetings are frequently rescheduled right after
long weekends"* — 4 supporting episodes across sessions 4, 9, 14, 17.
Line: *"Nobody ever told it that. It was promoted only after enough sourced
episodes agreed — that's the pattern layer's evidence bar, in the policy
file."*

**2:35–3:00 — Close (Ask page, side-by-side still on screen).**
Line: *"Traditional AI memory guesses — fluently. MemoryOS knows: every fact
traced, every confidence earned, every contradiction surfaced. AI shouldn't
remember more. It should remember correctly."*
Show the repo README + architecture diagram for the final two seconds.

---

Fallback notes:
- If Qwen keys are unset the answers render from the deterministic fallback
  and the provider chip shows `rules-only` — the demo still works; mention
  the fallback chain as a feature if it happens.
- All demo state is reproducible: reset + eval + seed (commands above).
