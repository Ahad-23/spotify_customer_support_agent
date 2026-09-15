"""
Unit tests for thread graph reconstruction and tree traversal logic.
"""

from typing import Dict, List


def reconstruct_thread_tree(
    root_tid: int,
    tweet_to_idx: Dict[int, int],
    parent_to_children: Dict[int, List[int]],
    authors: List[str],
    inbounds: List[bool],
    texts: List[str],
    created_ats: List[str],
) -> List[Dict]:
    """
    Reconstructs an ordered sequence of turns from a root tweet ID using BFS.
    """
    if root_tid not in tweet_to_idx or not inbounds[tweet_to_idx[root_tid]]:
        return []

    thread_tids = []
    queue = [root_tid]
    visited = set()

    while queue:
        tid = queue.pop(0)
        if tid in visited:
            continue
        visited.add(tid)
        thread_tids.append(tid)

        children = parent_to_children.get(tid, [])
        for child in sorted(children):
            if child not in visited:
                queue.append(child)

    turns = []
    for tid in thread_tids:
        if tid in tweet_to_idx:
            idx = tweet_to_idx[tid]
            is_agent = authors[idx] == "SpotifyCares"
            turns.append({
                "turn": len(turns) + 1,
                "speaker": "agent" if is_agent else "customer",
                "tweet_id": tid,
                "text": texts[idx],
                "created_at": created_ats[idx],
            })

    return turns


def test_reconstruct_linear_thread():
    # Linear dialogue: Customer (1) -> Agent (2) -> Customer (3) -> Agent (4)
    tweet_ids = [101, 102, 103, 104]
    authors = ["user1", "SpotifyCares", "user1", "SpotifyCares"]
    inbounds = [True, False, True, False]
    texts = [
        "Spotify won't play on my phone",
        "What device and OS are you using?",
        "iPhone 12 with iOS 16",
        "Try logging out, restarting phone, and logging back in.",
    ]
    created_ats = [
        "Wed Oct 11 10:00:00 2017",
        "Wed Oct 11 10:05:00 2017",
        "Wed Oct 11 10:10:00 2017",
        "Wed Oct 11 10:15:00 2017",
    ]
    parents = [None, 101, 102, 103]

    tweet_to_idx = {tid: i for i, tid in enumerate(tweet_ids)}
    parent_to_children = {101: [102], 102: [103], 103: [104]}

    turns = reconstruct_thread_tree(
        root_tid=101,
        tweet_to_idx=tweet_to_idx,
        parent_to_children=parent_to_children,
        authors=authors,
        inbounds=inbounds,
        texts=texts,
        created_ats=created_ats,
    )

    assert len(turns) == 4
    assert turns[0]["speaker"] == "customer"
    assert turns[0]["turn"] == 1
    assert turns[1]["speaker"] == "agent"
    assert turns[1]["turn"] == 2
    assert turns[2]["speaker"] == "customer"
    assert turns[3]["speaker"] == "agent"


def test_skip_non_inbound_root():
    # If the root is an outbound tweet by an agent, it shouldn't be treated as customer case root
    tweet_ids = [201, 202]
    authors = ["SpotifyCares", "user2"]
    inbounds = [False, True]
    texts = ["PSA: New update available", "Thanks!"]
    created_ats = ["Wed Oct 11 10:00:00 2017", "Wed Oct 11 10:05:00 2017"]

    tweet_to_idx = {tid: i for i, tid in enumerate(tweet_ids)}
    parent_to_children = {201: [202]}

    turns = reconstruct_thread_tree(
        root_tid=201,
        tweet_to_idx=tweet_to_idx,
        parent_to_children=parent_to_children,
        authors=authors,
        inbounds=inbounds,
        texts=texts,
        created_ats=created_ats,
    )

    assert turns == []


def test_cycle_prevention():
    # If graph has circular parent-child references, visited set prevents infinite loops
    tweet_ids = [301, 302]
    authors = ["user3", "SpotifyCares"]
    inbounds = [True, False]
    texts = ["Help me", "On it!"]
    created_ats = ["Wed Oct 11 10:00:00 2017", "Wed Oct 11 10:05:00 2017"]

    tweet_to_idx = {tid: i for i, tid in enumerate(tweet_ids)}
    # Circular reference
    parent_to_children = {301: [302], 302: [301]}

    turns = reconstruct_thread_tree(
        root_tid=301,
        tweet_to_idx=tweet_to_idx,
        parent_to_children=parent_to_children,
        authors=authors,
        inbounds=inbounds,
        texts=texts,
        created_ats=created_ats,
    )

    assert len(turns) == 2
    assert [t["tweet_id"] for t in turns] == [301, 302]
