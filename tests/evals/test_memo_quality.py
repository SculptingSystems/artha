"""Eval tests for memo quality. Skipped without a real API key."""
import os
import pytest
from unittest.mock import patch, MagicMock

from agents.orchestrator import Orchestrator


def _mock_agent_output(analysis_text: str) -> dict:
    return {
        "analysis": analysis_text,
        "raw_data": {"current_price": 3800, "period_return_pct": 12.5, "nifty50_return_pct": 8.0,
                     "pe_ratio": 28.5, "roe_pct": 52.0},
        "sentiment": "POSITIVE",
        "key_themes": ["Q4 beat", "AI demand"],
        "risk_flags": [],
        "shareholding": {"promoter_holding_pct": 72.3, "fii_holding_pct": 13.7},
        "macro_data": {"macro_stance": "neutral"},
    }


@pytest.fixture
def orchestrator_with_mocked_agents():
    with patch("agents.orchestrator.AnalysisMemory") as mock_mem:
        mock_mem.return_value.recall.return_value = []
        mock_mem.return_value.save.return_value = "id"
        orch = Orchestrator()
        orch.market_agent.run = MagicMock(return_value=_mock_agent_output("Strong technical setup."))
        orch.fundamentals_agent.run = MagicMock(return_value=_mock_agent_output("Valuation is fair."))
        orch.news_agent.run = MagicMock(return_value=_mock_agent_output("Positive sentiment."))
        orch.regulatory_agent.run = MagicMock(return_value=_mock_agent_output("Promoters hold 72%."))
        orch.macro_agent.run = MagicMock(return_value=_mock_agent_output("Macro neutral."))
        return orch


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "").startswith("sk-ant-dummy"),
    reason="Requires real API key",
)
def test_memo_contains_required_fields(orchestrator_with_mocked_agents):
    result = orchestrator_with_mocked_agents.analyze("Analyze TCS")

    assert "verdict" in result, "Memo must contain a verdict"
    assert "summary" in result, "Memo must contain a summary"
    assert "bull_case" in result, "Memo must contain bull case"
    assert "bear_case" in result, "Memo must contain bear case"
    assert "recommendation" in result, "Memo must contain a recommendation"


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "").startswith("sk-ant-dummy"),
    reason="Requires real API key",
)
def test_verdict_is_valid(orchestrator_with_mocked_agents):
    result = orchestrator_with_mocked_agents.analyze("Analyze TCS")
    assert result["verdict"] in ("BUY", "HOLD", "SELL", "AVOID"), \
        f"Unexpected verdict: {result['verdict']}"


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "").startswith("sk-ant-dummy"),
    reason="Requires real API key",
)
def test_summary_is_substantive(orchestrator_with_mocked_agents):
    result = orchestrator_with_mocked_agents.analyze("Analyze TCS")
    summary = result.get("summary", "")
    assert len(summary) > 50, f"Summary too short: '{summary}'"
    assert "TCS" in summary or "tcs" in summary.lower(), \
        "Summary should reference the company"


@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "").startswith("sk-ant-dummy"),
    reason="Requires real API key",
)
def test_bull_bear_case_not_empty(orchestrator_with_mocked_agents):
    result = orchestrator_with_mocked_agents.analyze("Analyze TCS")
    assert len(result.get("bull_case", [])) >= 2, "Bull case must have at least 2 points"
    assert len(result.get("bear_case", [])) >= 2, "Bear case must have at least 2 points"
