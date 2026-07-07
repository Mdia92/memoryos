"use client";

// Dashboard: the accuracy-over-sessions curve (the thesis on screen),
// KPI strip, and discovered patterns.

import { useCallback, useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type EvalRun, type Pattern, type Stats } from "@/lib/api";
import { Kpi, SectionTitle } from "@/components/ui";

const pct = (v: number) => `${Math.round(v * 100)}%`;

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-xs">
      <div className="mb-1 font-semibold">Session {label}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="size-2 rounded-full" style={{ background: p.color }} />
          <span className="text-muted">{p.name}</span>
          <span className="mono ml-auto tabular-nums">{pct(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [run, setRun] = useState<EvalRun | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api.evalLatest().then(setRun).catch(() => setRun(null));
    api.stats().then(setStats).catch(() => {});
    api.patterns().then(setPatterns).catch(() => {});
  }, []);

  useEffect(refresh, [refresh]);

  const runEval = async () => {
    setRunning(true);
    setError(null);
    try {
      await api.evalRun(20, 42);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  const rows = run?.results.sessions ?? [];
  const summary = run?.results.summary;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">
            AI shouldn&apos;t remember more. It should remember correctly.
          </h1>
          <p className="mt-1 text-sm text-muted">
            The same 12 decision tasks, asked after every session. Accuracy rises because
            evidence accumulates — not because the model changed.
          </p>
        </div>
        <button
          onClick={runEval}
          disabled={running}
          className="rounded-lg border border-accent/40 bg-accent/10 px-3.5 py-2 text-xs font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-50"
        >
          {running ? "Running 20 sessions…" : "Run evaluation"}
        </button>
      </header>

      {error ? (
        <div className="card border-danger/40 px-4 py-3 text-xs text-danger">{error}</div>
      ) : null}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
        <Kpi
          label="Accuracy s1 → s20"
          value={
            summary ? `${pct(summary.memoryos_first)} → ${pct(summary.memoryos_last)}` : "—"
          }
          tone="accent"
        />
        <Kpi
          label="Precision when acting"
          value={
            summary?.mean_precision_when_acting != null
              ? pct(summary.mean_precision_when_acting)
              : "—"
          }
          tone="accent"
        />
        <Kpi label="Active facts" value={stats?.facts_active ?? "—"} />
        <Kpi
          label="Corroborated"
          value={stats ? pct(stats.pct_corroborated) : "—"}
          tone="info"
        />
        <Kpi
          label="Conflicts resolved"
          value={stats?.contradictions_resolved ?? "—"}
          tone="warn"
        />
        <Kpi
          label="Patterns discovered"
          value={stats?.patterns_promoted ?? "—"}
          tone="default"
        />
      </div>

      <section className="card p-5">
        <SectionTitle sub="MemoryOS vs last-assertion-wins baseline on an identical, seeded synthetic dataset — 12 tasks per session, ground truth includes two mid-run preference changes.">
          Decision accuracy across sessions
        </SectionTitle>
        {rows.length ? (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
              <CartesianGrid stroke="#1c2330" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="session"
                tick={{ fill: "#8b94a7", fontSize: 11 }}
                stroke="#232a37"
                label={{ value: "session", fill: "#8b94a7", fontSize: 11, dy: 14 }}
              />
              <YAxis
                domain={[0, 1]}
                tickFormatter={pct}
                tick={{ fill: "#8b94a7", fontSize: 11 }}
                stroke="#232a37"
              />
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12, color: "#8b94a7" }} />
              <Line
                name="MemoryOS"
                dataKey="memoryos_accuracy"
                stroke="var(--accent)"
                strokeWidth={2.5}
                dot={false}
                type="monotone"
              />
              <Line
                name="Baseline (last wins)"
                dataKey="baseline_accuracy"
                stroke="var(--info)"
                strokeWidth={1.5}
                strokeDasharray="5 4"
                dot={false}
                type="monotone"
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-48 items-center justify-center text-sm text-muted">
            No evaluation run yet — press “Run evaluation”.
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card p-5">
          <SectionTitle sub="How often confidence cleared the acting gate (≥ 80%) — earned trust, session by session.">
            Act rate: confidence is earned
          </SectionTitle>
          {rows.length ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -18 }}>
                <CartesianGrid stroke="#1c2330" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="session"
                  tick={{ fill: "#8b94a7", fontSize: 11 }}
                  stroke="#232a37"
                />
                <YAxis
                  domain={[0, 1]}
                  tickFormatter={pct}
                  tick={{ fill: "#8b94a7", fontSize: 11 }}
                  stroke="#232a37"
                />
                <Tooltip content={<ChartTooltip />} />
                <Area
                  name="Act rate"
                  dataKey="act_rate"
                  stroke="var(--accent)"
                  fill="rgba(52,211,153,0.12)"
                  strokeWidth={2}
                  type="monotone"
                />
                <Area
                  name="Ask rate"
                  dataKey="ask_rate"
                  stroke="var(--danger)"
                  fill="rgba(248,113,113,0.08)"
                  strokeWidth={1.5}
                  type="monotone"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-40 items-center justify-center text-sm text-muted">
              Run the evaluation to populate.
            </div>
          )}
        </section>

        <section className="card p-5">
          <SectionTitle sub="Behavioral knowledge nobody stated — promoted only after enough sourced episodes agree.">
            Unprogrammed discoveries
          </SectionTitle>
          {patterns.length ? (
            <ul className="space-y-3">
              {patterns.map((p) => (
                <li key={p.id} className="rounded-lg border border-line bg-panel-2 px-3.5 py-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`mono rounded-md border px-1.5 py-0.5 text-[10px] font-semibold tracking-wider ${
                        p.promoted
                          ? "border-violet/40 bg-violet/10 text-violet"
                          : "border-line text-muted"
                      }`}
                    >
                      {p.promoted ? "PROMOTED" : "CANDIDATE"}
                    </span>
                    <span className="mono text-xs text-muted">{p.name}</span>
                  </div>
                  <p className="mt-1.5 text-sm">{p.description}</p>
                  <p className="mono mt-1 text-[11px] text-muted">
                    {p.support} supporting episodes across sessions {p.sessions.join(", ")}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex h-40 items-center justify-center text-center text-sm text-muted">
              No patterns yet — seed the memory from the Ask page,
              <br />
              or run the evaluation.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
