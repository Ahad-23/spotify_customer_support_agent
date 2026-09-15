"""
Dataset validation and quality check for extracted Spotify cases.
"""

import json
from collections import Counter
from rich.console import Console
from rich.table import Table

console = Console()

def validate(file_path: str):
    console.print(f"[bold cyan]Validating dataset:[/bold cyan] {file_path}")
    case_ids = set()
    duplicates = 0
    empty_messages = 0
    empty_resolutions = 0
    turn_counts = []
    intents = Counter()
    has_troubleshooting_cnt = 0
    resolved_in_public_cnt = 0
    total = 0

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            total += 1
            case = json.loads(line)
            cid = case.get("case_id")
            if cid in case_ids:
                duplicates += 1
            case_ids.add(cid)

            if not case.get("customer_message"):
                empty_messages += 1
            if not case.get("resolution"):
                empty_resolutions += 1

            t_count = case.get("metadata", {}).get("turn_count", 0)
            turn_counts.append(t_count)
            intents[case.get("intent", "unknown")] += 1

            if case.get("metadata", {}).get("has_troubleshooting"):
                has_troubleshooting_cnt += 1
            if case.get("metadata", {}).get("resolved_in_public"):
                resolved_in_public_cnt += 1

    table = Table(title=f"Dataset Validation Report: {file_path}", show_lines=True)
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Cases", f"{total:,}")
    table.add_row("Unique Cases", f"{len(case_ids):,}")
    table.add_row("Duplicate IDs", f"{duplicates:,}")
    table.add_row("Empty Customer Messages", f"{empty_messages:,}")
    table.add_row("Empty Resolutions", f"{empty_resolutions:,}")
    table.add_row("Avg Turns per Case", f"{sum(turn_counts)/total:.2f}" if total else "0")
    table.add_row("Cases with Troubleshooting", f"{has_troubleshooting_cnt:,} ({(has_troubleshooting_cnt/total*100):.1f}%)" if total else "0")
    table.add_row("Cases Resolved in Public", f"{resolved_in_public_cnt:,} ({(resolved_in_public_cnt/total*100):.1f}%)" if total else "0")

    console.print(table)


if __name__ == "__main__":
    validate("data/processed/spotify_troubleshooting_cases.jsonl")
