# I stopped optimizing my AI's memory. I started auditing it instead.

*Building MemoryOS for the Qwen Cloud Global AI Hackathon — a note on
what "memory" actually means when the model is downstream of the truth.*

---

There's a moment, when you scale a memory-augmented chatbot from a demo to
something real, when it starts confidently telling users things they never
said. The stored history is right there. The retrieval works. The model
picks a chunk and speaks. And what it produces is *technically grounded*
but *materially wrong* — because two chunks disagreed, and the retriever
ranked the one that lost.

That's the moment I stopped believing that memory was a retrieval problem.

## The confusion the industry runs on

"Memory" in most AI stacks today means one of two things:

1. **Rolling context** — dump the last N turns into every prompt.
2. **RAG-as-memory** — chunk the history, embed it, look up top-k on every
   query, prepend it to the prompt.

Both scale poorly for the same reason: the *volume* of retrievable content
grows, but nothing decides what is *true*. Two contradictory chunks live
side by side. The model reads both and picks one — usually the one with
higher embedding similarity to the current query, occasionally the one
that came last, more often the one that sounds most confident. This is
"memory" the way a filing cabinet is a memory: it holds documents. It
doesn't know which document is right.

At some scale, this stops being annoying and starts being expensive. An
assistant that reschedules the wrong meeting because two months ago you
told it Mondays were fine, and last week you said Mondays were bad, and
retrieval surfaced the older statement, is not a memory problem. It is a
*credibility* problem — and no amount of tuning the retriever will fix it,
because the retriever isn't the layer that should be deciding what to
believe.

## The shift: memory as evidence

MemoryOS treats memory as a chain of evidence rather than a chunk to
retrieve. Every stored fact carries three things a chunk doesn't:

- **A source.** Which document, which conversation, which timestamp
  originally produced this claim.
- **A confidence score.** A documented formula, not a vibe — 40%
  corroboration (how many independent origins), 30% recency, 20%
  verification, 10% user confirmation.
- **A verdict on contradictions.** If two facts disagree, they *both*
  stay, and a specialized agent decides what to do.

The point isn't to store more. It's to make the memory *auditable* — every
answer the system gives can be traced back to the events that supported
it. If the confidence is below a policy threshold, the system asks a
clarifying question instead of guessing. If two active facts contradict
each other, the system surfaces the conflict rather than picking one
silently.

That last one is the trick most retrieval systems don't do — because it
requires the memory layer to have opinions about truth, not just about
similarity.

## Four layers, one job

MemoryOS is structured as four layers, each with a specific responsibility:

**Episodic** — raw events, recorded with full provenance and never
interpreted. This is the ground truth. A chat message becomes an event.
A calendar entry becomes an event. Nothing is derived at this layer;
everything is remembered.

**Semantic** — the first opinion. Duplicate facts merge, and their sources
merge with them: five people saying "the user prefers morning meetings"
becomes one fact with five supporting sources. Facts that *disagree* don't
overwrite each other — they coexist as competing values until an auditor
resolves them.

**Pattern** — deterministic scans over episodes. A pattern is promoted to
trusted knowledge only when multiple sourced episodes across multiple
sessions agree. This is where *unprogrammed discovery* happens: nobody told
the system that meetings get rescheduled after long weekends, but four
sourced calendar events across four sessions agreed, so the system noticed.

**Decay** — memory that isn't corroborated fades. Single-source facts have
a six-month half-life; multi-source facts have eighteen months. This is not
a garbage collector — it is the mechanism by which the confidence formula
stays honest as the world changes.

And sitting across all four: an **Evidence Auditor** that runs after every
ingest. It detects contradictions, resolves what evidence can decide (a
sustained challenge from independent sources arriving *after* the
incumbent's last support is a preference change; a single stray claim
already contradicted by newer evidence is noise), and escalates the rest
to the user. When the user answers, their answer becomes the strongest
input in the confidence formula. Losers are superseded, never deleted.

## The proof — an accuracy curve you can reproduce

I built a deterministic eval harness that runs the same twelve decision
tasks after every session, against a seeded synthetic history containing
noise and two genuine preference changes. Ground truth at each session is
what a *correct* memory should believe then — a memory that can't update is
scored wrong.

Session 1: MemoryOS is at 42%. It doesn't have enough evidence yet, so it
asks a lot. Session 20: **100%**, and it acts on 75% of the tasks without
asking. Precision-when-acting across 1,440 decisions on six random seeds:
**1.00**. The acting gate never once fired on a wrong answer. A
last-assertion-wins baseline that just trusts whatever came last
whipsaws on noise, drops to 75% on the same runs, and on two seeds
ends the run *wrong*.

The curve rises because evidence accumulates. The model never changed. The
architecture did the work.

Every number above is reproducible bit-for-bit:

```bash
cd backend
python -m evals.run_eval --sessions 20 --seed 42
```

The harness makes zero LLM calls. It exercises the deterministic memory
dynamics directly.

## But does it work outside your own data?

Fair question. The honest answer is: on public data, MemoryOS is not a
strict superset of RAG — and that's the design intent, not a defeat.

I ran MemoryOS against LongMemEval (ICLR 2025, MIT-licensed, 500 questions
across six memory categories) alongside a vanilla RAG baseline using the
same Qwen embeddings and Qwen answer model on the same data. Any delta
between them is attributable to the fact layer, not retrieval quality.

The stratified 60-instance result:

| Category | MemoryOS | Vanilla RAG | Δ |
|---|---:|---:|---:|
| **knowledge-update** | **100%** | 80% | **+20 pts** |
| **multi-session** | **60%** | 50% | **+10 pts** |
| single-session-user | 100% | 100% | tie |
| temporal-reasoning | 80% | 90% | −10 pts |
| single-session-assistant | 10% | 30% | −20 pts |
| single-session-preference | 40% | 90% | −50 pts |

On the two categories where facts *change* over time — where memory has to
actually work, not just retrieve — MemoryOS wins by margins that matter.
The Evidence Auditor detects the contradiction, prefers the newer sourced
value, and supersedes the older one without deleting the evidence chain.
RAG retrieves both and picks the one whose chunk ranks higher.

On single-session-preference, MemoryOS loses badly. This deserves the
honest reading: those questions are advice-seeking ("I've been feeling
nostalgic — should I attend my high school reunion?"), and RAG's freedom
to confabulate a warm response from adjacent chat history is graded
correct. MemoryOS's discipline — cite what you know, refuse when you don't
— is graded wrong. In benchmark scoring this costs points; in production
this is exactly the failure mode you want to prevent.

The one-sentence positioning I landed on:

> **RAG makes retrieval smarter. MemoryOS makes memory auditable.**

They compose. The interesting question is not "which one wins" but "when
should the system be allowed to act on what it thinks it remembers."

## The engineering that makes it defensible

A few pieces that mattered more than I expected:

**Policy as code.** Confidence thresholds and pattern promotion criteria
live in a YAML file, not in code. Change the acting gate from 0.80 to
0.75, or the pattern promotion bar from three sources to five, and the
behavior changes without a redeploy. Judges and stakeholders can *read*
the policy.

**A fallback chain, not a fallback flag.** Every Qwen call has a documented
fallback: `qwen-plus → qwen-turbo → deterministic rules`. When the primary
fails or times out, the secondary tries. When the secondary fails, the
system honestly defers — extraction returns no assertions rather than
guessing. With zero working API keys, MemoryOS still records every event
episodically, keeps every confidence score correct, and answers questions
from the deterministic engine. The slow path is optional for reasoning; the
fast path is load-bearing.

**A measured 80/20.** On a live 20-session state with one question asked,
the dashboard shows 725 deterministic operations vs 2 Qwen calls —
**99.6% fast-path**. This is a counter, not a slogan. Every avoided call is
a token nobody is paying for.

**Deploy proof by construction.** The same containers that run locally
run on Alibaba Cloud ECS with only environment variables changing. There
is no "prod version." The live instance at http://8.219.249.248 is the
same code you can clone and start with `docker compose up`.

## What I didn't build

A memory system is a design opinion, and choosing what to include is half
the work. Things I deliberately left out:

- **A vector database as a product.** pgvector is a component here, not a
  headline. The fact-layer opinions matter more than the storage.
- **Agent orchestration.** MemoryOS is a memory system, not a chat
  framework. It has an HTTP API and an SSE event bus; use it inside
  whatever agent runtime you like.
- **Multi-tenancy at scale.** Prototype scope, documented as such. A
  production version would isolate subjects across tenants and add rate
  limiting on ingest.

## The take-away

The instinct in AI systems is to reach for more capable retrieval or a
larger model when memory feels flaky. Both of those help, but neither of
them can decide what is *true*. They can only decide what is *available*.

Building MemoryOS taught me that memory credibility is a system-design
problem, not a model-capacity problem. Once you commit to that view, the
architecture almost writes itself: sourced facts, a confidence formula,
policy-gated actions, an auditor for contradictions, and a slow path only
for the parts that genuinely need reasoning. The result is a system that
gets *more* trustworthy as it grows — the opposite of the failure mode
retrieval-only memory suffers.

MemoryOS is open source (MIT) at
[github.com/Mdia92/memoryos](https://github.com/Mdia92/memoryos). Everything
in this post is reproducible from the repo. The live instance is at
http://8.219.249.248.

*Built for the Qwen Cloud Global AI Hackathon, MemoryAgent track.*
