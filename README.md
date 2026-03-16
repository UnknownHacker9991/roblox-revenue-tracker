# Roblox Game Revenue Estimator

Estimates USD revenue for top Roblox games using live player data and Roblox's published ARPDAU — Python scraper + web dashboard.

> Run the scraper and open `index.html` to see the dashboard.

## How It Works

The estimator uses a **player-share model** to approximate how much each game earns:

```
Game Daily Revenue = (concurrent_players × 12) × $0.0285 × 0.7
```

### How it breaks down

1. **Estimate game DAU** from concurrent: `concurrent × 12` (session rotation factor — players rotate in/out throughout the day)
2. **Multiply by revenue per DAU**: `$0.0285` (derived from $1.5B annual developer payouts / 365 days / 144M platform DAU)
3. **Apply monetization discount**: `× 0.7` (not all players spend money; top games monetize above average but not perfectly)

### Constants

| Metric | Value | Source |
|--------|-------|--------|
| Total developer payouts (2025) | ~$1.5B/year | Roblox published data |
| Platform DAU | ~144M | Roblox Q4 2024 earnings |
| Dev revenue per DAU per day | ~$0.0285 | $1.5B / 365 / 144M |
| Session rotation factor | ×12 | Conservative estimate |
| Monetization discount | ×0.7 | Adjusts for non-paying users |

### Revenue Projections

- **Daily** = (concurrent × 12) × $0.0285 × 0.7
- **Weekly** = daily × 7
- **Monthly** = daily × 30
- **Yearly** = daily × 365
- **All-Time** = daily × days since game creation

Player counts are fetched live from the Roblox public API — no authentication required.

## Setup

### Requirements

- Python 3.8+
- `requests` library

### Install

```bash
git clone https://github.com/UnknownHacker9991/roblox-revenue-estimator.git
cd roblox-revenue-estimator
pip install requests
```

## Usage

### Single Run

```bash
python scraper.py
```

Fetches current player counts, estimates revenue, prints a table, and saves data to `data/`.

### Tracking Mode (every 30 min)

```bash
python scraper.py --track
```

Runs continuously, appending to `data/revenue_stats.csv` every 30 minutes. Press `Ctrl+C` to stop.

### Web Dashboard

1. Run the scraper at least once to generate `data/revenue_stats.json`
2. Open `index.html` in your browser (or serve via a local HTTP server)

```bash
# Option: serve with Python's built-in server
python -m http.server 8000
# Then open http://localhost:8000
```

The dashboard features:
- Live revenue table with sortable columns
- Bar chart comparing daily revenue across games
- Dark cyberpunk theme
- Responsive mobile layout

## Tracked Games (58 games)

Adopt Me!, Brookhaven RP, Rivals, Blox Fruits, Murder Mystery 2, Steal a Brainrot, The Strongest Battlegrounds, Bee Swarm Simulator, Dress To Impress, Berry Avenue RP, Flee the Facility, Sols RNG, Fisch, King Legacy, Anime Vanguards, Welcome to Bloxburg, BedWars, Grow a Garden, Evade, Driving Empire, Build A Boat For Treasure, Blade Ball, Slap Battles, Royale High, Jailbreak, Piggy, Doors, Tower of Hell, All Star Tower Defense, Natural Disaster Survival, Untitled Boxing Game, Deepwoken, Greenville, Work at a Pizza Place, Fruit Battlegrounds, Military Tycoon, Arsenal, Theme Park Tycoon 2, Toilet Tower Defense, Break In 2, Shindo Life, Arm Wrestle Simulator, Da Hood, Funky Friday, Your Bizarre Adventure, Islands, Survive the Killer, The Wild West, Speed Run 4, Type Soul, Pet Simulator 99, Rogue Lineage, My Restaurant, Livetopia, Anime Adventures, MeepCity, Military Roleplay, Dragon Ball Z Final Stand, Bubble Gum Simulator, Vehicle Simulator

## Output Files

- `data/revenue_stats.csv` — Historical data (appended each run)
- `data/revenue_stats.json` — Latest snapshot (used by the dashboard)

## Disclaimer

**These are estimates only.** Revenue figures are calculated from public player count data and Roblox's published revenue splits. Actual game earnings depend on many factors not captured here, including in-game purchases, game passes, engagement duration, and Roblox's internal revenue allocation algorithms. Use these numbers for educational and entertainment purposes only.

## Built With

- **Python** — Scraper and data processing
- **Requests** — HTTP client for the Roblox API
- **HTML/CSS/JS** — Single-file web dashboard
- **Roblox Games API** — Public endpoints for player counts and game metadata

## License

MIT License — see [LICENSE](LICENSE) for details.
