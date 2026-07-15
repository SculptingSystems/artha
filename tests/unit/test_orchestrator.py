import pytest
from unittest.mock import MagicMock, patch

from agents.orchestrator import Orchestrator


@pytest.fixture
def orchestrator():
    with patch("agents.orchestrator.LLMClient"), \
         patch("agents.orchestrator.AnalysisMemory"), \
         patch("agents.orchestrator.MarketDataAgent"), \
         patch("agents.orchestrator.FundamentalsAgent"), \
         patch("agents.orchestrator.NewsSentimentAgent"), \
         patch("agents.orchestrator.RegulatoryAgent"), \
         patch("agents.orchestrator.MacroAgent"):
        return Orchestrator()


def test_extract_symbol_by_name(orchestrator):
    assert orchestrator._extract_symbol("Analyze TCS performance") == "TCS"
    assert orchestrator._extract_symbol("reliance industries outlook") == "RELIANCE"
    assert orchestrator._extract_symbol("hdfc bank Q4 results") == "HDFCBANK"
    assert orchestrator._extract_symbol("should I buy infosys") == "INFY"


def test_extract_symbol_by_ticker(orchestrator):
    assert orchestrator._extract_symbol("What about WIPRO.NS stock?") == "WIPRO"


def test_extract_symbol_returns_none_for_unknown(orchestrator):
    result = orchestrator._extract_symbol("what is the weather today")
    assert result is None


def test_parse_memo_extracts_verdict(orchestrator):
    content = """VERDICT: BUY

SUMMARY: TCS is a strong long-term buy.

BULL_CASE:
- Market leader in IT services
- Strong cash generation

BEAR_CASE:
- Macro headwinds from US slowdown
- Currency risk

RISKS:
- Client concentration in BFSI

RECOMMENDATION: Accumulate on dips below Rs 3800."""

    parsed = orchestrator._parse_memo(content)
    assert parsed["verdict"] == "BUY"
    assert "TCS" in parsed["summary"]
    assert len(parsed["bull_case"]) == 2
    assert len(parsed["bear_case"]) == 2
    assert len(parsed["risks"]) == 1
    assert "Rs 3800" in parsed["recommendation"]


def test_parse_memo_handles_sell(orchestrator):
    content = "VERDICT: SELL\nSUMMARY: High risk.\nBULL_CASE:\nBEAR_CASE:\nRISKS:\nRECOMMENDATION: Exit."
    parsed = orchestrator._parse_memo(content)
    assert parsed["verdict"] == "SELL"


def test_analyze_returns_error_for_unknown_query(orchestrator):
    orchestrator.memory.recall.return_value = []
    result = orchestrator.analyze("what is the weather in Mumbai")
    assert "error" in result


def test_analyze_runs_all_agents(orchestrator):
    orchestrator.memory.recall.return_value = []
    orchestrator.memory.save.return_value = "some-id"

    mock_agent_result = {
        "analysis": "Test analysis.",
        "raw_data": {},
        "sentiment": "POSITIVE",
        "key_themes": ["growth"],
        "risk_flags": [],
        "shareholding": {"promoter_holding_pct": 72},
        "macro_data": {"macro_stance": "neutral"},
    }

    orchestrator.market_agent.run.return_value = mock_agent_result
    orchestrator.fundamentals_agent.run.return_value = mock_agent_result
    orchestrator.news_agent.run.return_value = mock_agent_result
    orchestrator.regulatory_agent.run.return_value = mock_agent_result
    orchestrator.macro_agent.run.return_value = mock_agent_result

    orchestrator.llm.chat.return_value = {
        "content": "VERDICT: BUY\nSUMMARY: Good.\nBULL_CASE:\n- Strong\nBEAR_CASE:\n- Risk\nRISKS:\n- None\nRECOMMENDATION: Buy.",
        "input_tokens": 100,
        "output_tokens": 50,
    }

    result = orchestrator.analyze("Analyze TCS")

    assert result.get("symbol") == "TCS"
    assert "verdict" in result
    orchestrator.market_agent.run.assert_called_once()
    orchestrator.fundamentals_agent.run.assert_called_once()
    orchestrator.news_agent.run.assert_called_once()
    orchestrator.regulatory_agent.run.assert_called_once()
    orchestrator.macro_agent.run.assert_called_once()
