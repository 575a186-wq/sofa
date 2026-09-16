"""Deep-dive niche analysis: seller concentration + freshness of top-N Etsy listings.

Answers the manual-validation criteria 1/2/4 programmatically via Etsy API:
- how many distinct shops own the top-N results
- what share the single top shop holds (monopoly check)
- how fresh the top results are (living-demand check)
- median price / price range (POD margin check)

Usage:
    python src/analyze_niche.py "sound wave art personalized" [limit]
Writes a markdown card into output/niche_deep_dive.md and prints a summary.
"""

import argparse
import datetime as _dt
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from fetchers.etsy_client import EtsyClient

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "niche_deep_dive.md"

load_dotenv(ROOT / ".env")


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def analyze(phrase: str, limit: int, client: EtsyClient, cache: dict[int, str]) -> dict:
    rows = client.fetch_top(phrase, limit=limit)
    n = len(rows)
    if not n:
        return {"phrase": phrase, "n": 0}

    prices = [r["price"] for r in rows if r["price"] is not None]
    ages = [r["age_days"] for r in rows if r["age_days"] is not None]

    shop_ids = {r["shop_id"] for r in rows if r["shop_id"] is not None}
    missing = {sid for sid in shop_ids if sid not in cache}
    cache.update(client.shop_names(missing))

    shops: dict[str, int] = {}
    for r in rows:
        name = cache.get(r["shop_id"], "(unknown)")
        shops[name] = shops.get(name, 0) + 1

    ranked = sorted(shops.items(), key=lambda kv: kv[1], reverse=True)
    top_shop, top_count = ranked[0]
    shops_2plus = [name for name, c in ranked if c > 1]

    young_90 = sum(1 for a in ages if a is not None and a <= 90)

    return {
        "phrase": phrase,
        "n": n,
        "distinct_shops": len(shops),
        "top_shop": top_shop,
        "top_shop_count": top_count,
        "top_shop_share": round(100.0 * top_count / n, 1) if n else 0.0,
        "shops_2plus": shops_2plus,
        "median_price": _median(prices),
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "median_age_days": round(_median(ages), 1) if ages else None,
        "young_90_share": round(100.0 * young_90 / len(ages), 1) if ages else 0.0,
        "rows": rows,
        "shop_cache": cache,
    }


def render(results: dict, append: bool = False) -> str:
    mode = "a" if append else "w"
    with open(OUT, mode, encoding="utf-8") as f:
        if not append:
            f.write(f"# Niche Deep-Dive (Etsy top-N analysis)\n\n_Generated {_dt.datetime.now(_dt.timezone.utc):%Y-%m-%d %H:%M UTC}_\n\n")
        f.write(f"## {results['phrase']}\n\n")
        if not results["n"]:
            f.write("_No data (dry-run or empty result)._  \n\n")
            return ""
        f.write(
            f"- Listings sampled: **{results['n']}** · distinct shops: **{results['distinct_shops']}**\n"
            f"- Top shop: **{results['top_shop']}** — {results['top_shop_count']}/{results['n']} "
            f"({results['top_shop_share']}% of top results)\n"
            f"- Shops with 2+ listings in top: {', '.join(results['shops_2plus']) if results['shops_2plus'] else 'none'}\n"
            f"- Price: median **${results['median_price']}** "
            f"(range ${results['min_price']}–${results['max_price']})\n"
            f"- Freshness: median age **{results['median_age_days']} days**, "
            f"**{results['young_90_share']}%** listings younger than 90 days\n\n"
        )
        f.write("| # | Title (trunc) | Shop | $ | age days |\n|---|---|---|---|---|\n")
        cache = results.get("shop_cache", {})
        for i, r in enumerate(results["rows"][:12], 1):
            title = (r["title"] or "")[:45].replace("|", "/")
            shop = cache.get(r["shop_id"], "")[:22].replace("|", "/") if r["shop_id"] else ""
            price = f"{r['price']:.2f}" if r["price"] is not None else "—"
            age = f"{r['age_days']:.0f}" if r["age_days"] is not None else "—"
            f.write(f"| {i} | {title} | {shop} | {price} | {age} |\n")
        f.write("\n")
    return (
        f"  {results['phrase']}: {results['n']} sampled, {results['distinct_shops']} shops, "
        f"top-shop {results['top_shop_share']}% ({results['top_shop']}), "
        f"med ${results['median_price']}, {results['young_90_share']}% young<90d"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phrase", nargs="+", help="keyword phrase to analyze")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--primary-only", action="store_true", help="skip the additional-phrases sweep")
    args = parser.parse_args()
    phrase = " ".join(args.phrase)

    client = EtsyClient()
    if client.dry_run:
        print("No ETSY_API_KEY — dry-run, no real data.")
        sys.exit(1)

    cache: dict[int, str] = {}
    first = analyze(phrase, args.limit, client, cache)
    summary = render(first, append=False)
    print(summary)

    additional = [
        "cycle route print",
        "race course poster",
        "wedding song lyrics art",
        "voice wave print",
        "music waveform poster",
    ]
    if args.primary_only:
        additional = []
    for extra in additional:
        res = analyze(extra, args.limit, client, cache)
        print(render(res, append=True))


if __name__ == "__main__":
    main()