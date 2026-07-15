import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

from tools.nse_tools import (
    _ticker,
    _safe,
    _safe_pct,
    _to_crores,
    _compute_rsi,
    get_price_data,
    get_fundamentals,
)


def test_ticker_adds_ns_suffix():
    assert _ticker("RELIANCE") == "RELIANCE.NS"
    assert _ticker("tcs") == "TCS.NS"


def test_ticker_keeps_existing_suffix():
    assert _ticker("RELIANCE.NS") == "RELIANCE.NS"
    assert _ticker("HDFCBANK.BO") == "HDFCBANK.BO"


def test_safe_rounds_float():
    assert _safe(12.3456) == 12.35
    assert _safe(None) is None
    assert _safe("bad") is None


def test_safe_pct_multiplies_by_100():
    assert _safe_pct(0.175) == 17.5
    assert _safe_pct(None) is None


def test_to_crores():
    assert _to_crores(1_00_00_000) == 1.0
    assert _to_crores(None) is None


def test_compute_rsi_returns_value():
    prices = pd.Series([float(i) + (i % 3) for i in range(1, 30)])
    rsi = _compute_rsi(prices)
    assert rsi is not None
    assert 0 <= rsi <= 100


def test_compute_rsi_insufficient_data():
    prices = pd.Series([100.0, 101.0, 102.0])
    assert _compute_rsi(prices) is None


@patch("tools.nse_tools.yf.Ticker")
def test_get_price_data_success(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "longName": "Tata Consultancy Services",
        "sector": "Technology",
        "industry": "IT Services",
    }
    dates = pd.date_range("2025-01-01", periods=260, freq="B")
    mock_ticker.history.return_value = pd.DataFrame({
        "Close": np.linspace(3500, 4200, 260),
        "Volume": [1_000_000] * 260,
    }, index=dates)
    mock_ticker_cls.return_value = mock_ticker

    result = get_price_data("TCS", period="1y")

    assert "error" not in result
    assert result["symbol"] == "TCS"
    assert result["current_price"] > 0
    assert "period_return_pct" in result
    assert "rsi_14" in result


@patch("tools.nse_tools.yf.Ticker")
def test_get_price_data_empty_returns_error(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.info = {}
    mock_ticker.history.return_value = pd.DataFrame()
    mock_ticker_cls.return_value = mock_ticker

    result = get_price_data("FAKESYMBOL")
    assert "error" in result


@patch("tools.nse_tools.yf.Ticker")
def test_get_fundamentals_success(mock_ticker_cls):
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "marketCap": 1_50_00_00_00_000,
        "trailingPE": 28.5,
        "forwardPE": 25.0,
        "priceToBook": 11.2,
        "returnOnEquity": 0.52,
        "profitMargins": 0.21,
        "debtToEquity": 0.0,
        "currentRatio": 3.1,
        "totalRevenue": 2_40_000_00_00_000,
        "netIncomeToCommon": 47_000_00_00_000,
        "trailingEps": 130.0,
        "dividendYield": 0.017,
        "bookValue": 350.0,
        "sector": "Technology",
    }
    mock_ticker_cls.return_value = mock_ticker

    result = get_fundamentals("TCS")

    assert "error" not in result
    assert result["pe_ratio"] == 28.5
    assert result["roe_pct"] == 52.0
    assert result["sector"] == "Technology"
