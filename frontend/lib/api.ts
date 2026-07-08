// Typed client for the MemoryOS backend.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface SourceRef {
  event_id: string;
  origin: string;
  occurred_at: string;
  excerpt: string;
}

export interface BreakdownTerm {
  score: number;
  weight: number;
  weighted: number;
}

export interface ConfidenceBreakdown {
  confidence: number;
  terms: Record<string, BreakdownTerm>;
  sources: number;
  independent_origins: number;
}

export interface Fact {
  id: string;
  subject: string;
  key: string;
  value: string;
  statement: string;
  confidence: number;
  verification: "unverified" | "verified" | "failed";
  user_confirmation: "none" | "confirmed" | "corrected";
  active: boolean;
  stale: boolean;
  superseded_by: string | null;
  first_seen: string | null;
  last_supported: string | null;
  sources: SourceRef[];
  breakdown: ConfidenceBreakdown;
}

export interface ContradictionSide {
  id: string;
  value: string;
  confidence: number;
  sources: number;
  active: boolean;
}

export interface Contradiction {
  id: string;
  subject: string;
  key: string;
  status: string;
  resolution: string;
  detected_at: string;
  resolved_at: string | null;
  fact_a: ContradictionSide | null;
  fact_b: ContradictionSide | null;
}

export interface Pattern {
  id: string;
  name: string;
  description: string;
  promoted: boolean;
  confidence: number;
  support: number;
  sessions: number[];
}

export interface Stats {
  events_total: number;
  facts_active: number;
  facts_verified: number;
  pct_corroborated: number;
  avg_confidence: number;
  stale_facts: number;
  contradictions_open: number;
  contradictions_resolved: number;
  patterns_promoted: number;
  qwen_available: boolean;
  cost?: {
    qwen_calls: number;
    qwen_input_tokens_est: number;
    qwen_by_model: Record<string, number>;
    rules_fallbacks: number;
    deterministic_decisions: number;
    deterministic_ops: number;
    fast_path_pct: number;
  };
}

export interface Decision {
  key: string | null;
  value: string | null;
  statement?: string;
  fact_id?: string;
  confidence: number | null;
  gate: "act" | "show_sources" | "ask" | "unknown";
  reason: string;
  margin?: number | null;
  competing_values?: { value: string; confidence: number; sources: number }[];
  evidence: SourceRef[];
  confidence_breakdown?: ConfidenceBreakdown;
}

export interface AskResponse {
  question: string;
  key: string | null;
  answer: string;
  decision: Decision | null;
  path?: "tracked-fact" | "hybrid-retrieval" | "abstain";
  baseline?: {
    value: string | null;
    answer: string;
    note: string;
    source: { origin: string; occurred_at: string } | null;
  };
  providers: Record<string, string>;
}

export interface EvalSessionRow {
  session: number;
  memoryos_accuracy: number;
  baseline_accuracy: number;
  precision_when_acting: number | null;
  act_rate: number;
  ask_rate: number;
  facts_active: number;
  facts_verified: number;
  avg_confidence: number;
  contradictions_open: number;
  contradictions_resolved: number;
  patterns_promoted: number;
}

export interface EvalResults {
  dataset: {
    sessions: number;
    events: number;
    noise_events: number;
    keys: number;
    synthetic: boolean;
  };
  sessions: EvalSessionRow[];
  summary: {
    memoryos_first: number;
    memoryos_last: number;
    baseline_first: number;
    baseline_last: number;
    mean_precision_when_acting: number | null;
    final_act_rate: number;
  };
}

export interface EvalRun {
  id: string;
  created_at: string;
  label: string;
  config: { sessions: number; seed: number };
  results: EvalResults;
}

export interface AuditEntry {
  ts: string;
  actor: string;
  action: string;
  detail: Record<string, unknown>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  stats: () => request<Stats>("/api/stats"),
  facts: (includeInactive = false) =>
    request<Fact[]>(`/api/facts?include_inactive=${includeInactive}`),
  fact: (id: string) => request<Fact & { contradictions: unknown[] }>(`/api/facts/${id}`),
  contradictions: () => request<Contradiction[]>("/api/contradictions"),
  resolveContradiction: (id: string, chosenFactId: string) =>
    request(`/api/contradictions/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ chosen_fact_id: chosenFactId }),
    }),
  patterns: () => request<Pattern[]>("/api/patterns"),
  audit: (limit = 100) => request<AuditEntry[]>(`/api/audit?limit=${limit}`),
  ask: (question: string, compare = true) =>
    request<AskResponse>("/api/ask", {
      method: "POST",
      body: JSON.stringify({ question, compare }),
    }),
  evalLatest: () => request<EvalRun>("/api/eval/latest"),
  evalRun: (sessions = 20, seed = 42, label = "dashboard") =>
    request<{ run_id: string } & EvalResults>("/api/eval/run", {
      method: "POST",
      body: JSON.stringify({ sessions, seed, label }),
    }),
  demoSeed: (sessions: number) =>
    request<{ sessions: number; events: number; facts_active: number }>("/api/demo/seed", {
      method: "POST",
      body: JSON.stringify({ sessions }),
    }),
  demoReset: () => request("/api/demo/reset", { method: "POST" }),
  ingestEvent: (payload: {
    type: string;
    content: string;
    assertions?: { subject: string; key: string; value: string; statement?: string }[] | null;
  }) =>
    request<{
      event_id: string;
      extraction_provider: string;
      assertions: { key: string; value: string }[];
      notifications: { type: string }[];
    }>("/api/events", { method: "POST", body: JSON.stringify(payload) }),
};
