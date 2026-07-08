"""Ingest an .ics calendar (Google Calendar / Outlook export) into MemoryOS.

Each VEVENT becomes one `calendar` MemoryOS event with the meeting title as
content, the start time as `occurred_at`, and structured meta (organizer,
location, attendee count, duration, action=reschedule if RECURRENCE-ID is
present). The existing engine handles extraction, corroboration, and the
pattern detectors that already look for `meta.action == "reschedule"`.

Usage:
  # google calendar → settings → export → .ics file
  python -m evals.ingest_ics --api http://localhost:8000 --path ~/calendar.ics

  # multiple files:
  python -m evals.ingest_ics --api ... --path ~/calendars/  # any *.ics inside

  # dry run:
  python -m evals.ingest_ics --path ~/calendar.ics --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
from icalendar import Calendar


def _ensure_datetime(value: Any) -> datetime:
    """DTSTART is date or datetime; normalize to timezone-aware UTC datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    raise TypeError(f"unsupported DTSTART type: {type(value).__name__}")


def _stringify(v: Any) -> str | None:
    if v is None:
        return None
    return str(v).strip() or None


def find_ics(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob("*.ics") if p.is_file())


def _iter_events(cal: Calendar) -> list[dict]:
    events: list[dict] = []
    for component in cal.walk("VEVENT"):
        try:
            occurred = _ensure_datetime(component.get("DTSTART").dt)
        except (AttributeError, TypeError):
            continue
        summary = _stringify(component.get("SUMMARY")) or "(untitled event)"
        description = _stringify(component.get("DESCRIPTION")) or ""
        location = _stringify(component.get("LOCATION"))
        organizer = _stringify(component.get("ORGANIZER"))
        attendees = component.get("ATTENDEE")
        if isinstance(attendees, list):
            attendee_count = len(attendees)
        elif attendees is None:
            attendee_count = 0
        else:
            attendee_count = 1
        # RECURRENCE-ID means "this is a modification/override of a recurring
        # instance" — the memoryOS pattern detectors look for reschedules.
        recurrence_id = component.get("RECURRENCE-ID") is not None
        end_dt = component.get("DTEND")
        duration_min: int | None = None
        if end_dt is not None:
            try:
                end = _ensure_datetime(end_dt.dt)
                duration_min = int((end - occurred).total_seconds() // 60)
            except (AttributeError, TypeError):
                pass

        content_parts = [summary]
        if location:
            content_parts.append(f"Location: {location}")
        if description:
            content_parts.append(description[:800])
        content = " | ".join(content_parts)

        events.append(
            {
                "occurred_at": occurred.isoformat(),
                "summary": summary,
                "content": content,
                "meta": {
                    "source": "ics",
                    "location": location,
                    "organizer": organizer,
                    "attendee_count": attendee_count,
                    "duration_min": duration_min,
                    "action": "reschedule" if recurrence_id else None,
                    "uid": _stringify(component.get("UID")),
                },
            }
        )
    return events


def parse_file(path: Path) -> list[dict]:
    with open(path, "rb") as f:
        cal = Calendar.from_ical(f.read())
    return _iter_events(cal)


async def _post_event(client: httpx.AsyncClient, api: str, payload: dict) -> dict:
    r = await client.post(f"{api}/api/events", json=payload, timeout=90)
    r.raise_for_status()
    return r.json()


async def ingest(root: Path, api: str, dry_run: bool) -> None:
    files = find_ics(root)
    if not files:
        print(f"No .ics files found under {root}")
        return

    all_events: list[dict] = []
    for path in files:
        try:
            all_events.extend(parse_file(path))
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] {path.name}: parse error {exc}")

    all_events.sort(key=lambda e: e["occurred_at"])
    print(f"Parsed {len(all_events)} calendar events from {len(files)} file(s)")
    if not dry_run:
        print(f"-> backend at {api}")
    print("-" * 60)

    async with httpx.AsyncClient() as client:
        total_events = 0
        total_assertions = 0
        for i, ev in enumerate(all_events, start=1):
            payload = {
                "type": "calendar",
                "content": ev["content"][:2000],
                "occurred_at": ev["occurred_at"],
                "meta": ev["meta"],
            }
            if dry_run:
                print(f"[{i}/{len(all_events)}] {ev['occurred_at'][:16]} {ev['summary'][:60]}")
                continue
            try:
                result = await _post_event(client, api, payload)
            except httpx.HTTPError as exc:
                print(f"[{i}] {ev['summary'][:40]}: HTTP error {exc}")
                continue
            total_events += 1
            assertions = result.get("assertions", [])
            total_assertions += len(assertions)
            tag = ", ".join(f"{a['key']}={a['value']}" for a in assertions[:2])
            trailer = f" -> [{tag}]" if tag else ""
            print(f"[{i}/{len(all_events)}] {ev['occurred_at'][:10]} {ev['summary'][:50]}{trailer}")

    if not dry_run:
        print("-" * 60)
        print(f"Ingested: {total_events} calendar events, {total_assertions} assertions extracted")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="ICS file or folder of .ics files")
    parser.add_argument(
        "--api",
        default=os.getenv("MEMORYOS_API", "http://localhost:8000"),
        help="MemoryOS backend URL",
    )
    parser.add_argument("--dry-run", action="store_true", help="list events, don't ingest")
    args = parser.parse_args()
    root = Path(args.path).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Not found: {root}")
    asyncio.run(ingest(root, args.api, args.dry_run))


if __name__ == "__main__":
    main()
