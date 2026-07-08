# Why not just use RAG / Mem0 / LangGraph?

A common question when judges look at a memory-agent project. The honest
answer: those solve different problems, and MemoryOS complements rather than
replaces the ones that ship.

## Vanilla RAG (chunk + embed + retrieve + prompt)

**What it does well.** Answering questions whose answer is *in the corpus*
somewhere. Fast to build. Cheap at prototype scale.

**Where it fails.** Retrieval is a similarity ranking, not a truth ranking.
When the same fact was said twice and later updated, RAG shows both and lets
the model pick — usually by embedding rank, occasionally correctly. When a
fact was never in the corpus, RAG confabulates a plausible answer from
adjacent context. When two chunks disagree, RAG doesn't notice.

**MemoryOS's answer.** On the LongMemEval `knowledge-update` category (78
questions where a fact is stated then updated), MemoryOS scores **100% vs
RAG's 80%** on our stratified sample — using the same Qwen embeddings and
the same Qwen answer model. The delta comes entirely from the fact layer:
the Evidence Auditor detects the contradiction, prefers the newer sourced
value, and supersedes the older one without deleting the evidence chain.
Full per-category breakdown: [longmemeval-results.md](longmemeval-results.md).

MemoryOS *includes* a RAG-style path (`app/retrieval.py`) as its hybrid
fallback for questions with no tracked key. The point is that RAG is a
component of a memory system, not the whole thing.

## Mem0

**What it does well.** Turns raw chat history into structured user
preferences. LangChain-friendly. Good for adding "memory" to an existing
chatbot.

**Where MemoryOS is different.** Mem0 stores extracted facts; it does not
audit them. If two sessions produce conflicting facts, Mem0 keeps the
newer one (or both, depending on config). MemoryOS keeps *both with their
sources*, promotes the challenger only when timeline-aware evidence rules
say the challenger is a preference change and not noise, and never deletes
a superseded value — it can be revived if the world reasserts it.

MemoryOS also carries a documented confidence formula and policy-as-code
gates. Mem0's confidence, when present, is per-implementation.

## LangGraph, LangMem, LlamaIndex Memory

**What they do well.** Framework-level plumbing for memory in agentic apps.
Great when you're already inside those ecosystems.

**Where MemoryOS is different.** They give you a graph and hooks; you still
have to define what "memory" *is*. MemoryOS is a specific opinion about the
data model: four layers, sourced facts, deterministic dynamics, a formula
you can hand-verify. It sits at a different level of the stack — you could
build MemoryOS *inside* LangGraph if you wanted. The interesting engineering
work (auditor, confidence math, decay tuning) doesn't come from the
framework.

## What MemoryOS is NOT

- **A vector database.** pgvector is a component, not a product.
- **A chat framework.** No agent orchestration, no tool router. The
  four-layer memory + auditor are self-contained.
- **A production identity/multi-tenant system.** Prototype scope. See the
  "Prototype scope" section in the README.

## The one-sentence positioning

> RAG makes retrieval smarter. MemoryOS makes memory *auditable*.

Both are useful. They compose. The right question isn't "which one wins" —
it's "when do you trust a system to act on what it remembers?" The
confidence gate and the evidence chain are how MemoryOS earns that trust
by construction rather than by prompt engineering.
