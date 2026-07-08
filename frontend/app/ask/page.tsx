"use client";

// The demo moment: ask the memory a question and compare MemoryOS
// (sourced, gated, confident) with a traditional last-wins memory.
// Also hosts the session-seeding controls for the cross-session story.

import { useState } from "react";
import { api, type AskResponse } from "@/lib/api";
import {
  ConfidenceBar,
  EvidenceList,
  GateBadge,
  SectionTitle,
} from "@/components/ui";

const SAMPLE_QUESTIONS = [
  "Does the user prefer morning or afternoon meetings?",
  "Where should I send notifications?",
  "What format should the quarterly report use?",
  "Does the user prefer remote or office meetings?",
];

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [seeding, setSeeding] = useState<number | null>(null);
  const [seedInfo, setSeedInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ask = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setResponse(await api.ask(q));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const seed = async (sessions: number) => {
    setSeeding(sessions);
    setError(null);
    try {
      const r = await api.demoSeed(sessions);
      setSeedInfo(
        `Replayed ${r.sessions} sessions — ${r.events} events, ${r.facts_active} active facts.`,
      );
      setResponse(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSeeding(null);
    }
  };

  const d = response?.decision;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-lg font-semibold tracking-tight">Ask the memory</h1>
        <p className="mt-1 text-sm text-muted">
          One question, two memories: a traditional assistant guesses fluently; MemoryOS
          answers with confidence it can prove.
        </p>
      </header>

      <section className="card p-4">
        <SectionTitle sub="Replay the synthetic enterprise history (clearly labeled synthetic) — a young memory asks, a mature one acts.">
          Cross-session story
        </SectionTitle>
        <div className="flex flex-wrap items-center gap-2">
          {[3, 10, 20].map((n) => (
            <button
              key={n}
              onClick={() => seed(n)}
              disabled={seeding !== null}
              className="rounded-lg border border-line bg-panel-2 px-3 py-2 text-xs font-medium transition-colors hover:border-accent/40 hover:text-accent disabled:opacity-50"
            >
              {seeding === n ? "Seeding…" : `Seed ${n} sessions`}
            </button>
          ))}
          <button
            onClick={() => api.demoReset().then(() => setSeedInfo("Memory wiped."))}
            className="rounded-lg border border-line px-3 py-2 text-xs text-muted transition-colors hover:border-danger/40 hover:text-danger"
          >
            Reset
          </button>
          {seedInfo ? <span className="text-xs text-muted">{seedInfo}</span> : null}
        </div>
      </section>

      <section className="space-y-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(question);
          }}
          className="flex gap-2"
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="What does the system know about my meeting preferences?"
            className="card w-full px-4 py-3 text-sm outline-none transition-colors placeholder:text-muted focus:border-accent/50"
          />
          <button
            type="submit"
            disabled={loading}
            className="shrink-0 rounded-lg border border-accent/40 bg-accent/10 px-4 text-sm font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-50"
          >
            {loading ? "…" : "Ask"}
          </button>
        </form>
        <div className="flex flex-wrap gap-2">
          {SAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => {
                setQuestion(q);
                ask(q);
              }}
              className="rounded-full border border-line px-3 py-1 text-[11px] text-muted transition-colors hover:border-accent/40 hover:text-ink"
            >
              {q}
            </button>
          ))}
        </div>
      </section>

      {error ? (
        <div className="card border-danger/40 px-4 py-3 text-xs text-danger">{error}</div>
      ) : null}

      {response ? (
        <div className="animate-slide-in grid gap-4 lg:grid-cols-2">
          <section className="card border-line p-5 opacity-80">
            <div className="mb-3 flex items-center gap-2">
              <h3 className="text-sm font-semibold text-muted">Traditional memory</h3>
              <span className="mono rounded-md border border-line px-1.5 py-0.5 text-[10px] text-muted">
                LAST ASSERTION WINS
              </span>
            </div>
            <p className="text-sm leading-relaxed">
              {response.baseline?.answer ?? "I don't know."}
            </p>
            <ul className="mono mt-4 space-y-1 text-[11px] text-muted">
              <li>· no sources</li>
              <li>· no confidence</li>
              <li>· never doubts itself</li>
              {response.baseline?.source ? (
                <li>
                  · silently trusted one {response.baseline.source.origin} event from{" "}
                  {new Date(response.baseline.source.occurred_at).toLocaleDateString()}
                </li>
              ) : null}
              {response.path === "hybrid-retrieval" && !response.baseline ? (
                <li>· no tracked key — this baseline is only defined for tracked facts</li>
              ) : null}
            </ul>
          </section>

          <section className="card border-accent/25 p-5">
            <div className="mb-3 flex items-center gap-2">
              <h3 className="text-sm font-semibold">MemoryOS</h3>
              {d ? <GateBadge gate={d.gate} /> : null}
              {response.path ? (
                <span className="mono rounded-md border border-line bg-panel-2 px-1.5 py-0.5 text-[10px] text-muted">
                  {response.path}
                </span>
              ) : null}
              {response.providers.answer ? (
                <span className="mono ml-auto text-[10px] text-muted">
                  {response.providers.answer}
                </span>
              ) : null}
            </div>
            <p className="text-sm leading-relaxed">{response.answer}</p>
            {d ? (
              <div className="mt-4 space-y-4">
                {d.confidence !== null ? (
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted">Confidence</span>
                    <ConfidenceBar value={d.confidence} />
                    {d.key ? (
                      <span className="mono ml-auto text-[11px] text-muted">{d.key}</span>
                    ) : null}
                  </div>
                ) : (
                  <div className="flex items-center gap-3 text-xs text-muted">
                    <span>Answered from retrieved events (no tracked fact yet)</span>
                  </div>
                )}
                {d.competing_values?.length ? (
                  <div className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-xs">
                    <span className="font-semibold text-danger">Contradiction on file: </span>
                    {d.competing_values.map((cv) => (
                      <span key={cv.value} className="text-muted">
                        “{cv.value}” at {Math.round(cv.confidence * 100)}% ({cv.sources}{" "}
                        sources)
                      </span>
                    ))}
                  </div>
                ) : null}
                {d.evidence.length ? (
                  <div>
                    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                      Evidence ({d.evidence.length})
                    </h4>
                    <EvidenceList sources={d.evidence.slice(0, 5)} />
                  </div>
                ) : null}
                <p className="mono border-t border-line pt-2.5 text-[11px] text-muted">
                  {d.reason}
                </p>
              </div>
            ) : null}
          </section>
        </div>
      ) : null}
    </div>
  );
}
