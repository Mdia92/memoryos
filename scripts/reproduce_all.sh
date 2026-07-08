#!/usr/bin/env bash
# Reproduce every result MemoryOS claims. Runs local against docker compose.
#
# Requires: docker, python 3.11+, a DASHSCOPE_API_KEY in .env (optional; the
# LongMemEval and demo scenes need it — everything else runs without).
#
# Cost: ~$0.20 in Qwen tokens if the key is set. Time: ~2 minutes without
# LongMemEval, ~5 minutes with the 20-instance benchmark run.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
API=${MEMORYOS_API:-http://localhost:8000}

banner() {
  echo
  echo "=================================================================="
  echo "  $1"
  echo "=================================================================="
}

banner "1. Backend unit + API tests (37 tests, deterministic, zero LLM)"
cd "$REPO/backend"
python -m pip install -q -e ".[dev]"
python -m pytest -q

banner "2. Reproduce the seeded accuracy curve (deterministic, zero LLM)"
python -m evals.run_eval --sessions 20 --seed 42

banner "3. Six-seed robustness sweep — precision-when-acting on every seed"
python -m evals.seed_sweep

banner "4. Bring up the full stack (backend + frontend + Postgres + nginx)"
cd "$REPO"
docker compose -f deploy/docker-compose.prod.yml --env-file .env up -d --build

echo "waiting for backend..."
until curl -sf "$API/health" > /dev/null 2>&1; do sleep 2; done
echo "backend healthy"

banner "5. End-to-end demo — seed, eval, three ask scenes, fast-path counter"
cd "$REPO/backend"
MEMORYOS_API="$API" python -m evals.demo

banner "6. LongMemEval — MemoryOS vs vanilla RAG (20 stratified instances)"
if [ -f evals/data/longmemeval_oracle.json ]; then
  python -m evals.longmemeval.run --n 20 --seed 42 --variant oracle --rag
else
  echo "LongMemEval dataset not present; run:"
  echo "  bash $REPO/scripts/download_datasets.sh"
  echo "then rerun this script."
fi

banner "Done."
echo "The dashboard is live at http://localhost — every claim above is"
echo "either printed on this terminal or one click away in the UI."
