"use client";

// App shell: sidebar navigation + live-connection header.

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type Stats } from "@/lib/api";
import { useStream, type Notification } from "@/lib/useStream";

const NAV = [
  { href: "/", label: "Dashboard", icon: "◧" },
  { href: "/memory", label: "Memory", icon: "▤" },
  { href: "/auditor", label: "Auditor", icon: "⚖" },
  { href: "/ask", label: "Ask", icon: "❯" },
];

function NotificationToast({ n }: { n: Notification }) {
  const tone =
    n.type === "contradiction_detected" || n.type === "clarification_needed"
      ? "border-danger/40 text-danger"
      : n.type === "pattern_promoted"
        ? "border-violet/40 text-violet"
        : n.type === "contradiction_resolved" || n.type === "fact_verified"
          ? "border-accent/40 text-accent"
          : "border-line text-muted";
  return (
    <div className={`card animate-slide-in border px-3 py-2 text-xs ${tone}`}>
      <span className="mono font-semibold uppercase tracking-wider">
        {n.type.replaceAll("_", " ")}
      </span>
      {"key" in n && typeof n.key === "string" ? (
        <span className="ml-2 text-muted">{n.key}</span>
      ) : null}
    </div>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [stats, setStats] = useState<Stats | null>(null);
  const [toasts, setToasts] = useState<Notification[]>([]);
  const { connected } = useStream((n) => {
    setToasts((prev) => [n, ...prev].slice(0, 3));
    setTimeout(() => setToasts((prev) => prev.slice(0, prev.length - 1)), 6000);
    api.stats().then(setStats).catch(() => {});
  });

  useEffect(() => {
    api.stats().then(setStats).catch(() => {});
    const t = setInterval(() => api.stats().then(setStats).catch(() => {}), 15000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-52 shrink-0 flex-col border-r border-line px-3 py-4">
        <div className="mb-6 px-2">
          <div className="text-sm font-bold tracking-tight">
            Memory<span className="text-accent">OS</span>
          </div>
          <div className="mt-0.5 text-[10px] leading-tight text-muted">
            evidence-based memory
          </div>
        </div>
        <nav className="space-y-1">
          {NAV.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] transition-colors ${
                  active
                    ? "bg-panel-2 font-medium text-ink"
                    : "text-muted hover:bg-panel hover:text-ink"
                }`}
              >
                <span className="mono text-xs">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto space-y-2 px-2">
          {stats ? (
            <div className="mono space-y-1 text-[10px] text-muted">
              <div>{stats.facts_active} facts · {stats.events_total} events</div>
              <div>
                {stats.contradictions_open > 0 ? (
                  <span className="text-danger">{stats.contradictions_open} open conflicts</span>
                ) : (
                  <span>0 open conflicts</span>
                )}
              </div>
              <div>
                Qwen:{" "}
                {stats.qwen_available ? (
                  <span className="text-accent">connected</span>
                ) : (
                  <span className="text-warn">rules-only</span>
                )}
              </div>
            </div>
          ) : null}
          <div className="flex items-center gap-1.5 text-[10px] text-muted">
            <span
              className={`live-dot size-1.5 rounded-full ${connected ? "bg-accent" : "bg-danger"}`}
            />
            {connected ? "live stream" : "stream offline"}
          </div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-6 py-6 lg:px-10">{children}</main>
      <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-72 flex-col gap-2">
        {toasts.map((n, i) => (
          <NotificationToast key={`${n.ts}-${i}`} n={n} />
        ))}
      </div>
    </div>
  );
}
