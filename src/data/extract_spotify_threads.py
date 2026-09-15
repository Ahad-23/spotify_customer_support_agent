"""
SpotifyCares Conversation Tree Extractor & RAG Dataset Builder

Reconstructs multi-turn conversational trees for SpotifyCares from twcs.csv,
cleans Twitter artifacts, classifies customer intents, extracts agent resolutions,
and outputs structured JSONL cases ready for embedding and RAG retrieval.
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
import polars as pl
from rich.console import Console
from rich.table import Table

from cleaner import clean_tweet_text, analyze_agent_response, score_agent_resolution
from intent_classifier import classify_intent

console = Console()


def extract_spotify_cases(input_file: str, output_dir: str = "data/processed", min_turns: int = 2):
    t_start = time.time()
    console.print(f"[bold cyan]Reading dataset:[/bold cyan] {input_file}")
    
    if not os.path.exists(input_file):
        console.print(f"[bold red]File not found:[/bold red] {input_file}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    # 1. Load data with Polars
    df = pl.read_csv(
        input_file,
        schema_overrides={
            "tweet_id": pl.Int64,
            "author_id": pl.Utf8,
            "inbound": pl.Boolean,
            "created_at": pl.Utf8,
            "text": pl.Utf8,
            "response_tweet_id": pl.Utf8,
            "in_response_to_tweet_id": pl.Float64,
        },
        ignore_errors=True
    )
    console.print(f"Loaded [bold green]{len(df):,}[/bold green] total tweets in {time.time() - t_start:.2f}s")

    # 2. Extract column arrays for fast indexing
    df_clean = df.select([
        "tweet_id",
        "author_id",
        "inbound",
        "created_at",
        "text",
        "in_response_to_tweet_id"
    ]).with_columns(
        pl.col("in_response_to_tweet_id").cast(pl.Int64)
    )

    tweet_ids = df_clean["tweet_id"].to_list()
    authors = df_clean["author_id"].to_list()
    inbounds = df_clean["inbound"].to_list()
    created_ats = df_clean["created_at"].to_list()
    texts = df_clean["text"].to_list()
    parents = df_clean["in_response_to_tweet_id"].to_list()

    tweet_to_idx = {tid: i for i, tid in enumerate(tweet_ids)}
    
    parent_to_children: Dict[int, List[int]] = {}
    for tid, pid in zip(tweet_ids, parents):
        if pid is not None:
            parent_to_children.setdefault(pid, []).append(tid)

    # 3. Find all SpotifyCares tweets and climb up to root inbound tweets
    console.print("Identifying SpotifyCares threads and tracing roots...")
    spotify_tweet_indices = [
        i for i, (auth, inb) in enumerate(zip(authors, inbounds))
        if auth == "SpotifyCares" and not inb
    ]
    console.print(f"Total SpotifyCares outbound tweets: [bold green]{len(spotify_tweet_indices):,}[/bold green]")

    root_tweet_ids = set()
    for idx in spotify_tweet_indices:
        curr_tid = tweet_ids[idx]
        visited_climb = set()
        while curr_tid in tweet_to_idx:
            visited_climb.add(curr_tid)
            c_idx = tweet_to_idx[curr_tid]
            pid = parents[c_idx]
            if pid is None or pid not in tweet_to_idx or pid in visited_climb:
                root_tweet_ids.add(curr_tid)
                break
            curr_tid = pid

    console.print(f"Found [bold green]{len(root_tweet_ids):,}[/bold green] unique root tweets for SpotifyCares.")

    # 4. Linearize conversation trees into ordered dialog turns
    cases = []
    high_quality_cases = []

    for root_tid in root_tweet_ids:
        if root_tid not in tweet_to_idx:
            continue

        root_idx = tweet_to_idx[root_tid]
        # Skip if root itself is not inbound
        if not inbounds[root_idx]:
            continue

        # Traverse primary thread path (chronological tree)
        # Using BFS to collect all tweets in this specific thread
        thread_tids = []
        queue = [root_tid]
        visited = set()

        while queue:
            tid = queue.pop(0)
            if tid in visited:
                continue
            visited.add(tid)
            thread_tids.append(tid)

            # Sort children by tweet_id / creation if multiple
            children = parent_to_children.get(tid, [])
            for child in children:
                if child not in visited:
                    queue.append(child)

        # Build chronologically ordered sequence of turns
        thread_tweets = [
            {
                "tweet_id": tid,
                "author_id": authors[tweet_to_idx[tid]],
                "inbound": inbounds[tweet_to_idx[tid]],
                "text": texts[tweet_to_idx[tid]] or "",
                "created_at": created_ats[tweet_to_idx[tid]],
            }
            for tid in thread_tids
            if tid in tweet_to_idx
        ]

        if not thread_tweets:
            continue

        # Check that SpotifyCares participated
        has_spotify = any(t["author_id"] == "SpotifyCares" for t in thread_tweets)
        if not has_spotify:
            continue

        # Reconstruct turns
        turns = []
        conversation_dialogue = []
        agent_resolutions = []
        has_troubleshooting = False
        is_deflection_thread = False

        customer_msg = ""
        for i, t in enumerate(thread_tweets):
            is_agent = t["author_id"] == "SpotifyCares"
            speaker = "agent" if is_agent else "customer"
            clean_text = clean_tweet_text(t["text"], is_agent=is_agent)
            
            if not clean_text:
                continue

            if i == 0 and speaker == "customer":
                customer_msg = clean_text

            if is_agent:
                is_deflect, has_trouble = analyze_agent_response(clean_text)
                if is_deflect:
                    is_deflection_thread = True
                if has_trouble:
                    has_troubleshooting = True
                agent_resolutions.append(clean_text)

            speaker_label = "SpotifyCares" if is_agent else "Customer"
            conversation_dialogue.append(f"{speaker_label}: {clean_text}")

            turns.append({
                "turn": len(turns) + 1,
                "speaker": speaker,
                "text": clean_text,
                "tweet_id": t["tweet_id"],
                "created_at": t["created_at"],
            })

        if len(turns) < min_turns or not customer_msg:
            continue

        # Determine overall resolution summary text
        # Pick the most actionable agent response based on scoring
        best_resolution = ""
        if agent_resolutions:
            best_resolution = max(agent_resolutions, key=lambda r: score_agent_resolution(r))

        intent = classify_intent(customer_msg)

        case_obj = {
            "case_id": f"spotify_case_{root_tid}",
            "intent": intent,
            "customer_message": customer_msg,
            "conversation": conversation_dialogue,
            "turns": turns,
            "resolution": best_resolution,
            "metadata": {
                "brand": "SpotifyCares",
                "root_tweet_id": root_tid,
                "turn_count": len(turns),
                "has_resolution": bool(best_resolution),
                "has_troubleshooting": has_troubleshooting,
                "is_deflection": is_deflection_thread,
                "resolved_in_public": not is_deflection_thread,
                "created_at": thread_tweets[0]["created_at"],
            }
        }

        cases.append(case_obj)
        if has_troubleshooting and len(turns) >= 2:
            high_quality_cases.append(case_obj)

    console.print(f"Extracted [bold green]{len(cases):,}[/bold green] valid Spotify support cases.")
    console.print(f"High-quality troubleshooting cases: [bold cyan]{len(high_quality_cases):,}[/bold cyan]")

    # 5. Save output files
    all_cases_path = os.path.join(output_dir, "spotify_cases.jsonl")
    hq_cases_path = os.path.join(output_dir, "spotify_troubleshooting_cases.jsonl")

    console.print(f"Saving cases to [yellow]{all_cases_path}[/yellow]...")
    with open(all_cases_path, "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    console.print(f"Saving high-quality cases to [yellow]{hq_cases_path}[/yellow]...")
    with open(hq_cases_path, "w", encoding="utf-8") as f:
        for c in high_quality_cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # 6. Print Intent Distribution
    intent_counts = {}
    for c in cases:
        intent_counts[c["intent"]] = intent_counts.get(c["intent"], 0) + 1

    table = Table(title="SpotifyCares Extracted Cases - Intent Distribution", show_lines=True)
    table.add_column("Intent Category", style="bold cyan")
    table.add_column("Total Cases", justify="right", style="green")
    table.add_column("Percentage", justify="right", style="magenta")

    for intent, count in sorted(intent_counts.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(cases)) * 100 if cases else 0.0
        table.add_row(intent, f"{count:,}", f"{pct:.1f}%")

    console.print(table)
    console.print(f"[bold green]Dataset preparation completed in {time.time() - t_start:.2f}s[/bold green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract and structure SpotifyCares dialogue cases")
    parser.add_argument("--input", type=str, default="dataset/twcs.csv", help="Input CSV path")
    parser.add_argument("--output_dir", type=str, default="data/processed", help="Output directory")
    parser.add_argument("--min_turns", type=int, default=2, help="Minimum turns required")
    args = parser.parse_args()

    extract_spotify_cases(args.input, args.output_dir, args.min_turns)
