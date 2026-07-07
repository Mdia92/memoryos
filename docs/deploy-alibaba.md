# Deploying MemoryOS on Alibaba Cloud

Three managed services, no code changes — only environment variables:

| Piece | Alibaba Cloud service | What changes |
|---|---|---|
| Qwen models + embeddings | **Model Studio** (DashScope OpenAI-compatible API) | `DASHSCOPE_API_KEY` |
| Memory store | **ApsaraDB RDS for PostgreSQL** (pgvector supported) | `DATABASE_URL` |
| Backend + dashboard | **ECS** instance running Docker Compose | none |

## 1. Model Studio (Qwen)

1. Console → Model Studio → activate, create an API key.
2. International accounts use `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
   (already the default `DASHSCOPE_BASE_URL`); mainland accounts use
   `https://dashscope.aliyuncs.com/compatible-mode/v1`.
3. Models used: `qwen-plus` (primary), `qwen-turbo` (fallback),
   `text-embedding-v3`.

## 2. ApsaraDB RDS for PostgreSQL

1. Create an RDS PostgreSQL 16 instance (smallest spec is fine — the memory
   store is tiny at prototype scale).
2. Create database `memoryos` and an account with full privileges on it.
3. Add the ECS instance's internal IP (or its VPC security group) to the RDS
   whitelist.
4. pgvector: the backend runs `CREATE EXTENSION IF NOT EXISTS vector` at
   startup; on RDS the `vector` extension is available — ensure the account
   may create extensions, or create it once from the console/`psql`.
5. `DATABASE_URL=postgresql+asyncpg://<user>:<password>@<internal-endpoint>:5432/memoryos`

## 3. ECS

1. Create an ECS instance (2 vCPU / 2–4 GB, Ubuntu 22.04), same VPC as RDS.
   Open ports 22 and 80 in the security group.
2. Install Docker + the compose plugin:
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
3. Clone the repo and configure:
   ```bash
   git clone https://github.com/<you>/memoryos && cd memoryos
   cp .env.example .env   # set DASHSCOPE_API_KEY, DATABASE_URL, CORS_ORIGINS=http://<ecs-public-ip>
   ```
4. Launch:
   ```bash
   docker compose -f deploy/docker-compose.prod.yml --env-file .env up -d --build
   ```
5. Verify from anywhere:
   ```bash
   curl http://<ecs-public-ip>/health
   curl -X POST http://<ecs-public-ip>/api/demo/seed -H "Content-Type: application/json" -d '{"sessions":20}'
   curl -X POST http://<ecs-public-ip>/api/eval/run  -H "Content-Type: application/json" -d '{"label":"cloud","sessions":20,"seed":42}'
   ```

nginx serves the dashboard at `http://<ecs-public-ip>/` and proxies `/api/*`
(SSE included) to the backend; the browser talks same-origin, so no extra
CORS configuration is needed beyond the ECS URL.

## Deployment proof recording (submission requirement)

Record one short screen capture showing:

1. The Alibaba Cloud console: the running ECS instance and the RDS instance.
2. A terminal on ECS: `docker compose ps` showing the three containers.
3. `curl http://<ecs-public-ip>/health` from a machine that is not the ECS
   instance, returning `{"status":"ok", ...}`.
4. The dashboard loading from the public IP, and one `/api/ask` answer whose
   provider chip shows a Qwen model id (proves live Model Studio calls).

Code-level proof link for the submission form:
[`backend/app/qwen_client.py`](../backend/app/qwen_client.py) — every LLM and
embedding call targets DashScope on Alibaba Cloud.
