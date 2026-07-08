#!/usr/bin/env bash
# Download benchmark datasets used by MemoryOS evals.
#
# Currently: LongMemEval-cleaned (ICLR 2025), 500 questions across 6 categories.
#   MIT-licensed, hosted on HuggingFace by the original authors.
#
#   oracle  — ~15 MB, only the sessions relevant to each question. Recommended
#             for MemoryOS: tests the ingest→corroborate→answer pipeline
#             without conflating in a needle-in-haystack retrieval challenge.
#   small   — ~277 MB, ~115k tokens haystack per question (retrieval-heavy).
#
# Usage:
#   bash scripts/download_datasets.sh          # oracle only (default)
#   bash scripts/download_datasets.sh small    # add small variant
set -euo pipefail

DATA_DIR="$(cd "$(dirname "$0")/../backend/evals/data" && pwd)"
mkdir -p "$DATA_DIR"

download() {
  local name="$1"
  local url="$2"
  local dest="$DATA_DIR/$name"
  if [[ -f "$dest" ]]; then
    echo "[skip] $name already present"
    return
  fi
  echo "[get ] $name"
  curl -sfL --max-time 600 -o "$dest" "$url"
}

download longmemeval_oracle.json \
  "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_oracle.json"

if [[ "${1:-}" == "small" ]]; then
  download longmemeval_s.json \
    "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json"
fi

echo "Done. Files in $DATA_DIR:"
ls -lh "$DATA_DIR"
