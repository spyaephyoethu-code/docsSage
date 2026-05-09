"""
In-memory daily budget guards for external APIs.
Counters reset at the start of each UTC day (first request of the day).
All state is process-local — acceptable for a single-process Railway deployment.
"""

from collections import defaultdict
from datetime import date

from app.domain.exceptions import BudgetExceeded

# Tune these to stay within free-tier / acceptable spend.
_GROQ_DAILY_TOKEN_LIMIT = 500_000
_VOYAGE_DAILY_TOKEN_LIMIT = 10_000_000
_COHERE_DAILY_CALL_LIMIT = 500

_counts: dict[tuple[str, date], int] = defaultdict(int)


def _today() -> date:
    return date.today()


# ── Groq ──────────────────────────────────────────────────────────────────────


def check_groq_budget() -> None:
    if _counts[("groq", _today())] >= _GROQ_DAILY_TOKEN_LIMIT:
        raise BudgetExceeded(
            "Daily Groq token budget reached — service paused until midnight UTC"
        )


def record_groq_usage(tokens: int) -> None:
    _counts[("groq", _today())] += tokens


# ── Voyage ────────────────────────────────────────────────────────────────────


def check_voyage_budget() -> None:
    if _counts[("voyage", _today())] >= _VOYAGE_DAILY_TOKEN_LIMIT:
        raise BudgetExceeded(
            "Daily Voyage token budget reached — new ingestions paused until midnight UTC"
        )


def record_voyage_usage(tokens: int) -> None:
    _counts[("voyage", _today())] += tokens


# ── Cohere ────────────────────────────────────────────────────────────────────


def check_cohere_budget() -> None:
    if _counts[("cohere", _today())] >= _COHERE_DAILY_CALL_LIMIT:
        raise BudgetExceeded("Daily Cohere call budget reached")


def record_cohere_usage() -> None:
    _counts[("cohere", _today())] += 1
