#!/usr/bin/env python3
"""Seed MongoDB with a balanced ~1,000-node graph for frontend demos."""
from __future__ import annotations

import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running from the frontend/ directory or project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.config import COLLECTION_TASK_NODES, DB_NAME, MONGODB_URI  # noqa: E402
from db.embeddings import embed_task  # noqa: E402
from pymongo import MongoClient  # noqa: E402

DOMAINS = [
    "walmart.com",
    "amazon.com",
    "google.com",
    "github.com",
    "youtube.com",
    "x.com",
    "linkedin.com",
    "target.com",
    "bestbuy.com",
    "ebay.com",
]

TASKS_PER_DOMAIN = 100
CLUSTER_COUNT = 100

RUN_COUNTS = [120, 180, 260, 340, 480, 650, 820, 1050, 1350, 1700, 2100, 2500]

INTENT_LABELS = [
    "discover products",
    "compare options",
    "complete checkout",
    "track progress",
    "resolve issue",
    "publish update",
    "validate content",
    "manage account",
    "review history",
    "optimize workflow",
    "find support",
    "configure settings",
    "organize workspace",
    "prepare report",
    "filter results",
    "capture insight",
    "coordinate schedule",
    "verify status",
    "finalize action",
    "monitor trend",
]

DOMAIN_ACTION_TARGETS = {
    "walmart.com": [
        "walmart_search_results",
        "walmart_product_grid",
        "walmart_cart_summary",
        "walmart_pickup_options",
        "walmart_delivery_panel",
        "walmart_order_lookup",
    ],
    "amazon.com": [
        "amazon_search_results",
        "amazon_product_grid",
        "amazon_cart_summary",
        "amazon_prime_banner",
        "amazon_order_lookup",
        "amazon_review_panel",
    ],
    "google.com": [
        "google_search_results",
        "google_news_tab",
        "google_maps_panel",
        "google_translate_panel",
        "google_calendar_modal",
        "google_account_menu",
    ],
    "github.com": [
        "github_repo_list",
        "github_pull_request_panel",
        "github_issue_form",
        "github_action_run_log",
        "github_settings_sidebar",
        "github_star_widget",
    ],
    "youtube.com": [
        "youtube_search_results",
        "youtube_channel_panel",
        "youtube_playlist_modal",
        "youtube_comment_thread",
        "youtube_library_sidebar",
        "youtube_upload_dialog",
    ],
    "x.com": [
        "x_home_timeline",
        "x_compose_modal",
        "x_trending_panel",
        "x_profile_header",
        "x_notifications_panel",
        "x_bookmarks_list",
    ],
    "linkedin.com": [
        "linkedin_feed_stream",
        "linkedin_jobs_panel",
        "linkedin_profile_editor",
        "linkedin_connection_modal",
        "linkedin_company_page",
        "linkedin_message_panel",
    ],
    "target.com": [
        "target_search_results",
        "target_product_grid",
        "target_circle_panel",
        "target_cart_summary",
        "target_store_lookup",
        "target_pickup_options",
    ],
    "bestbuy.com": [
        "bestbuy_search_results",
        "bestbuy_product_grid",
        "bestbuy_geeksquad_panel",
        "bestbuy_order_lookup",
        "bestbuy_cart_summary",
        "bestbuy_support_modal",
    ],
    "ebay.com": [
        "ebay_search_results",
        "ebay_listing_editor",
        "ebay_auction_panel",
        "ebay_bid_modal",
        "ebay_feedback_form",
        "ebay_order_lookup",
    ],
}


def _build_step_sig(action: str, target: str, value: str | None) -> str:
    if value:
        return f"{action}:{target}:{value}"
    return f"{action}:{target}"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _build_task_name(domain: str, cluster_idx: int, domain_idx: int) -> str:
    label = INTENT_LABELS[cluster_idx % len(INTENT_LABELS)]
    return f"{label} route {cluster_idx:03d} on {domain} (lane {domain_idx + 1})"


def _domain_targets(domain: str, cluster_idx: int) -> tuple[str, str]:
    targets = DOMAIN_ACTION_TARGETS[domain]
    first = targets[cluster_idx % len(targets)]
    second = targets[(cluster_idx * 7 + 3) % len(targets)]
    if second == first:
        second = targets[(cluster_idx + 1) % len(targets)]
    return first, second


def main() -> None:
    random.seed(42)

    client = MongoClient(MONGODB_URI)
    collection = client[DB_NAME][COLLECTION_TASK_NODES]

    # Full reset for deterministic demo topology.
    collection.delete_many({})
    print("Cleared existing task_nodes.\n")

    print(f"Embedding {CLUSTER_COUNT} cluster intent families...")
    cluster_embeddings: dict[int, list[float]] = {}
    for cluster_idx in range(CLUSTER_COUNT):
        label = INTENT_LABELS[cluster_idx % len(INTENT_LABELS)]
        embed_text = f"{label} multi-site agent workflow pattern {cluster_idx:03d}"
        cluster_embeddings[cluster_idx] = embed_task(embed_text)
    print("Done embedding.\n")

    now = datetime.now(timezone.utc)
    base_time = now - timedelta(days=45)

    docs = []
    domain_counts: dict[str, int] = defaultdict(int)

    total_expected = len(DOMAINS) * TASKS_PER_DOMAIN
    print(f"Generating {total_expected} task nodes...")

    doc_idx = 0
    for domain_idx, domain in enumerate(DOMAINS):
        for cluster_idx in range(TASKS_PER_DOMAIN):
            task_name = _build_task_name(domain, cluster_idx, domain_idx)

            # Two shared signatures per cluster ensure consistent cross-domain connectivity
            # without creating a near-complete graph.
            shared_steps = [
                ("click", f"route_hub_{cluster_idx:03d}", None),
                ("type", f"route_probe_{cluster_idx:03d}", f"lane_{domain_idx}"),
            ]

            target_a, target_b = _domain_targets(domain, cluster_idx)
            domain_steps = [
                ("click", f"{target_a}_{cluster_idx:03d}", None),
                ("click", f"{target_b}_{cluster_idx:03d}", None),
            ]

            trailing_steps = [("scroll", "page_content", None)]
            steps = shared_steps + domain_steps + trailing_steps

            run_count = random.choice(RUN_COUNTS)
            success_count = int(run_count * random.uniform(0.68, 0.98))

            step_counts = {}
            step_traces = []
            optimal_actions = []

            for step_idx, (action, target, value) in enumerate(steps):
                sig = _build_step_sig(action, target, value)
                attempts = max(1, int(run_count * random.uniform(0.58, 0.96)))

                # Keep the two cluster-shared signatures highly reliable so they survive
                # optimal-action filtering and produce stable cross-task links.
                if step_idx < 2:
                    success_rate = random.uniform(0.82, 0.99)
                else:
                    success_rate = random.uniform(0.65, 0.98)

                successes = max(1, int(attempts * success_rate))
                rate = round(successes / attempts, 3)

                step_counts[sig] = {
                    "attempts": attempts,
                    "successes": successes,
                    "signature": sig,
                }
                step_traces.append({
                    "action_signature": sig,
                    "attempt_count": attempts,
                    "success_rate": rate,
                })

                if rate >= 0.7:
                    optimal_actions.append(sig)

            success_rate = success_count / run_count if run_count else 0.0
            volume_factor = min(1.0, run_count / max(RUN_COUNTS))
            confidence = round(min(0.995, success_rate * 0.72 + volume_factor * 0.28), 3)

            created_at = base_time + timedelta(minutes=(doc_idx * 40) + random.randint(0, 20))

            history = []
            history_points = 6
            for h in range(history_points):
                frac = (h + 1) / history_points
                h_runs = max(1, int(run_count * frac))
                h_conf = _clamp(
                    0.1 + (confidence * frac) + random.uniform(-0.03, 0.03),
                    0.05,
                    0.995,
                )
                history.append({
                    "timestamp": created_at + timedelta(hours=h * 14),
                    "confidence": round(h_conf, 3),
                    "run_count": h_runs,
                })

            docs.append({
                "task": task_name,
                "domain": domain,
                "task_embedding": cluster_embeddings[cluster_idx],
                "run_count": run_count,
                "confidence": confidence,
                "optimal_actions": optimal_actions,
                "step_traces": step_traces,
                "_step_counts": step_counts,
                "_success_count": success_count,
                "created_at": created_at,
                "updated_at": now,
                "_history": history,
            })

            domain_counts[domain] += 1
            doc_idx += 1

    assert len(docs) == total_expected, f"Expected {total_expected} docs, got {len(docs)}"

    for domain in DOMAINS:
        count = domain_counts.get(domain, 0)
        assert count == TASKS_PER_DOMAIN, f"Expected {TASKS_PER_DOMAIN} tasks for {domain}, got {count}"

    collection.insert_many(docs)

    print("\nDomain distribution:")
    for domain in DOMAINS:
        print(f"  {domain}: {domain_counts[domain]} tasks")

    print(f"\nSeeded {len(docs)} task nodes across {len(DOMAINS)} canonical domains.")


if __name__ == "__main__":
    main()
