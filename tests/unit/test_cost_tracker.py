import pytest
from core.cost_tracker import CostTracker


@pytest.fixture
def tracker():
    return CostTracker()


def test_records_cost_for_known_model(tracker):
    entry = tracker.record("q1", "claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
    expected = (1000 * 3.0 + 500 * 15.0) / 1_000_000
    assert abs(entry.cost_usd - expected) < 1e-9


def test_session_total_accumulates(tracker):
    tracker.record("q1", "gpt-4o", input_tokens=1000, output_tokens=200)
    tracker.record("q2", "gpt-4o", input_tokens=500, output_tokens=100)
    assert tracker.session_total() > 0
    assert len(tracker._queries) == 2


def test_session_summary_keys(tracker):
    tracker.record("q1", "claude-haiku-4-5", input_tokens=200, output_tokens=100)
    summary = tracker.session_summary()
    assert "total_queries" in summary
    assert "total_input_tokens" in summary
    assert "total_output_tokens" in summary
    assert "total_cost_usd" in summary
    assert summary["total_queries"] == 1


def test_unknown_model_uses_default_rate(tracker):
    entry = tracker.record("q1", "unknown-model-xyz", input_tokens=1000, output_tokens=1000)
    assert entry.cost_usd > 0


def test_zero_tokens_zero_cost(tracker):
    entry = tracker.record("q1", "gpt-4o", input_tokens=0, output_tokens=0)
    assert entry.cost_usd == 0.0
