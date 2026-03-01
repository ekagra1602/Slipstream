"""Deterministic demo graph seeding helpers for frontend visualization."""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from dombot.domain_utils import canonicalize_domain

DEFAULT_DOMAINS = [
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

EMBEDDING_DIMENSIONS = 1536

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


@dataclass
class DemoSeedSummary:
    inserted_nodes: int
    inserted_domains: int
    total_runs: int
    warnings: list[str]


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


def _deterministic_embedding(seed: int, dims: int = EMBEDDING_DIMENSIONS) -> list[float]:
    rand = random.Random(seed)
    values = [rand.uniform(-1.0, 1.0) for _ in range(dims)]
    magnitude = sum(v * v for v in values) ** 0.5
    if magnitude <= 1e-9:
        return [0.0] * dims
    return [round(v / magnitude, 6) for v in values]


def generate_demo_docs(
    *,
    domain_count: int = 10,
    tasks_per_domain: int = 100,
    include_history: bool = True,
) -> tuple[list[dict], DemoSeedSummary]:
    random.seed(42)
    warnings: list[str] = []

    if domain_count < 1:
        raise ValueError("domain_count must be >= 1")
    if tasks_per_domain < 1:
        raise ValueError("tasks_per_domain must be >= 1")

    if domain_count > len(DEFAULT_DOMAINS):
        warnings.append(
            f"Requested {domain_count} domains, but only {len(DEFAULT_DOMAINS)} defaults exist; clamped."
        )
        domain_count = len(DEFAULT_DOMAINS)

    domains = [canonicalize_domain(d) or d for d in DEFAULT_DOMAINS[:domain_count]]

    now = datetime.now(timezone.utc)
    base_time = now - timedelta(days=45)

    cluster_embeddings: dict[int, list[float]] = {}
    for cluster_idx in range(tasks_per_domain):
        cluster_embeddings[cluster_idx] = _deterministic_embedding(cluster_idx + 1000)

    docs: list[dict] = []
    domain_counts: dict[str, int] = defaultdict(int)
    total_runs = 0

    doc_idx = 0
    for domain_idx, domain in enumerate(domains):
        for cluster_idx in range(tasks_per_domain):
            task_name = _build_task_name(domain, cluster_idx, domain_idx)
            shared_steps = [
                ("click", f"route_hub_{cluster_idx:03d}", None),
                ("type", f"route_probe_{cluster_idx:03d}", f"lane_{domain_idx}"),
            ]
            target_a, target_b = _domain_targets(domain, cluster_idx)
            domain_steps = [
                ("click", f"{target_a}_{cluster_idx:03d}", None),
                ("click", f"{target_b}_{cluster_idx:03d}", None),
            ]
            steps = shared_steps + domain_steps + [("scroll", "page_content", None)]

            run_count = random.choice(RUN_COUNTS)
            total_runs += run_count
            success_count = int(run_count * random.uniform(0.68, 0.98))

            step_counts: dict[str, dict] = {}
            step_traces: list[dict] = []
            optimal_actions: list[str] = []

            for step_idx, (action, target, value) in enumerate(steps):
                sig = _build_step_sig(action, target, value)
                attempts = max(1, int(run_count * random.uniform(0.58, 0.96)))

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
                step_traces.append(
                    {
                        "action_signature": sig,
                        "attempt_count": attempts,
                        "success_rate": rate,
                    }
                )

                if rate >= 0.7:
                    optimal_actions.append(sig)

            success_rate = success_count / run_count if run_count else 0.0
            volume_factor = min(1.0, run_count / max(RUN_COUNTS))
            confidence = round(
                min(0.995, success_rate * 0.72 + volume_factor * 0.28),
                3,
            )

            created_at = base_time + timedelta(
                minutes=(doc_idx * 40) + random.randint(0, 20)
            )

            history: list[dict] = []
            if include_history:
                history_points = 6
                for h in range(history_points):
                    frac = (h + 1) / history_points
                    h_runs = max(1, int(run_count * frac))
                    h_conf = _clamp(
                        0.1 + (confidence * frac) + random.uniform(-0.03, 0.03),
                        0.05,
                        0.995,
                    )
                    history.append(
                        {
                            "timestamp": created_at + timedelta(hours=h * 14),
                            "confidence": round(h_conf, 3),
                            "run_count": h_runs,
                        }
                    )

            docs.append(
                {
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
                }
            )

            domain_counts[domain] += 1
            doc_idx += 1

    summary = DemoSeedSummary(
        inserted_nodes=len(docs),
        inserted_domains=len(domains),
        total_runs=total_runs,
        warnings=warnings,
    )
    return docs, summary
