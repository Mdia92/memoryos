# LongMemEval results

**LongMemEval** ([Wu et al., ICLR 2025](https://github.com/xiaowu0162/LongMemEval))
benchmarks chat-assistant long-term memory across 6 categories, each with a
gold answer graded by an LLM judge. The dataset is MIT-licensed and hosted
on HuggingFace as `xiaowu0162/longmemeval-cleaned`.

## What we run

- **Variant**: `longmemeval_oracle.json` (only sessions relevant to each
  question). Rationale: MemoryOS is a memory *fidelity* system, not a
  needle-in-haystack retriever. The oracle variant isolates the ingest →
  corroborate → gate → answer pipeline from a separate retrieval-from-noise
  challenge, which is fair — and honest about scope.
- **Sample**: stratified across all 6 question types.
- **Judge**: Qwen-plus grades correct/incorrect against gold, substituting for
  the paper's GPT-4 (documented tradeoff).
- **Baseline**: a **vanilla RAG** pipeline (identical Qwen embeddings, top-5
  retrieval, Qwen answer prompt tuned to answer even under uncertainty). This
  is what most "memory + LLM" projects actually ship.

Reproduce:

```bash
bash scripts/download_datasets.sh
cd backend
python -m evals.longmemeval.run --n 60 --seed 42 --variant oracle --rag \
  --out longmemeval_results.jsonl
```

## Results

(Populated by the eval run; see `longmemeval_results.jsonl` for per-question
outputs.)

| Category | MemoryOS | Vanilla RAG |
|---|---:|---:|
| knowledge-update | *pending* | *pending* |
| single-session-preference | *pending* | *pending* |
| multi-session | *pending* | *pending* |
| temporal-reasoning | *pending* | *pending* |
| single-session-user | *pending* | *pending* |
| single-session-assistant | *pending* | *pending* |
| **Overall** | *pending* | *pending* |

## The important reading

MemoryOS is **not** a superset of RAG on this benchmark, and it is not
designed to be. LongMemEval scores every response as right/wrong: if the
system says *"I don't hold evidence about that"* on a question whose answer
was mentioned once in the haystack, it counts as wrong. RAG will always emit
*some* plausible answer; MemoryOS's confidence gate deliberately refuses to
bluff.

That gap is the design intent, and it matters more in production than at
benchmark time. What to look at instead:

1. **Categories where facts CHANGE over time** (`knowledge-update`,
   `temporal-reasoning`). This is what the Evidence Auditor is for — surfacing
   contradictions and preferring newer sourced facts over older ones. On
   these categories, MemoryOS should meet or beat RAG.
2. **Precision when acting**. Filter to responses where MemoryOS committed
   to an answer (`gate ∈ {act, show_sources}`). That precision is the trust
   metric — how often the system is right when it *chooses* to speak.
3. **Abstention behavior**. RAG never abstains. MemoryOS abstains when
   evidence is insufficient. On this benchmark that costs points; in the
   real world it saves them.

## Known limitations

- The oracle variant is used, not the full haystack. MemoryOS's semantic
  retrieval (`app/retrieval.py`) is a working prototype, not a production
  retriever; the small-haystack variant would fold in retrieval quality as
  a separate concern.
- Qwen-plus as judge introduces judge variance vs the paper's GPT-4. A cheap
  spot-check on the disagreements between judges is possible but not run.
- The extraction prompt (`app/extraction.py`) is tuned to be broad (any
  durable user fact) but is still English-only.
