from datetime import date
from unittest.mock import patch

import pytest

from app.core import circuit_breaker
from app.domain.exceptions import BudgetExceeded


def reset_counts():
    circuit_breaker._counts.clear()


@pytest.fixture(autouse=True)
def clear_state():
    reset_counts()
    yield
    reset_counts()


# ── Groq ──────────────────────────────────────────────────────────────────────

def test_groq_budget_not_exceeded_when_under_limit():
    circuit_breaker.record_groq_usage(100)
    circuit_breaker.check_groq_budget()  # should not raise


def test_groq_budget_raises_when_limit_reached():
    circuit_breaker.record_groq_usage(circuit_breaker._GROQ_DAILY_TOKEN_LIMIT)
    with pytest.raises(BudgetExceeded):
        circuit_breaker.check_groq_budget()


def test_groq_usage_accumulates():
    circuit_breaker.record_groq_usage(100)
    circuit_breaker.record_groq_usage(200)
    key = ("groq", date.today())
    assert circuit_breaker._counts[key] == 300


def test_groq_budget_resets_on_new_day():
    circuit_breaker.record_groq_usage(circuit_breaker._GROQ_DAILY_TOKEN_LIMIT)

    future_date = date(2099, 1, 1)
    with patch.object(circuit_breaker, "_today", return_value=future_date):
        circuit_breaker.check_groq_budget()  # should not raise on a new day


# ── Voyage ────────────────────────────────────────────────────────────────────

def test_voyage_budget_not_exceeded_when_under_limit():
    circuit_breaker.record_voyage_usage(100)
    circuit_breaker.check_voyage_budget()  # should not raise


def test_voyage_budget_raises_when_limit_reached():
    circuit_breaker.record_voyage_usage(circuit_breaker._VOYAGE_DAILY_TOKEN_LIMIT)
    with pytest.raises(BudgetExceeded):
        circuit_breaker.check_voyage_budget()


def test_voyage_usage_accumulates():
    circuit_breaker.record_voyage_usage(1000)
    circuit_breaker.record_voyage_usage(2000)
    key = ("voyage", date.today())
    assert circuit_breaker._counts[key] == 3000


def test_voyage_budget_resets_on_new_day():
    circuit_breaker.record_voyage_usage(circuit_breaker._VOYAGE_DAILY_TOKEN_LIMIT)

    future_date = date(2099, 1, 1)
    with patch.object(circuit_breaker, "_today", return_value=future_date):
        circuit_breaker.check_voyage_budget()  # should not raise


# ── Cohere ────────────────────────────────────────────────────────────────────

def test_cohere_budget_not_exceeded_when_under_limit():
    circuit_breaker.record_cohere_usage()
    circuit_breaker.check_cohere_budget()  # should not raise


def test_cohere_budget_raises_when_limit_reached():
    for _ in range(circuit_breaker._COHERE_DAILY_CALL_LIMIT):
        circuit_breaker.record_cohere_usage()
    with pytest.raises(BudgetExceeded):
        circuit_breaker.check_cohere_budget()


def test_cohere_each_call_increments_by_one():
    circuit_breaker.record_cohere_usage()
    circuit_breaker.record_cohere_usage()
    key = ("cohere", date.today())
    assert circuit_breaker._counts[key] == 2


def test_cohere_budget_resets_on_new_day():
    for _ in range(circuit_breaker._COHERE_DAILY_CALL_LIMIT):
        circuit_breaker.record_cohere_usage()

    future_date = date(2099, 1, 1)
    with patch.object(circuit_breaker, "_today", return_value=future_date):
        circuit_breaker.check_cohere_budget()  # should not raise
