"use client";

// Memory browser: every fact with its full evidence chain and the
// term-by-term confidence breakdown — the score is recomputable by hand.

import { useEffect, useState } from "react";
import { api, type Fact } from "@/lib/api";
import {
  ConfidenceBar,
  EvidenceList,
  GateBadge,
  SectionTitle,
  VerificationBadge,
} from "@/components/ui";

const TERM_LABELS: Record<string, string> = {
  corroboration: "Corroboration",
  recency: "Recency",
  verification: "Verification",
  user_confirmation: "User confirmation",
};

function gateOf(confidence: number): "act" | "show_sources" | "ask" {
  if (confidence >= 0.8) return "act";
  if (confidence >= 0.4) return "show_sources";
  return "ask";
}

function FactCard({ fact }: { fact: Fact }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`card card-hover ${fact.active ? "" : "opacity-55"}`}>
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-sm font-medium">{fact.statement}</span>
            {fact.stale ? (
              <span className="mono rounded-md border border-warn/40 bg-warn/10 px-1.5 py-0.5 text-[10px] text-warn">
                STALE
              </span>
            ) : null}
            {!fact.active ? (
              <span className="mono rounded-md border border-line px-1.5 py-0.5 text-[10px] text-muted">
                SUPERSEDED
              </span>
            ) : null}
            {fact.user_confirmation === "confirmed" ? (
              <span className="mono rounded-md border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent">
                USER CONFIRMED
              </span>
            ) : null}
          </div>
          <div className="mono mt-1 flex flex-wrap items-center gap-3 text-[11px] text-muted">
            <span>{fact.key}</span>
            <span>
              {fact.sources.length} sources · {fact.breakdown.independent_origins} independent
            </span>
            <VerificationBadge status={fact.verification} />
          </div>
        </div>
        <GateBadge gate={gateOf(fact.confidence)} />
        <ConfidenceBar value={fact.confidence} />
        <span className="mono text-xs text-muted">{open ? "−" : "+"}</span>
      </button>
      {open ? (
        <div className="animate-slide-in grid gap-5 border-t border-line px-4 py-4 md:grid-cols-2">
          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
              Evidence chain
            </h4>
            <EvidenceList sources={fact.sources} />
          </div>
          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
              Confidence breakdown
            </h4>
            <table className="w-full text-xs">
              <tbody>
                {Object.entries(fact.breakdown.terms).map(([name, t]) => (
                  <tr key={name} className="border-b border-line/50 last:border-0">
                    <td className="py-1.5 text-muted">{TERM_LABELS[name] ?? name}</td>
                    <td className="mono py-1.5 text-right tabular-nums text-muted">
                      {t.score.toFixed(2)} × {t.weight}
                    </td>
                    <td className="mono w-14 py-1.5 text-right tabular-nums">
                      {t.weighted.toFixed(3)}
                    </td>
                  </tr>
                ))}
                <tr>
                  <td className="py-1.5 font-semibold">Confidence</td>
                  <td />
                  <td className="mono py-1.5 text-right font-semibold tabular-nums">
                    {fact.breakdown.confidence.toFixed(3)}
                  </td>
                </tr>
              </tbody>
            </table>
            <p className="mt-2 text-[11px] leading-relaxed text-muted">
              40% corroboration · 30% recency · 20% verification · 10% user confirmation —
              every term is observable in the evidence chain.
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}

type SortBy = "confidence" | "recent" | "sources" | "key";

function sortFacts(facts: Fact[], by: SortBy): Fact[] {
  const copy = [...facts];
  switch (by) {
    case "confidence":
      return copy.sort((a, b) => b.confidence - a.confidence);
    case "sources":
      return copy.sort((a, b) => b.sources.length - a.sources.length);
    case "recent":
      return copy.sort((a, b) => {
        const aT = a.last_supported ? new Date(a.last_supported).getTime() : 0;
        const bT = b.last_supported ? new Date(b.last_supported).getTime() : 0;
        return bT - aT;
      });
    case "key":
      return copy.sort((a, b) => a.key.localeCompare(b.key));
  }
}

function FactSkeleton() {
  return (
    <div className="card animate-pulse px-4 py-3">
      <div className="h-4 w-2/3 rounded bg-panel-2" />
      <div className="mt-2 h-3 w-1/3 rounded bg-panel-2" />
    </div>
  );
}

export default function MemoryPage() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("confidence");

  useEffect(() => {
    setLoaded(false);
    api
      .facts(showAll)
      .then(setFacts)
      .catch(() => setFacts([]))
      .finally(() => setLoaded(true));
  }, [showAll]);

  const q = query.trim().toLowerCase();
  const filtered = q
    ? facts.filter(
        (f) =>
          f.statement.toLowerCase().includes(q) ||
          f.key.toLowerCase().includes(q) ||
          f.value.toLowerCase().includes(q),
      )
    : facts;
  const ordered = sortFacts(filtered, sortBy);

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Semantic memory</h1>
          <p className="mt-1 text-sm text-muted">
            Deduplicated facts with merged evidence. Nothing here is trusted without a source.
          </p>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-muted">
          <input
            type="checkbox"
            checked={showAll}
            onChange={(e) => setShowAll(e.target.checked)}
            className="accent-[var(--accent)]"
          />
          include superseded
        </label>
      </header>

      {loaded && facts.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by key, value, or statement…"
            className="card min-w-[220px] flex-1 px-3 py-2 text-xs outline-none transition-colors placeholder:text-muted focus:border-accent/50"
          />
          <div className="flex items-center gap-1 text-[11px] text-muted">
            <span>Sort:</span>
            {(["confidence", "recent", "sources", "key"] as SortBy[]).map((s) => (
              <button
                key={s}
                onClick={() => setSortBy(s)}
                className={`mono rounded-md border px-2 py-0.5 transition-colors ${
                  sortBy === s
                    ? "border-accent/40 bg-accent/10 text-accent"
                    : "border-line hover:border-accent/30"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <span className="mono ml-auto text-[11px] text-muted">
            {ordered.length} of {facts.length}
          </span>
        </div>
      ) : null}

      {!loaded ? (
        <div className="space-y-2.5">
          <FactSkeleton />
          <FactSkeleton />
          <FactSkeleton />
        </div>
      ) : ordered.length ? (
        <div className="space-y-2.5">
          {ordered.map((f) => (
            <FactCard key={f.id} fact={f} />
          ))}
        </div>
      ) : facts.length ? (
        <div className="card px-5 py-10 text-center text-sm text-muted">
          No facts match &ldquo;{query}&rdquo;. Try a different search or clear the filter.
        </div>
      ) : (
        <div className="card px-5 py-10 text-center text-sm text-muted">
          Memory is empty — seed it from the Ask page or ingest events via the API.
        </div>
      )}

      {ordered.length ? (
        <div className="pb-4 pt-1">
          <SectionTitle>Reading the ledger</SectionTitle>
          <ul className="grid gap-2 text-xs text-muted md:grid-cols-3">
            <li className="card px-3 py-2.5">
              <span className="text-accent">ACT</span> — confidence ≥ 80%: the agent may act
              autonomously on this memory.
            </li>
            <li className="card px-3 py-2.5">
              <span className="text-warn">SHOW SOURCES</span> — 40–80%: it answers, but always
              surfaces the evidence.
            </li>
            <li className="card px-3 py-2.5">
              <span className="text-danger">ASK</span> — below 40% (or ambiguous): it asks
              instead of guessing.
            </li>
          </ul>
        </div>
      ) : null}
    </div>
  );
}
