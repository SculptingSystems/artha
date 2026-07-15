"""
Artha CLI. Runs a full analysis and prints the investment memo.
Usage: python demo.py "Analyze TCS"
       python demo.py "Should I buy HDFC Bank given the RBI rate pause?"
"""
import sys
import io
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

console = Console(force_terminal=True)

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


def render_memo(memo: dict):
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

    # Data snapshot table
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

    # Bull / Bear cases side by side
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

    # Risks
    if memo.get("risks"):
        risks_text = "\n".join(f"⚠  {r}" for r in memo["risks"])
        console.print(Panel(risks_text, title="[bold yellow]RISKS[/bold yellow]", border_style="yellow"))

    # Risk flags
    flags = data.get("risk_flags", [])
    if flags:
        console.print()
        flags_text = "\n".join(f"[red]⚠[/red]  {f}" for f in flags)
        console.print(Panel(flags_text, title="[bold red]REGULATORY FLAGS[/bold red]", border_style="red"))

    # News themes
    themes = data.get("news_themes", [])
    if themes:
        console.print()
        console.print(f"[bold]News Themes:[/bold] {' · '.join(themes)}")

    # Recommendation
    console.print()
    console.print(Panel(
        memo.get("recommendation", ""),
        title="[bold cyan]RECOMMENDATION[/bold cyan]",
        border_style="cyan",
    ))

    # Agent analyses
    console.print()
    console.rule("[dim]Agent Analyses[/dim]", style="dim")
    agents = memo.get("agent_analyses", {})
    agent_labels = {
        "market": "Market Data",
        "fundamentals": "Fundamentals",
        "news": "News & Sentiment",
        "regulatory": "Regulatory",
        "macro": "Macro",
    }
    for key, label in agent_labels.items():
        text = agents.get(key, "")
        if text:
            console.print(f"\n[bold dim]{label}:[/bold dim]")
            console.print(f"[dim]{text}[/dim]")

    # Cost
    cost = memo.get("cost_summary", {})
    console.print()
    console.print(Rule(style="dim"))
    console.print(
        f"[dim]tokens  in={cost.get('total_input_tokens', 0):,} "
        f"out: {cost.get('total_output_tokens', 0):,} | "
        f"Est. cost: ${cost.get('total_cost_usd', 0):.4f}[/dim]"
    )
    console.print()


def main():
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Analyze TCS"

    console.print(f"\n[bold cyan]Artha[/bold cyan]  Indian equity research")
    console.print(f"[dim]Query:[/dim] {query}\n")

    with console.status("[bold cyan]Running 5 agents in parallel...[/bold cyan]", spinner="dots"):
        start = time.time()
        orchestrator = Orchestrator()
        result = orchestrator.analyze(query)
        elapsed = time.time() - start

    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        if "hint" in result:
            console.print(f"[dim]Hint: {result['hint']}[/dim]")
        sys.exit(1)

    console.print(f"[dim]Analysis complete in {elapsed:.1f}s[/dim]")
    render_memo(result)


if __name__ == "__main__":
    main()
