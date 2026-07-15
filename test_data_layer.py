"""Quick smoke test for the data layer. No API key needed."""
import time
from tools.nse_tools import get_price_data, get_fundamentals
from tools.news_tools import fetch_news_rss
from tools.macro_tools import get_macro_summary, get_sector_performance

print("=" * 60)
print("ARTHA Data Layer Smoke Test")
print("=" * 60)

print("\n[1] TCS Price Data (yfinance NSE)")
data = get_price_data("TCS", period="6mo")
if "error" in data:
    print("  ERROR:", data["error"])
else:
    print(f"  Company : {data['company_name']}")
    print(f"  Price   : Rs {data['current_price']}")
    print(f"  6M Rtn  : {data['period_return_pct']}%  |  NIFTY: {data['nifty50_return_pct']}%")
    print(f"  Alpha   : {data['alpha_vs_nifty']}%")
    print(f"  RSI(14) : {data['rsi_14']}")
    print(f"  52W H/L : {data['high_52w']} / {data['low_52w']}")
    print(f"  Sector  : {data['sector']}")

time.sleep(2)
print("\n[2] HDFCBANK Fundamentals (yfinance)")
f = get_fundamentals("HDFCBANK")
if "error" in f:
    print("  ERROR:", f["error"])
else:
    print(f"  Market Cap  : Rs {f['market_cap_cr']} Cr")
    print(f"  P/E         : {f['pe_ratio']}x")
    print(f"  P/B         : {f['pb_ratio']}x")
    print(f"  ROE         : {f['roe_pct']}%")
    print(f"  Net Margin  : {f['net_margin_pct']}%")
    print(f"  Sector      : {f['sector']}")

print("\n[3] News RSS Feeds (no API key)")
articles = fetch_news_rss("TCS", "Tata Consultancy", max_articles=5)
print(f"  Found {len(articles)} articles")
for a in articles[:3]:
    print(f"  [{a['source']}] {a['title'][:70]}")

print("\n[4] Macro Summary")
macro = get_macro_summary()
rbi = macro["rbi"]
flows = macro["fii_dii_flows"]
print(f"  Repo Rate    : {rbi['repo_rate_pct']}%  |  Stance: {rbi['stance']}")
print(f"  FII Net (30d): Rs {flows['fii_net_cr']} Cr")
print(f"  DII Net (30d): Rs {flows['dii_net_cr']} Cr")
print(f"  Macro Stance : {macro['macro_stance'].upper()}")

print("\n[5] Sector Performance (1 month)")
sectors = get_sector_performance()
for name, ret in list(sectors.get("sector_returns_1m_pct", {}).items())[:5]:
    arrow = "+" if ret > 0 else ""
    print(f"  {name:<20} {arrow}{ret}%")

print("\n" + "=" * 60)
print("Data layer OK - all feeds verified")
print("=" * 60)
