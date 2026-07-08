"""Tests for the .ics calendar ingester (parser only, no HTTP)."""

from pathlib import Path

import pytest
from icalendar import Calendar

from evals.ingest_ics import _iter_events, find_ics, parse_file

BASE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//MemoryOS//Test//EN
BEGIN:VEVENT
UID:evt001@memoryos
DTSTAMP:20260315T090000Z
DTSTART:20260315T090000Z
DTEND:20260315T095000Z
SUMMARY:Team standup
DESCRIPTION:Daily sync - 15 min
LOCATION:Zoom
ATTENDEE:mailto:alice@example.com
ATTENDEE:mailto:bob@example.com
END:VEVENT
BEGIN:VEVENT
UID:evt002@memoryos
DTSTAMP:20260316T140000Z
DTSTART:20260316T140000Z
DTEND:20260316T150000Z
SUMMARY:1:1 with Sarah
LOCATION:Cafe Rio
END:VEVENT
BEGIN:VEVENT
UID:evt003@memoryos
DTSTAMP:20260317T100000Z
DTSTART:20260317T100000Z
DTEND:20260317T110000Z
RECURRENCE-ID:20260317T090000Z
SUMMARY:Weekly sync (RESCHEDULED)
LOCATION:Zoom
END:VEVENT
END:VCALENDAR
"""

ALL_DAY_ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:allday@memoryos
DTSTAMP:20260401T000000Z
DTSTART;VALUE=DATE:20260401
DTEND;VALUE=DATE:20260402
SUMMARY:Company holiday
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture
def sample_calendar():
    return Calendar.from_ical(BASE_ICS)


def test_iter_events_parses_all_vevents(sample_calendar):
    events = _iter_events(sample_calendar)
    assert len(events) == 3
    assert [e["summary"] for e in events] == [
        "Team standup",
        "1:1 with Sarah",
        "Weekly sync (RESCHEDULED)",
    ]


def test_recurrence_id_marks_reschedule(sample_calendar):
    events = _iter_events(sample_calendar)
    assert events[0]["meta"]["action"] is None
    assert events[1]["meta"]["action"] is None
    assert events[2]["meta"]["action"] == "reschedule"


def test_attendee_count(sample_calendar):
    events = _iter_events(sample_calendar)
    assert events[0]["meta"]["attendee_count"] == 2
    assert events[1]["meta"]["attendee_count"] == 0
    assert events[2]["meta"]["attendee_count"] == 0


def test_duration_computed(sample_calendar):
    events = _iter_events(sample_calendar)
    assert events[0]["meta"]["duration_min"] == 50
    assert events[1]["meta"]["duration_min"] == 60
    assert events[2]["meta"]["duration_min"] == 60


def test_location_appears_in_content(sample_calendar):
    events = _iter_events(sample_calendar)
    assert "Zoom" in events[0]["content"]
    assert "Cafe Rio" in events[1]["content"]


def test_description_included_in_content(sample_calendar):
    events = _iter_events(sample_calendar)
    assert "Daily sync" in events[0]["content"]


def test_all_day_event_normalized_to_datetime():
    cal = Calendar.from_ical(ALL_DAY_ICS)
    events = _iter_events(cal)
    assert len(events) == 1
    ts = events[0]["occurred_at"]
    assert ts.startswith("2026-04-01T00:00:00")


def test_find_ics_returns_only_ics_files(tmp_path: Path):
    (tmp_path / "cal1.ics").write_text(BASE_ICS)
    (tmp_path / "cal2.ics").write_text(BASE_ICS)
    (tmp_path / "notes.txt").write_text("not a calendar")
    (tmp_path / "readme.md").write_text("# hi")
    found = find_ics(tmp_path)
    assert len(found) == 2
    assert all(p.suffix == ".ics" for p in found)


def test_find_ics_single_file(tmp_path: Path):
    f = tmp_path / "solo.ics"
    f.write_text(BASE_ICS)
    assert find_ics(f) == [f]


def test_parse_file_reads_from_disk(tmp_path: Path):
    f = tmp_path / "test.ics"
    f.write_text(BASE_ICS)
    events = parse_file(f)
    assert len(events) == 3


def test_missing_dtstart_skipped():
    ics = """BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:bad@memoryos
DTSTAMP:20260315T090000Z\nSUMMARY:no start\nEND:VEVENT\nEND:VCALENDAR\n"""
    cal = Calendar.from_ical(ics)
    # icalendar raises when DTSTART is genuinely absent; skipped events return 0.
    events = _iter_events(cal)
    assert events == []


def test_missing_summary_falls_back():
    ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:x@memoryos
DTSTAMP:20260315T090000Z
DTSTART:20260315T090000Z
DTEND:20260315T100000Z
END:VEVENT
END:VCALENDAR
"""
    cal = Calendar.from_ical(ics)
    events = _iter_events(cal)
    assert len(events) == 1
    assert events[0]["summary"] == "(untitled event)"
