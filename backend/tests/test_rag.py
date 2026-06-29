"""Unit tests for RAG / computed-field logic (Section 8 rules)."""

from datetime import date

from backend.core.enums import HighestRisk, Rag
from backend.core import rag


def test_highest_risk_none_when_empty():
    assert rag.highest_risk([]) == HighestRisk.NONE


def test_highest_risk_picks_max():
    assert rag.highest_risk(["LOW", "HIGH", "MEDIUM"]) == HighestRisk.HIGH
    assert rag.highest_risk(["LOW", "MEDIUM"]) == HighestRisk.MEDIUM
    assert rag.highest_risk(["LOW"]) == HighestRisk.LOW


def test_risk_rag_mapping():
    assert rag.risk_rag("LOW") == Rag.GREEN
    assert rag.risk_rag("MEDIUM") == Rag.AMBER
    assert rag.risk_rag("HIGH") == Rag.RED


def test_amp_expiry_rag_thresholds():
    today = date(2026, 6, 1)
    assert rag.amp_expiry_rag(None, today=today) == Rag.NONE
    assert rag.amp_expiry_rag(date(2026, 5, 31), today=today) == Rag.RED  # expired
    assert rag.amp_expiry_rag(date(2026, 6, 20), today=today) == Rag.AMBER  # within 30
    assert rag.amp_expiry_rag(date(2026, 6, 30), today=today) == Rag.AMBER  # exactly 29 days
    assert rag.amp_expiry_rag(date(2026, 8, 1), today=today) == Rag.GREEN  # > 30


def test_amp_expired_and_expiring_soon():
    today = date(2026, 6, 1)
    assert rag.is_amp_expired(date(2026, 5, 1), today=today) is True
    assert rag.is_amp_expired(date(2026, 7, 1), today=today) is False
    assert rag.is_amp_expiring_soon(date(2026, 6, 15), today=today) is True
    assert rag.is_amp_expiring_soon(date(2026, 8, 1), today=today) is False
