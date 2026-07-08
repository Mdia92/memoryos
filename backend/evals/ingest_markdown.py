"""Ingest a folder of markdown notes into a live MemoryOS backend.

Turns a real notes vault (Obsidian, Bear, plain markdown) into episodic
events. Each file becomes one or more `note` events (chunked at ~800 words
so extraction sees coherent context). Runs through the same
extraction -> engine pipeline as the API — nothing benchmark-specific.

Usage:
  # streams events into a running backend
  python -m evals.ingest_markdown --api http://localhost:8000 --path ~/notes

  # dry run: prints what would be ingested and what's extracted, no HTTP
  python -m evals.ingest_markdown --path ~/notes --dry-run

Filename -> occurred_at rule:
  1. YYYY-MM-DD prefix in the filename;
  2. else the file's mtime.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx

DATE_PREFIX = re.compile(r"^(\d{4})[-_](\d{2})[-_](\d{2})")
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
CHUNK_WORDS = 800


def _occurred_at(path: Path) -> datetime:
    m = DATE_PREFIX.search(path.stem)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=UTC)
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


def _strip_frontmatter(text: str) -> str:
    return FRONTMATTER.sub("", text, count=1)


def _chunk(text: str, size: int = CHUNK_WORDS) -> list[str]:
    words = text.split()
    if len(words) <= size:
        return [text]
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size)]


def find_markdown(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.md") if p.is_file())


async def _post_event(client: httpx.AsyncClient, api: str, payload: dict) -> dict:
    r = await client.post(f"{api}/api/events", json=payload, timeout=90)
    r.raise_for_status()
    return r.json()


async def ingest(root: Path, api: str, dry_run: bool) -> None:
    files = find_markdown(root)
    if not files:
        print(f"No .md files under {root}")
        return

    print(f"Ingesting {len(files)} files from {root}")
    if not dry_run:
        print(f"-> backend at {api}")
    print("-" * 60)

    async with httpx.AsyncClient() as client:
        total_events = 0
        total_assertions = 0
        for i, path in enumerate(files, start=1):
            try:
                raw = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                print(f"[{i}/{len(files)}] {path.name}: read error {exc}")
                continue
            body = _strip_frontmatter(raw).strip()
            if not body:
                continue
            occurred = _occurred_at(path)
            for chunk in _chunk(body):
                event = {
                    "type": "note",
                    "content": chunk,
                    "occurred_at": occurred.isoformat(),
                    "meta": {"source_file": str(path.relative_to(root))},
                }
                if dry_run:
                    print(f"[{i}] {path.name} ({len(chunk.split())} words)")
                    continue
                try:
                    result = await _post_event(client, api, event)
                except httpx.HTTPError as exc:
                    print(f"[{i}] {path.name}: HTTP error {exc}")
                    continue
                total_events += 1
                assertions = result.get("assertions", [])
                total_assertions += len(assertions)
                summary = ", ".join(f"{a['key']}={a['value']}" for a in assertions[:3])
                if len(assertions) > 3:
                    summary += f" ... (+{len(assertions) - 3} more)"
                notes = f"-> {result.get('extraction_provider')}: [{summary}]" if summary else ""
                print(f"[{i}/{len(files)}] {path.name} {notes}")

    if not dry_run:
        print("-" * 60)
        print(f"Ingested: {total_events} events, {total_assertions} assertions extracted")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="root folder of markdown notes")
    parser.add_argument(
        "--api",
        default=os.getenv("MEMORYOS_API", "http://localhost:8000"),
        help="MemoryOS backend URL",
    )
    parser.add_argument("--dry-run", action="store_true", help="list files, don't ingest")
    args = parser.parse_args()
    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")
    asyncio.run(ingest(root, args.api, args.dry_run))


if __name__ == "__main__":
    main()
