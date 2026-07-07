"""Synthetic enterprise scenario generator — CLEARLY LABELED SYNTHETIC DATA.

Simulates 20 weekly work sessions for one persona ("the user") across five
origins: calendar, email, note, task, chat. Twelve preference/behavior keys
have known ground truth, two of which genuinely change mid-way (the flips),
and every session has a chance of emitting a misleading one-off event (the
noise). The generator is fully seeded — the same seed always produces the
same dataset, so every accuracy number in the eval is reproducible.

The design deliberately creates the three situations a memory system must
survive: sparse early evidence, noisy exceptions, and true preference
change. Nothing about MemoryOS's scoring is fit to this data; the policy
file never saw it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.memory.core import Assertion, MemoryEvent, new_id

ORIGINS = ["calendar", "email", "note", "task", "chat"]


@dataclass
class TruthKey:
    key: str
    question: str
    initial: str
    wrong: str  # the plausible-but-false value noise events assert
    statement_template: str  # "{value}" is interpolated
    flip_at_session: int | None = None
    flip_to: str | None = None
    origins: list[str] = field(default_factory=lambda: list(ORIGINS))

    def truth_at(self, session: int) -> str:
        if self.flip_at_session is not None and session >= self.flip_at_session:
            return self.flip_to or self.initial
        return self.initial

    def wrong_at(self, session: int) -> str:
        """The plausible-but-false value AT THIS SESSION — after a flip, the
        old value is what a misleading one-off event would claim."""
        truth = self.truth_at(session)
        return self.wrong if truth != self.wrong else self.initial


TRUTH_KEYS: list[TruthKey] = [
    TruthKey(
        key="meeting_time_preference",
        question="Does the user prefer morning or afternoon meetings?",
        initial="morning",
        wrong="afternoon",
        statement_template="User prefers {value} meetings",
    ),
    TruthKey(
        key="meeting_mode",
        question="Does the user prefer remote or office meetings?",
        initial="remote",
        wrong="office",
        statement_template="User prefers {value} meetings",
        flip_at_session=8,
        flip_to="office",
    ),
    TruthKey(
        key="report_format",
        question="What format does the user want reports in?",
        initial="pdf",
        wrong="slides",
        statement_template="User wants reports delivered as {value}",
    ),
    TruthKey(
        key="summary_length",
        question="Does the user want short or detailed summaries?",
        initial="short",
        wrong="detailed",
        statement_template="User wants {value} summaries",
    ),
    TruthKey(
        key="notification_channel",
        question="Where does the user want notifications sent?",
        initial="email",
        wrong="slack",
        statement_template="User wants notifications via {value}",
        flip_at_session=12,
        flip_to="slack",
    ),
    TruthKey(
        key="travel_class",
        question="Which travel class does the user book?",
        initial="economy",
        wrong="business",
        statement_template="User books {value} class for work travel",
    ),
    TruthKey(
        key="standup_day",
        question="Which day is the user's team standup?",
        initial="tuesday",
        wrong="monday",
        statement_template="Team standup happens on {value}",
    ),
    TruthKey(
        key="focus_block_day",
        question="Which day does the user block for focus work?",
        initial="friday",
        wrong="wednesday",
        statement_template="User blocks {value} for deep focus work",
    ),
    TruthKey(
        key="lunch_slot",
        question="When does the user take lunch?",
        initial="12:30",
        wrong="13:30",
        statement_template="User takes lunch at {value}",
    ),
    TruthKey(
        key="code_review_style",
        question="Does the user prefer async or live code reviews?",
        initial="async",
        wrong="live",
        statement_template="User prefers {value} code reviews",
    ),
    TruthKey(
        key="expense_tool",
        question="Which tool does the user file expenses with?",
        initial="spreadsheet",
        wrong="erp",
        statement_template="User files expenses with the {value}",
    ),
    TruthKey(
        key="writing_tone",
        question="What tone should drafts written for the user take?",
        initial="formal",
        wrong="casual",
        statement_template="User's drafts should use a {value} tone",
    ),
]

CONTENT_BY_ORIGIN = {
    "calendar": "Calendar event: {statement}.",
    "email": "Email thread excerpt: \"...just so you know, {statement_lower}...\"",
    "note": "Meeting note: {statement}.",
    "task": "Task update: {statement}.",
    "chat": "Chat message: \"{statement_lower}\"",
}

# Sessions where a long-weekend/break precedes work and meetings get
# rescheduled — the raw material of the pattern layer's discovery.
RESCHEDULE_SESSIONS = [4, 9, 14, 17]


def _make_event(
    rng: random.Random,
    session: int,
    session_start: datetime,
    tk: TruthKey,
    value: str,
    is_noise: bool,
) -> MemoryEvent:
    origin = rng.choice(tk.origins)
    statement = tk.statement_template.format(value=value)
    if is_noise:
        statement += " (one-off exception)"
    content = CONTENT_BY_ORIGIN[origin].format(
        statement=statement, statement_lower=statement[0].lower() + statement[1:]
    )
    occurred = session_start + timedelta(hours=rng.randint(1, 70), minutes=rng.randint(0, 59))
    return MemoryEvent(
        id=new_id(),
        session_id=session,
        type=origin,
        content=content,
        occurred_at=occurred,
        assertions=[
            Assertion(subject="user", key=tk.key, value=value, statement=statement)
        ],
        meta={"synthetic": True, "noise": is_noise},
    )


def generate_dataset(
    sessions: int = 20,
    seed: int = 42,
    keys_per_session: int = 5,
    noise_probability: float = 0.30,
    end: datetime | None = None,
) -> dict[int, list[MemoryEvent]]:
    """Returns {session_id: [events]} for sessions 1..N, one session per week,
    ending at `end` (default: now) so decay behaves like live data."""
    rng = random.Random(seed)
    end = end or datetime.now(UTC)
    start = end - timedelta(weeks=sessions)

    by_session: dict[int, list[MemoryEvent]] = {}
    for s in range(1, sessions + 1):
        session_start = start + timedelta(weeks=s - 1)
        # Anchor sessions to Monday 08:00 so weekday-based patterns are real.
        session_start = session_start - timedelta(days=session_start.weekday())
        session_start = session_start.replace(hour=8, minute=0, second=0, microsecond=0)
        events: list[MemoryEvent] = []

        # Post-break reschedule events (no assertions — pure episodic signal).
        if s in RESCHEDULE_SESSIONS:
            events.append(
                MemoryEvent(
                    id=new_id(),
                    session_id=s,
                    type="calendar",
                    content=(
                        "Calendar event: weekly sync RESCHEDULED to later this week "
                        "(first working day after a long weekend)."
                    ),
                    occurred_at=session_start,  # Monday 08:00, right after the gap
                    assertions=[],
                    meta={"synthetic": True, "action": "reschedule"},
                )
            )

        # Truthful supporting events for a sample of keys. A key whose truth
        # just flipped is guaranteed to appear — a real preference change
        # produces evidence, it doesn't hide.
        sampled = rng.sample(TRUTH_KEYS, keys_per_session)
        for tk in TRUTH_KEYS:
            if (
                tk.flip_at_session is not None
                and s in (tk.flip_at_session, tk.flip_at_session + 1)
                and tk not in sampled
            ):
                sampled.append(tk)
        for tk in sampled:
            events.append(_make_event(rng, s, session_start, tk, tk.truth_at(s), is_noise=False))
            # Right after a preference flips, evidence of the new truth is denser.
            if tk.flip_at_session is not None and s in (
                tk.flip_at_session,
                tk.flip_at_session + 1,
            ):
                events.append(
                    _make_event(rng, s, session_start, tk, tk.truth_at(s), is_noise=False)
                )

        # Noise: a misleading one-off exception about some key.
        if rng.random() < noise_probability:
            tk = rng.choice(TRUTH_KEYS)
            events.append(_make_event(rng, s, session_start, tk, tk.wrong_at(s), is_noise=True))

        events.sort(key=lambda e: e.occurred_at)
        by_session[s] = events
    return by_session


def dataset_summary(by_session: dict[int, list[MemoryEvent]]) -> dict:
    total = sum(len(v) for v in by_session.values())
    noise = sum(1 for evs in by_session.values() for e in evs if e.meta.get("noise"))
    return {
        "sessions": len(by_session),
        "events": total,
        "noise_events": noise,
        "keys": len(TRUTH_KEYS),
        "flips": [
            {"key": tk.key, "at_session": tk.flip_at_session, "to": tk.flip_to}
            for tk in TRUTH_KEYS
            if tk.flip_at_session is not None
        ],
        "synthetic": True,
    }
