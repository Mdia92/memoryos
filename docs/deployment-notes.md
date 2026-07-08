# Deployment notes

Operational reference for running MemoryOS. The one-command quick start in
the README covers the happy path; this doc covers the details.

## Environment variables

Loaded from `.env` at the repo root (dev) or from Docker Compose env
(prod). The complete list:

| Var | Required | Default | Purpose |
|---|---|---|---|
| `DASHSCOPE_API_KEY` | recommended | *empty* | Qwen slow path; with this unset the system runs on the rules-only fallback |
| `DASHSCOPE_BASE_URL` | no | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | International accounts; mainland uses `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `QWEN_PRIMARY_MODEL` | no | `qwen-plus` | First model tried by the fallback chain |
| `QWEN_FALLBACK_MODEL` | no | `qwen-turbo` | Second model tried; cheaper and faster |
| `QWEN_EMBEDDING_MODEL` | no | `text-embedding-v3` | For hybrid-retrieval semantic search |
| `DATABASE_URL` | yes | `postgresql+asyncpg://memoryos:memoryos@db:5432/memoryos` (in prod compose) | PostgreSQL + pgvector; use ApsaraDB RDS internal endpoint in production |
| `CORS_ORIGINS` | no | `http://localhost` | Comma-separated list of allowed browser origins |
| `NEXT_PUBLIC_API_URL` | no | *empty* (same-origin via nginx) | Frontend-side base URL; keep empty in prod so the browser calls same-origin `/api/*` |
| `MEMORYOS_API` | no | `http://localhost:8000` | Used by the CLI clients (`ingest_markdown`, `ingest_ics`, `demo`) |

## docker compose commands

```bash
# Bring the stack up (build if needed)
docker compose -f deploy/docker-compose.prod.yml --env-file .env up -d --build

# Watch backend logs
docker compose -f deploy/docker-compose.prod.yml logs -f backend

# Restart just the backend after a code change
docker compose -f deploy/docker-compose.prod.yml up -d --build backend

# Check container health (all should be Up + healthy)
docker compose -f deploy/docker-compose.prod.yml ps

# Full teardown (keeps volumes)
docker compose -f deploy/docker-compose.prod.yml down

# Nuke volumes too (deletes persisted memory)
docker compose -f deploy/docker-compose.prod.yml down -v
```

## Health checks

- **Container-level**: `HEALTHCHECK` on the backend container hits
  `/health` every 15s. `docker compose ps` shows `(healthy)` when it's
  passing.
- **App-level**: `curl $API/health` returns `{status, qwen_available,
  facts, events}`. `qwen_available: true` proves the API key is loaded.
- **Deep**: `curl $API/api/stats` returns the full KPI panel including
  the cost tile (`fast_path_pct`, `qwen_calls`, `deterministic_ops`).

## Common operational tasks

**Reset to a clean demo state:**
```bash
export API=http://<your-host>
curl -X POST $API/api/demo/reset
curl -X POST $API/api/demo/seed -H "Content-Type: application/json" \
     -d '{"sessions":20}'
curl -X POST $API/api/eval/run -H "Content-Type: application/json" \
     -d '{"label":"demo","sessions":20,"seed":42}'
```

**Ingest real data:**
```bash
python -m evals.ingest_markdown --path ~/notes --api $API
python -m evals.ingest_ics --path ~/calendar.ics --api $API
```

**Backup (portable JSON — the recommended path):**
```bash
curl -s $API/api/export > memoryos-export-$(date +%F).json
```
No lock-in: `/api/export` dumps every event, fact, contradiction, pattern,
and audit entry as a stable JSON. You can pipe it into `jq`, re-ingest it
into another MemoryOS instance via `/api/events` (each event carries its
`occurred_at`, `assertions`, and `meta`), or archive it forever.

**Backup (SQL dump — for pg_restore):**
```bash
docker compose -f deploy/docker-compose.prod.yml exec -T db \
  pg_dump -U memoryos memoryos > memoryos-backup-$(date +%F).sql
```

**Restore:**
```bash
cat memoryos-backup-YYYY-MM-DD.sql | \
  docker compose -f deploy/docker-compose.prod.yml exec -T db \
  psql -U memoryos memoryos
```

## Alibaba Cloud specifics

For the hackathon deployment we run everything on a single ECS instance
with the bundled Postgres container. For a real Alibaba Cloud deployment:

1. **ECS**: `ecs.t6-c1m2.large` (2 vCPU / 4 GiB) is enough at prototype
   scale; upgrade for real workloads.
2. **ApsaraDB RDS for PostgreSQL 16**: the smallest instance class works.
   Add pgvector via the console. Whitelist the ECS's internal IP.
   Change `DATABASE_URL` in the ECS `.env` to the RDS internal endpoint;
   remove the `db` service from `deploy/docker-compose.prod.yml`.
3. **Model Studio (DashScope)**: activate in the console, mint a key,
   drop it into `.env`. No further config needed — the endpoint URL in
   `config.py` is the international one by default.
4. **Security group**: inbound 22 (SSH from your IP) + 80 (HTTP world).
   Add 443 when you terminate TLS.

## Monitoring hints

MemoryOS emits structured events on `/api/stream` (SSE). A production
deployment can subscribe to these for near-real-time monitoring:

- `contradiction_detected` — the auditor found conflicting facts
- `contradiction_resolved` — either evidence decided or the user did
- `clarification_needed` — the acting gate refused; user attention needed
- `pattern_promoted` — a new pattern crossed the promotion bar
- `fact_verified` — an existing fact just gained enough corroboration
- `memory_seeded` / `memory_reset` — bulk state changes

Point a log shipper (or a simple `curl -N`) at that endpoint to feed
downstream observability. There is no other event bus; this is the whole
notification surface.

## Cost expectations

The dashboard shows `fast_path_pct` live. On the standard demo state
(seed → seed 20 sessions → run eval → ask one question) it sits at
99.6%: 725 deterministic engine operations vs 2 Qwen calls. Steady-state
cost is dominated by user-facing asks (2 Qwen calls per question) and
ingestion of unstructured text (1 Qwen call per event, unless pre-
extracted assertions are supplied). At `qwen-plus` prices, that's roughly
$0.001 per question. Ingesting an entire markdown vault of ~1000 notes
runs to about $0.20.

If cost matters more than latency: swap primary + fallback in the env
so `qwen-turbo` runs first, and pre-extract assertions on the ingest
side to skip the extraction hop entirely.
