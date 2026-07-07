"use client";

// Small shared UI atoms: gate badges, confidence bars, origin chips.

export function GateBadge({ gate }: { gate: "act" | "show_sources" | "ask" | string }) {
  const map: Record<string, { label: string; cls: string }> = {
    act: { label: "ACT", cls: "text-accent border-accent/40 bg-accent/10" },
    show_sources: { label: "SHOW SOURCES", cls: "text-warn border-warn/40 bg-warn/10" },
    ask: { label: "ASK", cls: "text-danger border-danger/40 bg-danger/10" },
  };
  const m = map[gate] ?? { label: gate.toUpperCase(), cls: "text-muted border-line bg-panel-2" };
  return (
    <span
      className={`mono inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-semibold tracking-wider ${m.cls}`}
    >
      {m.label}
    </span>
  );
}

export function VerificationBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    verified: { label: "✓ verified", cls: "text-accent" },
    unverified: { label: "unverified", cls: "text-muted" },
    failed: { label: "✕ failed verification", cls: "text-danger" },
  };
  const m = map[status] ?? { label: status, cls: "text-muted" };
  return <span className={`mono text-[11px] ${m.cls}`}>{m.label}</span>;
}

export function ConfidenceBar({ value, small }: { value: number; small?: boolean }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.8 ? "var(--accent)" : value >= 0.4 ? "var(--warn)" : "var(--danger)";
  return (
    <div className="flex items-center gap-2">
      <div
        className={`${small ? "w-16" : "w-24"} h-1.5 overflow-hidden rounded-full bg-[#1c2330]`}
      >
        <div
          className="h-full rounded-full transition-[width] duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="mono text-xs tabular-nums" style={{ color }}>
        {pct}%
      </span>
    </div>
  );
}

const ORIGIN_COLORS: Record<string, string> = {
  calendar: "var(--info)",
  email: "var(--violet)",
  note: "var(--warn)",
  task: "var(--accent)",
  chat: "#f472b6",
  user: "#e7ebf2",
};

export function OriginChip({ origin }: { origin: string }) {
  const color = ORIGIN_COLORS[origin] ?? "var(--muted)";
  return (
    <span
      className="mono inline-flex items-center gap-1 rounded-md border border-line bg-panel-2 px-1.5 py-0.5 text-[10px]"
      style={{ color }}
    >
      <span className="size-1.5 rounded-full" style={{ background: color }} />
      {origin}
    </span>
  );
}

export function SectionTitle({
  children,
  sub,
}: {
  children: React.ReactNode;
  sub?: React.ReactNode;
}) {
  return (
    <div className="mb-3">
      <h2 className="text-sm font-semibold tracking-wide text-ink">{children}</h2>
      {sub ? <p className="mt-0.5 text-xs text-muted">{sub}</p> : null}
    </div>
  );
}

export function Kpi({
  label,
  value,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  tone?: "accent" | "warn" | "danger" | "info" | "default";
}) {
  const colors: Record<string, string> = {
    accent: "text-accent",
    warn: "text-warn",
    danger: "text-danger",
    info: "text-info",
    default: "text-ink",
  };
  return (
    <div className="card px-4 py-3">
      <div className="text-[11px] uppercase tracking-wider text-muted">{label}</div>
      <div className={`mt-1 text-xl font-semibold tabular-nums ${colors[tone ?? "default"]}`}>
        {value}
      </div>
    </div>
  );
}

export function EvidenceList({
  sources,
}: {
  sources: { event_id: string; origin: string; occurred_at: string; excerpt: string }[];
}) {
  return (
    <ol className="relative ml-2 space-y-2 border-l border-line pl-4">
      {sources.map((s, i) => (
        <li key={`${s.event_id}-${i}`} className="relative">
          <span className="absolute -left-[21px] top-1.5 size-2 rounded-full border border-line bg-panel-2" />
          <div className="flex flex-wrap items-center gap-2">
            <OriginChip origin={s.origin} />
            <span className="mono text-[11px] text-muted">
              {new Date(s.occurred_at).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </span>
          </div>
          {s.excerpt ? <p className="mt-1 text-xs leading-relaxed text-muted">{s.excerpt}</p> : null}
        </li>
      ))}
    </ol>
  );
}
