"use client";

// The Evidence Auditor feed: contradictions (open → resolve), the
// human-in-the-loop clarification flow, and the append-only audit trail.

import { useCallback, useEffect, useState } from "react";
import { api, type AuditEntry, type Contradiction } from "@/lib/api";
import { ConfidenceBar, SectionTitle } from "@/components/ui";
import { useStream } from "@/lib/useStream";

function SideCard({
  side,
  chosen,
  onChoose,
  resolving,
}: {
  side: { id: string; value: string; confidence: number; sources: number; active: boolean };
  chosen: boolean;
  onChoose?: () => void;
  resolving: boolean;
}) {
  return (
    <div
      className={`flex-1 rounded-lg border px-3.5 py-3 ${
        chosen ? "border-accent/50 bg-accent/5" : side.active ? "border-line bg-panel-2" : "border-line bg-panel-2 opacity-50"
      }`}
    >
      <div className="text-sm font-semibold">“{side.value}”</div>
      <div className="mono mt-1 text-[11px] text-muted">{side.sources} sources</div>
      <div className="mt-2">
        <ConfidenceBar value={side.confidence} small />
      </div>
      {onChoose ? (
        <button
          onClick={onChoose}
          disabled={resolving}
          className="mt-3 w-full rounded-md border border-accent/40 bg-accent/10 px-2 py-1.5 text-[11px] font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-50"
        >
          This is correct
        </button>
      ) : null}
    </div>
  );
}

function ContradictionCard({
  c,
  onResolved,
}: {
  c: Contradiction;
  onResolved: () => void;
}) {
  const [resolving, setResolving] = useState(false);
  const open = c.status === "open";
  const statusTone =
    c.status === "open"
      ? "border-danger/40 bg-danger/10 text-danger"
      : c.status === "resolved_by_user"
        ? "border-accent/40 bg-accent/10 text-accent"
        : "border-line bg-panel-2 text-muted";

  const choose = async (factId: string) => {
    setResolving(true);
    try {
      await api.resolveContradiction(c.id, factId);
      onResolved();
    } finally {
      setResolving(false);
    }
  };

  return (
    <div className="card animate-slide-in p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`mono rounded-md border px-1.5 py-0.5 text-[10px] font-semibold tracking-wider ${statusTone}`}
        >
          {c.status.replaceAll("_", " ").toUpperCase()}
        </span>
        <span className="mono text-xs text-muted">{c.key}</span>
        <span className="mono ml-auto text-[11px] text-muted">
          {new Date(c.detected_at).toLocaleString()}
        </span>
      </div>
      {open ? (
        <p className="mt-2 text-sm text-muted">
          Conflicting evidence — the auditor cannot decide from evidence alone. Which is
          correct?
        </p>
      ) : null}
      <div className="mt-3 flex flex-col gap-3 sm:flex-row">
        {c.fact_a ? (
          <SideCard
            side={c.fact_a}
            chosen={!open && c.fact_a.active}
            onChoose={open ? () => choose(c.fact_a!.id) : undefined}
            resolving={resolving}
          />
        ) : null}
        <div className="mono self-center text-xs text-muted">vs</div>
        {c.fact_b ? (
          <SideCard
            side={c.fact_b}
            chosen={!open && c.fact_b.active}
            onChoose={open ? () => choose(c.fact_b!.id) : undefined}
            resolving={resolving}
          />
        ) : null}
      </div>
      {c.resolution ? (
        <p className="mono mt-3 border-t border-line pt-2.5 text-[11px] leading-relaxed text-muted">
          ⚖ {c.resolution}
        </p>
      ) : null}
    </div>
  );
}

const ACTOR_COLORS: Record<string, string> = {
  auditor: "var(--danger)",
  verifier: "var(--accent)",
  semantic: "var(--info)",
  episodic: "var(--muted)",
  pattern: "var(--violet)",
  decay: "var(--warn)",
  user: "#e7ebf2",
};

export default function AuditorPage() {
  const [contradictions, setContradictions] = useState<Contradiction[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);

  const refresh = useCallback(() => {
    api.contradictions().then(setContradictions).catch(() => {});
    api.audit(80).then(setAudit).catch(() => {});
  }, []);

  useEffect(refresh, [refresh]);
  useStream(refresh);

  const open = contradictions.filter((c) => c.status === "open");
  const closed = contradictions.filter((c) => c.status !== "open");

  return (
    <div className="mx-auto max-w-6xl">
      <header className="mb-5">
        <h1 className="text-lg font-semibold tracking-tight">Evidence Auditor</h1>
        <p className="mt-1 text-sm text-muted">
          Never trust memory without checking the evidence. Contradictions the evidence can
          decide are resolved autonomously; the rest escalate to you.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <section>
            <SectionTitle
              sub={
                open.length
                  ? "The agent asks instead of guessing — your confirmation becomes the strongest evidence."
                  : "Nothing needs you right now."
              }
            >
              Needs clarification ({open.length})
            </SectionTitle>
            <div className="space-y-3">
              {open.map((c) => (
                <ContradictionCard key={c.id} c={c} onResolved={refresh} />
              ))}
              {!open.length ? (
                <div className="card px-5 py-8 text-center text-sm text-muted">
                  No open contradictions.
                </div>
              ) : null}
            </div>
          </section>

          <section>
            <SectionTitle sub="Losers are superseded, never deleted — the full history stays auditable.">
              Resolved by evidence ({closed.length})
            </SectionTitle>
            <div className="space-y-3">
              {closed.slice(0, 8).map((c) => (
                <ContradictionCard key={c.id} c={c} onResolved={refresh} />
              ))}
              {!closed.length ? (
                <div className="card px-5 py-8 text-center text-sm text-muted">
                  No contradictions resolved yet.
                </div>
              ) : null}
            </div>
          </section>
        </div>

        <aside>
          <SectionTitle sub="Every state change, in order, with its actor.">
            Audit trail
          </SectionTitle>
          <div className="card max-h-[70vh] space-y-0 overflow-y-auto p-3">
            {audit.map((a, i) => (
              <div
                key={`${a.ts}-${i}`}
                className="border-b border-line/50 py-2 text-[11px] last:border-0"
              >
                <div className="flex items-center gap-2">
                  <span
                    className="mono font-semibold"
                    style={{ color: ACTOR_COLORS[a.actor] ?? "var(--muted)" }}
                  >
                    {a.actor}
                  </span>
                  <span className="mono text-muted">{a.action}</span>
                  <span className="mono ml-auto text-[10px] text-muted">
                    {new Date(a.ts).toLocaleTimeString()}
                  </span>
                </div>
                {"key" in a.detail && typeof a.detail.key === "string" ? (
                  <div className="mono mt-0.5 text-[10px] text-muted">{a.detail.key}</div>
                ) : null}
              </div>
            ))}
            {!audit.length ? (
              <div className="py-8 text-center text-xs text-muted">Audit log is empty.</div>
            ) : null}
          </div>
        </aside>
      </div>
    </div>
  );
}
