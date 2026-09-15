"""Niche research pipeline orchestrator."""

import argparse
import datetime as _dt
import logging
import os
import sys
from pathlib import Path

import yaml

from fetchers.etsy_client import EtsyClient, DEFAULT_MAX_LISTINGS
from fetchers.trends_client import get_trend_growth
from scoring.score_niches import opportunity_score, final_score

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "candidate_seeds.yaml"
OUTPUT_DIR = ROOT / "output"
LOGS_DIR = OUTPUT_DIR / "logs"


def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = LOGS_DIR / f"pipeline-{ts}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("pipeline")


def main() -> int:
    parser = argparse.ArgumentParser(description="Niche research pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run (ignore ETSY_API_KEY)")
    parser.add_argument("--max-listings", type=int, default=DEFAULT_MAX_LISTINGS,
                        help=f"Max listings to sample per niche (default {DEFAULT_MAX_LISTINGS})")
    args = parser.parse_args()

    log = setup_logging()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    seeds = config["niches"]
    weights = config.get("scoring", {})

    api_key = os.getenv("ETSY_API_KEY") or None
    dry_run = args.dry_run or api_key is None
    if dry_run:
        log.info("DRY-RUN mode (ETSY_API_KEY unset or --dry-run). Etsy data is synthetic.")
    else:
        log.info("LIVE mode: ETSY_API_KEY set.")

    etsy = EtsyClient(api_key=api_key, max_listings=args.max_listings)
    results: list[dict] = []

    for seed in seeds:
        log.info("Processing niche: %s (%s)", seed["id"], seed["name"])
        keywords = seed["keywords"]

        trend = get_trend_growth(" ".join(keywords), geo=seed.get("geo", "US"))
        if trend["error"]:
            log.warning("  trends unavailable: %s", trend["error"])

        etsy_stats = etsy.fetch(keywords)
        if dry_run:
            log.info("  etsy (dry-run) -> count=%s avg_price=%s avg_age=%s",
                     etsy_stats["total_count"], etsy_stats["avg_price"], etsy_stats["avg_age_days"])
        else:
            log.info("  etsy (live) -> count=%s avg_price=%s avg_age=%s",
                     etsy_stats["total_count"], etsy_stats["avg_price"], etsy_stats["avg_age_days"])

        opp = opportunity_score(
            trend_growth_pct=trend["trend_growth_pct"],
            social_growth_pct=None,
            etsy_listing_count=etsy_stats["total_count"],
            avg_age_days=etsy_stats["avg_age_days"],
            weights=weights,
        )
        final = final_score(opp, seed["automation_fit"])

        results.append({
            "id": seed["id"],
            "name": seed["name"],
            "art_type": seed["art_type"],
            "final_score": final,
            "opportunity_score": opp,
            "trend_growth_pct": trend["trend_growth_pct"],
            "trend_error": trend["error"],
            "etsy_listing_count": etsy_stats["total_count"],
            "avg_price": etsy_stats["avg_price"],
            "avg_age_days": etsy_stats["avg_age_days"],
        })

    results.sort(key=lambda r: r["final_score"], reverse=True)

    report_path = write_report(results, dry_run=dry_run)
    log.info("Wrote report to %s", report_path)
    return 0


def _short_error(error: str | None, limit: int = 100) -> str:
    """Truncate a multi-line error to a compact single-line hint (full text stays in logs)."""
    if not error:
        return ""
    first_line = error.splitlines()[0]
    return first_line[:limit] + ("..." if len(first_line) > limit else "")


def write_report(results: list[dict], dry_run: bool) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / "weekly_report.md"
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    mode = "dry-run" if dry_run else "live"
    failed_trends = [r for r in results if r["trend_error"]]

    lines = [
        f"# Niche Research Report — {now}",
        "",
        f"**Mode:** `{mode}`",
        f"**Niches evaluated:** {len(results)}",
        f"**Trends data:** {len(results) - len(failed_trends)}/{len(results)} succeeded"
        + (f" (unavailable: {', '.join(r['id'] for r in failed_trends)})" if failed_trends else ""),
        "",
        "## Top Candidates",
        "",
        "| # | Niche | Final | Opp. | Trend% | Etsy Listings | Avg Price | Avg Age Days | Type |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(results, 1):
        trend_str = f"{r['trend_growth_pct']:.1f}%" if r["trend_growth_pct"] is not None else "n/a"
        price_str = f"${r['avg_price']:.0f}" if r["avg_price"] else "n/a"
        age_str = f"{r['avg_age_days']:.0f}" if r["avg_age_days"] else "n/a"
        lines.append(
            f"| {i} | {r['name']} | {r['final_score']:.4f} | {r['opportunity_score']:.4f} "
            f"| {trend_str} | {r['etsy_listing_count']} | {price_str} | {age_str} | {r['art_type']} |"
        )

    lines += ["", "## Notes", ""]
    for r in results:
        trend_str = f"{r['trend_growth_pct']:.1f}%" if r["trend_growth_pct"] is not None else "n/a"
        note = f"**{r['name']}** — trend {trend_str}, {r['etsy_listing_count']} listings"
        if r["trend_error"]:
            note += f" (trend unavailable: {_short_error(r['trend_error'])})"
        lines.append(f"- {note}")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


if __name__ == "__main__":
    raise SystemExit(main())