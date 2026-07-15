"""
Generates SVG screenshots of live Artha analysis output for the README.
Run once: python capture_screenshots.py
"""
import sys
import io
import os
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box
from rich.text import Text
from rich.rule import Rule

from agents.orchestrator import Orchestrator
from core.cost_tracker import cost_tracker

VERDICT_COLORS = {
    "BUY": "bold green",
    "HOLD": "bold yellow",
    "SELL": "bold red",
    "AVOID": "bold red",
}

SENTIMENT_COLORS = {
    "POSITIVE": "green",
    "NEGATIVE": "red",
    "NEUTRAL": "yellow",
    "MIXED": "blue",
}

MACRO_COLORS = {
    "bullish": "green",
    "bearish": "red",
    "neutral": "yellow",
    "tailwind": "green",
    "headwind": "red",
}


def render_memo(console: Console, memo: dict):
    symbol = memo.get("symbol", "")
    verdict = memo.get("verdict", "HOLD")
    data = memo.get("data_snapshot", {})

    console.print()
    console.rule(f"[bold cyan]ARTHA / {symbol}[/bold cyan]", style="cyan")
    console.print()

    verdict_color = VERDICT_COLORS.get(verdict, "white")
    console.print(Panel(
        f"[{verdict_color}]{verdict}[/{verdict_color}]",
        title="[bold]VERDICT[/bold]",
        border_style="cyan",
        expand=False,
    ))

    console.print()
    console.print(Panel(
        memo.get("summary", ""),
        title="[bold]SUMMARY[/bold]",
        border_style="white",
    ))

    console.print()

    snapshot = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    snapshot.add_column("Metric", style="dim")
    snapshot.add_column("Value")

    price = data.get("price")
    ret = data.get("period_return_pct")
    nifty = data.get("nifty50_return_pct")
    sentiment = data.get("news_sentiment", "NEUTRAL")
    macro = data.get("macro_stance", "neutral")

    if price and price != "N/A":
        snapshot.add_row("Current Price", f"Rs {price}")
    if ret is not None and ret != "N/A":
        color = "green" if float(ret) > 0 else "red"
        snapshot.add_row("1Y Return", f"[{color}]{ret}%[/{color}]")
    if nifty is not None and nifty != "N/A":
        snapshot.add_row("NIFTY 50 Return", f"{nifty}%")
    if data.get("pe_ratio") not in (None, "N/A"):
        snapshot.add_row("P/E Ratio", f"{data['pe_ratio']}x")
    if data.get("roe_pct") not in (None, "N/A"):
        snapshot.add_row("ROE", f"{data['roe_pct']}%")
    if data.get("promoter_holding_pct") not in (None, "N/A"):
        snapshot.add_row("Promoter Holding", f"{data['promoter_holding_pct']}%")

    sent_color = SENTIMENT_COLORS.get(sentiment, "white")
    snapshot.add_row("News Sentiment", f"[{sent_color}]{sentiment}[/{sent_color}]")

    macro_color = MACRO_COLORS.get(macro.lower(), "white")
    snapshot.add_row("Macro Stance", f"[{macro_color}]{macro.upper()}[/{macro_color}]")

    console.print(Panel(snapshot, title="[bold]DATA SNAPSHOT[/bold]", border_style="cyan"))

    bull_text = Text()
    for point in memo.get("bull_case", []):
        bull_text.append(f"+ {point}\n", style="green")

    bear_text = Text()
    for point in memo.get("bear_case", []):
        bear_text.append(f"- {point}\n", style="red")

    console.print()
    console.print(Columns([
        Panel(bull_text, title="[bold green]BULL CASE[/bold green]", border_style="green"),
        Panel(bear_text, title="[bold red]BEAR CASE[/bold red]", border_style="red"),
    ]))

    if memo.get("risks"):
        risks_text = "\n".join(f"!  {r}" for r in memo["risks"])
        console.print(Panel(risks_text, title="[bold yellow]RISKS[/bold yellow]", border_style="yellow"))

    flags = data.get("risk_flags", [])
    if flags:
        console.print()
        flags_text = "\n".join(f"!  {f}" for f in flags)
        console.print(Panel(flags_text, title="[bold red]REGULATORY FLAGS[/bold red]", border_style="red"))

    themes = data.get("news_themes", [])
    if themes:
        console.print()
        console.print(f"[bold]News Themes:[/bold] {' · '.join(themes)}")

    console.print()
    console.print(Panel(
        memo.get("recommendation", ""),
        title="[bold cyan]RECOMMENDATION[/bold cyan]",
        border_style="cyan",
    ))

    cost = memo.get("cost_summary", {})
    console.print()
    console.print(Rule(style="dim"))
    console.print(
        f"[dim]tokens  in={cost.get('total_input_tokens', 0):,} "
        f"out: {cost.get('total_output_tokens', 0):,} | "
        f"Est. cost: ${cost.get('total_cost_usd', 0):.4f}[/dim]"
    )
    console.print()


def capture(query: str, filename: str, title: str):
    print(f"Capturing: {query} -> {filename}")
    console = Console(record=True, force_terminal=True, width=100, highlight=False)

    console.print(f"\n[bold cyan]Artha[/bold cyan]  Indian equity research")
    console.print(f"[dim]Query:[/dim] {query}\n")

    start = time.time()
    orchestrator = Orchestrator()
    result = orchestrator.analyze(query)
    elapsed = time.time() - start

    if "error" in result:
        print(f"  Error: {result['error']}")
        return

    console.print(f"[dim]Analysis complete in {elapsed:.1f}s[/dim]")
    render_memo(console, result)

    os.makedirs("screenshots", exist_ok=True)
    console.save_svg(f"screenshots/{filename}", title=title)
    print(f"  Saved screenshots/{filename}")


if __name__ == "__main__":
    capture("Analyze TCS", "tcs_analysis.svg", "TCS Analysis")
    time.sleep(3)
    capture(
        "Should I buy HDFC Bank given the RBI rate pause?",
        "hdfcbank_analysis.svg",
        "HDFC Bank Analysis",
    )
    print("\nDone.")
