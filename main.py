"""
SpotifyCares AI Support Agent - Interactive CLI & Benchmark Testbed
"""

import argparse
from pathlib import Path
import sys
import time

# Force UTF-8 on Windows consoles to prevent cp1252 UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.agent.graph import run_support_agent
from src.rag.indexer import CaseIndexer

console = Console()


def display_agent_turn(query: str, state):
    """
    Renders an agent interaction in a rich visual format.
    """
    # 1. Customer Inquiry Panel
    console.print()
    console.print(
        Panel(
            Text(query, style="bold white"),
            title="[bold green]Customer Inquiry[/bold green]",
            border_style="green",
        )
    )

    # 2. Diagnostics & RAG Inspection Panel
    diag_table = Table(show_header=False, box=None, padding=(0, 1))
    diag_table.add_column("Key", style="bold cyan", width=18)
    diag_table.add_column("Value", style="white")

    diag_table.add_row("Detected Intent", f"[bold yellow]{state.intent}[/bold yellow]")
    platforms = state.device_info.get("platforms", [])
    diag_table.add_row("Detected Devices", ", ".join(platforms) if platforms else "Not specified")
    diag_table.add_row(
        "Escalation Needed",
        f"[bold red]YES ({state.escalation_reason})[/bold red]"
        if state.requires_escalation
        else "[green]No (Public Troubleshooting)[/green]",
    )
    diag_table.add_row("Retrieval Score", f"{state.confidence_score:.4f}" if state.confidence_score else "N/A")

    if state.retrieved_cases:
        top_case = state.retrieved_cases[0]
        diag_table.add_row(
            "Top Matched Case",
            f"ID: {top_case.get('case_id')} | Problem: {top_case.get('customer_problem')[:70]}...",
        )
        diag_table.add_row(
            "Historical Resolution",
            f"[italic dim]{top_case.get('resolution')[:120]}...[/italic dim]",
        )

    console.print(
        Panel(
            diag_table,
            title="[bold cyan]Session Diagnostics & Case Evidence[/bold cyan]",
            border_style="cyan",
        )
    )

    # 3. SpotifyCares Response Panel
    console.print(
        Panel(
            Text(state.final_response, style="bold bright_green"),
            title="[bold magenta]SpotifyCares Agent[/bold magenta]",
            border_style="magenta",
        )
    )

    # 4. Human-In-The-Loop (HITL) Handoff Dispatch Panel
    if getattr(state, "is_hitl", False) and state.handoff_ticket:
        ticket = state.handoff_ticket
        ticket_table = Table(show_header=False, box=None, padding=(0, 1))
        ticket_table.add_column("Key", style="bold red", width=22)
        ticket_table.add_column("Value", style="white")

        ticket_table.add_row("Ticket ID", f"[bold yellow]{ticket.get('ticket_id')}[/bold yellow]")
        ticket_table.add_row("Priority", f"[bold red]{ticket.get('priority')}[/bold red]")
        ticket_table.add_row("Frustration Level", f"[bold magenta]{ticket.get('frustration_level')}[/bold magenta]")
        ticket_table.add_row("Failed Attempts", str(ticket.get("failed_attempts", ticket.get("failed_troubleshooting_attempts", 0))))
        ticket_table.add_row("Conversation Turns", str(ticket.get("conversation_turns", 0)))
        ticket_table.add_row("Handoff Reason", f"[italic]{ticket.get('escalation_reason')}[/italic]")

        console.print(
            Panel(
                ticket_table,
                title="[bold red]Human-in-the-Loop (HITL) Handoff Ticket[/bold red]",
                border_style="red",
            )
        )


def interactive_chat():
    """
    Interactive terminal chat session with the Spotify support agent.
    """
    console.print(
        Panel(
            "[bold green]Spotify Support Assistant[/bold green]\n\n"
            "Type your issue below (or type [bold red]'exit'[/bold red] to quit).",
            border_style="green",
        )
    )

    history = []
    while True:
        try:
            console.print()
            query = console.input("[bold yellow]You > [/bold yellow]").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                console.print("[bold cyan]Thank you for using Spotify Support. Have a great day![/bold cyan]")
                break

            if query.lower() == "clear":
                history = []
                console.print("[dim]Conversation history cleared.[/dim]")
                continue

            with console.status("[bold green]Analyzing problem & retrieving historical solutions...[/bold green]"):
                state = run_support_agent(query, history=history)

            display_agent_turn(query, state)
            history = state.messages

        except KeyboardInterrupt:
            console.print("\n[bold cyan]Session closed.[/bold cyan]")
            break
        except Exception as e:
            console.print(f"[bold red]Error processing inquiry:[/bold red] {e}")


def run_eval():
    """
    Evaluates the agent on canonical Spotify support scenarios.
    """
    benchmark_queries = [
        ("Playback / Bluetooth", "Spotify keeps skipping tracks on my Anker bluetooth speaker"),
        ("Offline Storage", "My downloaded playlists are grayed out and won't play offline on Android"),
        ("App Stability", "Spotify app keeps crashing and closing on my Windows 11 PC when opening"),
        ("Account Escalation", "I noticed an unauthorized charge of $15 on my card that I didn't make"),
        ("HITL Frustration", "This is ridiculous, nothing you suggested works and your app is completely broken!"),
        ("HITL Human Request", "I demand to speak to a real human representative right now."),
    ]

    table = Table(title="SpotifyCares Agent Benchmark & Retrieval Evaluation", show_lines=True)
    table.add_column("Category", style="bold cyan")
    table.add_column("Customer Query", style="white")
    table.add_column("Intent", style="bold yellow")
    table.add_column("Score", justify="right", style="magenta")
    table.add_column("Escalated?", style="bold")
    table.add_column("Response Preview", style="green")

    for cat, q in benchmark_queries:
        state = run_support_agent(q)
        escalated = "[red]YES[/red]" if state.requires_escalation else "[green]No[/green]"
        preview = state.final_response.replace("\n", " ")[:60] + "..."
        score_str = f"{state.confidence_score:.3f}" if state.confidence_score else "N/A"
        table.add_row(cat, q, state.intent, score_str, escalated, preview)

    console.print(table)


def main():
    parser = argparse.ArgumentParser(description="SpotifyCares Case-Based AI Support Agent")
    parser.add_argument("--query", "-q", type=str, help="Run a single query and exit")
    parser.add_argument("--eval", action="store_true", help="Run benchmark evaluation queries")
    parser.add_argument("--index", action="store_true", help="Index cases into Elasticsearch")
    parser.add_argument("--recreate", action="store_true", help="Recreate Elasticsearch index")
    parser.add_argument("--limit", type=int, default=None, help="Limit indexing count")
    args = parser.parse_args()

    if args.index:
        indexer = CaseIndexer()
        indexer.setup_index(recreate=args.recreate)
        indexer.index_cases("data/processed/spotify_troubleshooting_cases.jsonl", limit=args.limit)
    elif args.eval:
        run_eval()
    elif args.query:
        state = run_support_agent(args.query)
        display_agent_turn(args.query, state)
    else:
        interactive_chat()


if __name__ == "__main__":
    main()
