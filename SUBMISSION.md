# Devpost submission — working sheet

**Track: 1 — MemoryAgent**

## Checklist (from the hackathon brief)

- [ ] Public repo URL with **MIT license detectable in the About section**
      (GitHub auto-detects `LICENSE` at repo root — verify the badge shows).
- [ ] **Proof of Alibaba Cloud deployment**: short screen recording (console
      + `docker compose ps` on ECS + external `curl /health` + dashboard on
      public IP). Plus the code-file link:
      `backend/app/qwen_client.py`.
- [ ] **Architecture diagram**: `architecture.svg` (embedded in README).
- [ ] **~3-minute demo video** on YouTube/Vimeo, public.
      Storyboard: `docs/demo-script.md`.
- [ ] **Text description** (below).
- [ ] Track identified: **MemoryAgent**.
- [ ] Optional: blog post for the Blog Prize.

## Text description (paste into Devpost)

**MemoryOS — AI shouldn't remember more. It should remember correctly.**

Most "memory agents" are retrieval systems: they store more, but they don't
get smarter — and the more they store, the more they hallucinate, because
the model fills gaps with invention when retrieval is noisy.

MemoryOS treats memory as a chain of evidence. Every stored fact carries its
source, its confidence, and its lineage across four layers: **episodic**
(raw events with provenance, never interpreted), **semantic** (duplicates
merge, and their sources merge with them), **pattern** (knowledge promoted
only when several sourced episodes agree), and **decay** (single-source
memories fade 3× faster than corroborated ones). Confidence is a documented
formula — 40% corroboration, 30% recency, 20% verification, 10% user
confirmation — so every score in the UI can be recomputed by hand from the
evidence chain. Policy-as-code gates what the agent may do: act at ≥80%,
show sources at ≥40%, otherwise ask instead of guessing.

An **Evidence Auditor** runs after every ingest: it detects contradictions,
resolves what evidence can decide (its timeline-aware rule distinguishes a
genuine preference change from a one-off noisy claim), and escalates the
rest to the user — whose answer becomes the strongest evidence in the
formula.

The proof is structural, not a marketing claim: a deterministic, seeded eval
asks the same 12 decision tasks after each of 20 sessions against a
synthetic enterprise history containing noise and two genuine preference
changes. MemoryOS climbs from 42% to 100% accuracy and its acting gate never
once fired on a wrong answer (precision-when-acting 1.00 across 1,440
decisions on 6 seeds), while a last-assertion-wins baseline whipsaws on
noise and sometimes ends the run wrong. Accuracy rises because evidence
accumulates — the model never changed.

Built on Alibaba Cloud end to end: Qwen (qwen-plus → qwen-turbo →
rules-only fallback chain) via Model Studio's DashScope OpenAI-compatible
API handles the ~20% of work needing genuine reasoning (assertion
extraction, question mapping, sourced answers); the deterministic fast path
handles the other 80% at zero token cost. The memory store is ApsaraDB RDS
for PostgreSQL (pgvector), and the FastAPI backend + Next.js evidence
dashboard run on ECS. The dashboard streams the system's self-triggered
events live: contradictions detected, clarifications requested, patterns
discovered, facts verified.

## Links to fill

- Repo: `https://github.com/<user>/memoryos`
- Demo video: `<YouTube URL>`
- Deployment proof recording: `<URL>`
- Live instance (optional): `http://<ecs-ip>/`
