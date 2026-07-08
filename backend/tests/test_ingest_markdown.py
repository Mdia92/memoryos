"""Tests for the markdown ingester's parsing helpers (no HTTP)."""

from datetime import UTC, datetime
from pathlib import Path

from evals.ingest_markdown import (
    _chunk,
    _occurred_at,
    _strip_frontmatter,
    find_markdown,
)


def test_occurred_at_reads_date_prefix(tmp_path: Path):
    """YYYY-MM-DD prefix on the filename is the truth of when it happened."""
    f = tmp_path / "2026-03-15-standup.md"
    f.write_text("# hi")
    ts = _occurred_at(f)
    assert ts == datetime(2026, 3, 15, tzinfo=UTC)


def test_occurred_at_supports_underscore_separator(tmp_path: Path):
    f = tmp_path / "2026_04_02_deep_work.md"
    f.write_text("# hi")
    ts = _occurred_at(f)
    assert ts == datetime(2026, 4, 2, tzinfo=UTC)


def test_occurred_at_falls_back_to_mtime(tmp_path: Path):
    """No date prefix → we trust the filesystem mtime."""
    f = tmp_path / "random-name.md"
    f.write_text("# hi")
    ts = _occurred_at(f)
    # mtime should be within the last few seconds
    now = datetime.now(UTC)
    assert (now - ts).total_seconds() < 10


def test_occurred_at_invalid_date_falls_back(tmp_path: Path):
    """A 2026-13-45-typo.md prefix is invalid → fall through to mtime."""
    f = tmp_path / "2026-13-45-typo.md"
    f.write_text("# hi")
    ts = _occurred_at(f)
    # No exception, and we get some datetime back
    assert isinstance(ts, datetime)


def test_strip_frontmatter_removes_yaml_block():
    text = "---\ntitle: My Note\ntags: [x, y]\n---\nActual body content."
    assert _strip_frontmatter(text) == "Actual body content."


def test_strip_frontmatter_leaves_non_frontmatter_alone():
    text = "# Just a heading\n\nNo frontmatter here."
    assert _strip_frontmatter(text) == text


def test_strip_frontmatter_only_removes_leading_block():
    """A --- later in the body is not frontmatter — must be preserved."""
    text = "---\nheader: 1\n---\nBody\n\n---\nInline horizontal rule\n---\nMore body."
    stripped = _strip_frontmatter(text)
    assert stripped.startswith("Body")
    assert "Inline horizontal rule" in stripped


def test_chunk_returns_single_for_small_text():
    text = "one two three four five"
    assert _chunk(text, size=10) == [text]


def test_chunk_splits_at_word_boundary():
    text = " ".join(str(i) for i in range(2500))
    chunks = _chunk(text, size=800)
    assert len(chunks) == 4
    for c in chunks[:-1]:
        assert len(c.split()) == 800
    assert len(chunks[-1].split()) == 100


def test_chunk_preserves_all_words():
    text = " ".join(f"w{i}" for i in range(1600))
    chunks = _chunk(text, size=500)
    rejoined = " ".join(chunks)
    assert rejoined == text


def test_find_markdown_recurses_and_filters(tmp_path: Path):
    (tmp_path / "root.md").write_text("# r")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.md").write_text("# n")
    (sub / "notes.txt").write_text("plaintext")
    found = find_markdown(tmp_path)
    assert len(found) == 2
    assert all(p.suffix == ".md" for p in found)


def test_find_markdown_sorted(tmp_path: Path):
    (tmp_path / "b.md").write_text("b")
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "c.md").write_text("c")
    found = find_markdown(tmp_path)
    assert [p.name for p in found] == ["a.md", "b.md", "c.md"]
