#!/usr/bin/env python3
"""
Roblox Game Revenue Estimator — Scraper
Fetches live player counts from the Roblox API and estimates USD revenue
for top Roblox games based on player share and Roblox's published ARPDAU.
"""

import argparse
import csv
import io
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ─── Constants ───────────────────────────────────────────────────────────────

# Revenue model based on Roblox's actual published developer payouts.
# Total developer payouts 2025: ~$1.5B/year (what ALL devs received combined)
# Roblox platform DAU: ~144M
# Dev revenue per DAU per day: $1.5B / 365 / 144M ≈ $0.0285
DEV_PAYOUT_ANNUAL = 1_500_000_000    # $1.5B total developer payouts (2025)
PLATFORM_DAU = 144_000_000           # 144M daily active users
DEV_REVENUE_PER_DAU = DEV_PAYOUT_ANNUAL / 365 / PLATFORM_DAU  # ~$0.0285

# Session rotation factor: concurrent × this ≈ DAU for the game.
# Players rotate in/out throughout the day; 12 is conservative.
SESSION_ROTATION_FACTOR = 12

# Monetization discount: top games monetize above average but not all
# players spend money. 0.7 = 70% of theoretical max.
MONETIZATION_FACTOR = 0.7

UNIVERSE_IDS = {
    # ── Top tier (100K+ typical) ──────────────────────────────────
    383310974:   "Adopt Me!",
    1686885941:  "Brookhaven RP",
    6035872082:  "Rivals",
    994732206:   "Blox Fruits",
    66654135:    "Murder Mystery 2",
    7709344486:  "Steal a Brainrot",

    # ── High tier (20K–100K typical) ──────────────────────────────
    3808081382:  "The Strongest Battlegrounds",
    601130232:   "Bee Swarm Simulator",
    3240075297:  "Berry Avenue RP",
    5203828273:  "Dress To Impress",
    372226183:   "Flee the Facility",
    5361032378:  "Sols RNG",
    5750914919:  "Fisch",
    1451439645:  "King Legacy",
    5578556129:  "Anime Vanguards",
    88070565:    "Welcome to Bloxburg",
    2619619496:  "BedWars",
    7436755782:  "Grow a Garden",
    3647333358:  "Evade",
    1202096104:  "Driving Empire",

    # ── Mid tier (5K–20K typical) ─────────────────────────────────
    210851291:   "Build A Boat For Treasure",
    4777817887:  "Blade Ball",
    2380077519:  "Slap Battles",
    321778215:   "Royale High",
    245662005:   "Jailbreak",
    1516533665:  "Piggy",
    2440500124:  "Doors",
    703124385:   "Tower of Hell",
    1720936166:  "All Star Tower Defense",
    65241:       "Natural Disaster Survival",
    371263894:   "Greenville",
    1359573625:  "Deepwoken",
    47545:       "Work at a Pizza Place",
    4730278139:  "Untitled Boxing Game",
    111958650:   "Arsenal",
    31970568:    "Theme Park Tycoon 2",
    3457700596:  "Fruit Battlegrounds",
    2788648141:  "Military Tycoon",
    4582358979:  "Arm Wrestle Simulator",

    # ── Lower tier (1K–5K typical) ────────────────────────────────
    4807308814:  "Break In 2",
    1511883870:  "Shindo Life",
    4778845442:  "Toilet Tower Defense",
    1008451066:  "Da Hood",
    2404080894:  "Funky Friday",
    1016936714:  "Your Bizarre Adventure",
    1659645941:  "Islands",
    1489026993:  "Survive the Killer",
    807930589:   "The Wild West",
    83858907:    "Speed Run 4",
    2316994223:  "Pet Simulator 99",
    4871329703:  "Type Soul",
    1434220026:  "My Restaurant",
    1087859240:  "Rogue Lineage",
    2934974644:  "Livetopia",
    3183403065:  "Anime Adventures",
    2177157737:  "Military Roleplay",
    140239261:   "MeepCity",
    892043755:   "Bubble Gum Simulator",
    81762198:    "Vehicle Simulator",
    210213771:   "Dragon Ball Z Final Stand",
}

API_GAMES = "https://games.roblox.com/v1/games"
API_VOTES = "https://games.roblox.com/v1/games/votes"

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CSV_PATH = os.path.join(DATA_DIR, "revenue_stats.csv")
JSON_PATH = os.path.join(DATA_DIR, "revenue_stats.json")

# ─── Helpers ─────────────────────────────────────────────────────────────────

def fmt_usd(value):
    """Format a number as USD with K/M/B suffix."""
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:,.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:,.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:,.1f}K"
    return f"${value:,.2f}"


def fetch_json(url, params=None):
    """GET a URL and return parsed JSON, or None on failure."""
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        print(f"  [!] API error: {exc}", file=sys.stderr)
        return None


def days_since(date_str):
    """Return the number of days between an ISO date string and now."""
    try:
        created = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - created
        return max(delta.days, 1)
    except (ValueError, TypeError):
        return 1

# ─── Core ────────────────────────────────────────────────────────────────────

def fetch_game_data():
    """Fetch game details and votes from the Roblox API (batched for large lists)."""
    all_ids = list(UNIVERSE_IDS.keys())
    batch_size = 50  # API limit per request
    all_games = []
    vote_map = {}

    for i in range(0, len(all_ids), batch_size):
        batch = all_ids[i:i + batch_size]
        ids_str = ",".join(str(uid) for uid in batch)

        print(f"[*] Fetching game details (batch {i // batch_size + 1})...")
        details = fetch_json(API_GAMES, params={"universeIds": ids_str})
        if details and "data" in details:
            all_games.extend(details["data"])

        print(f"[*] Fetching vote data (batch {i // batch_size + 1})...")
        votes = fetch_json(API_VOTES, params={"universeIds": ids_str})
        if votes and "data" in votes:
            for v in votes["data"]:
                vote_map[v["id"]] = {"up": v.get("upVotes", 0), "down": v.get("downVotes", 0)}

    if not all_games:
        print("[!] Failed to fetch any game details.", file=sys.stderr)
        return None

    # Filter out games that resolved to wrong universe (user places with 0 visits)
    valid_games = [g for g in all_games if g.get("visits", 0) > 1000]
    skipped = len(all_games) - len(valid_games)
    if skipped:
        print(f"[*] Filtered out {skipped} invalid/dead universe IDs.")

    return valid_games, vote_map


def calculate_revenue(games, vote_map):
    """Calculate estimated revenue for each game.

    Formula: game_daily_revenue = (concurrent × 12) × $0.0285 × 0.7
    - concurrent × 12 = estimated game DAU (session rotation)
    - $0.0285 = dev revenue per DAU per day (from $1.5B annual payouts / 144M DAU)
    - 0.7 = monetization discount factor
    """
    total_tracked = sum(g.get("playing", 0) for g in games)
    if total_tracked == 0:
        print("[!] Total player count is zero — cannot estimate revenue.", file=sys.stderr)
        return []

    now = datetime.now(timezone.utc)
    results = []

    for game in games:
        uid = game["id"]
        name = UNIVERSE_IDS.get(uid, game.get("name", "Unknown"))
        playing = game.get("playing", 0)
        visits = game.get("visits", 0)
        created = game.get("created", "")
        age_days = days_since(created)

        # Estimate game DAU from concurrent, then multiply by per-DAU revenue
        est_game_dau = playing * SESSION_ROTATION_FACTOR
        daily = est_game_dau * DEV_REVENUE_PER_DAU * MONETIZATION_FACTOR
        share = playing / total_tracked if total_tracked else 0

        votes = vote_map.get(uid, {"up": 0, "down": 0})
        total_votes = votes["up"] + votes["down"]
        like_pct = (votes["up"] / total_votes * 100) if total_votes else 0

        results.append({
            "universe_id": uid,
            "name": name,
            "playing": playing,
            "visits": visits,
            "created": created,
            "age_days": age_days,
            "player_share": round(share * 100, 2),
            "est_daily": round(daily, 2),
            "est_weekly": round(daily * 7, 2),
            "est_monthly": round(daily * 30, 2),
            "est_yearly": round(daily * 365, 2),
            "est_alltime": round(daily * age_days, 2),
            "upvotes": votes["up"],
            "downvotes": votes["down"],
            "like_pct": round(like_pct, 1),
            "timestamp": now.isoformat(),
        })

    results.sort(key=lambda r: r["est_daily"], reverse=True)
    return results


def save_csv(results):
    """Append results to CSV for historical tracking."""
    os.makedirs(DATA_DIR, exist_ok=True)
    file_exists = os.path.isfile(CSV_PATH)
    fieldnames = [
        "timestamp", "name", "universe_id", "playing", "visits",
        "player_share", "est_daily", "est_weekly", "est_monthly",
        "est_yearly", "est_alltime", "upvotes", "downvotes", "like_pct",
        "created", "age_days",
    ]
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for r in results:
            writer.writerow({k: r[k] for k in fieldnames})
    print(f"[+] CSV saved → {CSV_PATH}")


def save_json(results):
    """Export results as JSON for the web dashboard."""
    os.makedirs(DATA_DIR, exist_ok=True)
    total_tracked = sum(r["playing"] for r in results)
    payload = {
        "last_updated": results[0]["timestamp"] if results else datetime.now(timezone.utc).isoformat(),
        "dev_payout_annual": DEV_PAYOUT_ANNUAL,
        "platform_dau": PLATFORM_DAU,
        "dev_revenue_per_dau": round(DEV_REVENUE_PER_DAU, 4),
        "session_rotation_factor": SESSION_ROTATION_FACTOR,
        "monetization_factor": MONETIZATION_FACTOR,
        "total_tracked_players": total_tracked,
        "games": results,
    }
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"[+] JSON saved → {JSON_PATH}")


def print_table(results):
    """Print a formatted table to the terminal."""
    print()
    header = f"{'#':<3} {'Game':<28} {'Players':>10} {'Share':>7} {'Daily':>12} {'Weekly':>12} {'Monthly':>12} {'Yearly':>12} {'All-Time':>14}"
    print(header)
    print("─" * len(header))

    for i, r in enumerate(results, 1):
        print(
            f"{i:<3} {r['name']:<28} {r['playing']:>10,} {r['player_share']:>6.1f}% "
            f"{fmt_usd(r['est_daily']):>12} {fmt_usd(r['est_weekly']):>12} "
            f"{fmt_usd(r['est_monthly']):>12} {fmt_usd(r['est_yearly']):>12} "
            f"{fmt_usd(r['est_alltime']):>14}"
        )

    print("─" * len(header))
    total_daily = sum(r["est_daily"] for r in results)
    total_players = sum(r["playing"] for r in results)
    total_share = sum(r["player_share"] for r in results)
    print(f"    {'TOTAL':<28} {total_players:>10,} {total_share:>6.1f}% {fmt_usd(total_daily):>12}")
    print(f"\n[i] Dev payouts: {fmt_usd(DEV_PAYOUT_ANNUAL)}/yr | Platform DAU: {PLATFORM_DAU/1e6:.0f}M | Rev/DAU: ${DEV_REVENUE_PER_DAU:.4f}")
    print(f"[i] Session rotation: x{SESSION_ROTATION_FACTOR} | Monetization factor: {MONETIZATION_FACTOR}")
    print(f"[i] Last updated: {results[0]['timestamp'] if results else 'N/A'}\n")

# ─── Main ────────────────────────────────────────────────────────────────────

def run_once():
    """Single scrape + calculate + save cycle."""
    data = fetch_game_data()
    if data is None:
        return False

    games, vote_map = data
    results = calculate_revenue(games, vote_map)
    if not results:
        return False

    print_table(results)
    save_csv(results)
    save_json(results)
    return True


def main():
    parser = argparse.ArgumentParser(description="Roblox Game Revenue Estimator")
    parser.add_argument("--track", action="store_true", help="Run continuously every 30 minutes")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════╗")
    print("║   Roblox Game Revenue Estimator v1.0     ║")
    print("╚══════════════════════════════════════════╝")

    if args.track:
        print("[*] Tracking mode — refreshing every 30 minutes. Press Ctrl+C to stop.\n")
        while True:
            run_once()
            try:
                time.sleep(1800)  # 30 minutes
            except KeyboardInterrupt:
                print("\n[*] Stopped.")
                break
    else:
        run_once()


if __name__ == "__main__":
    main()
