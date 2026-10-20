# YOW Flight Deals

A website that shows the best round-trip flight deals out of Ottawa (YOW), refreshed automatically every day.

## How it works

1. **`fetch_deals.py`** runs once a day. It asks the Travelpayouts / Aviasales flight data API for the cheapest round trips from YOW departing in the next 6 months (thousands of fares).
2. For every destination it keeps the cheapest fare and compares it with the **usual price** for that destination (the median of the prices it has tracked over the last 120 days). Anything **20% or more below usual** is flagged as a deal.
3. It writes `data/deals.json` (what the website shows) and `data/history.json` (the price history that makes the deal detection smarter every day).
4. **`index.html`** is the website. It reads `data/deals.json` and lets visitors filter by region, month, price, nonstop and "deals only".
5. **GitHub Actions** (`.github/workflows/daily-deals.yml`) runs the script every morning at 6 AM Ottawa time for free, saves the new data, and **GitHub Pages** hosts the site for free.

Until the first real run, `data/deals.json` contains sample data and the site shows a "sample data" banner.

## Setup (about 15 minutes, all free)

### 1. Get a flight data token
1. Sign up at <https://www.travelpayouts.com>.
2. Join the **Aviasales** program in the dashboard.
3. Copy your **API token** (Profile → API token). Your **marker** (partner ID) is optional; add it if you want to earn commission on bookings made through the "See flight" links.

### 2. Put the project on GitHub
1. Create a new repository at <https://github.com/new> (public, so Pages and Actions are free).
2. Upload all the files in this folder, keeping the folders (`.github/workflows/`, `data/`).

### 3. Add your token as a secret
Repository → **Settings → Secrets and variables → Actions → New repository secret**
- Name `TRAVELPAYOUTS_TOKEN`, value: your token
- (optional) Name `TRAVELPAYOUTS_MARKER`, value: your marker

### 4. Turn on the website
Repository → **Settings → Pages** → Source: **Deploy from a branch** → Branch: `main`, folder `/ (root)` → Save.
Your site will be at `https://<your-username>.github.io/<repo-name>/`.

### 5. Run it the first time
Repository → **Actions → Daily flight deals → Run workflow**. After a minute or two, refresh your site — the sample banner disappears and real fares show up. From then on it runs every day by itself.

## Settings you can change

In `fetch_deals.py` (or as environment variables in the workflow):

| Setting | Default | What it does |
|---|---|---|
| `ORIGIN` | `YOW` | Departure airport |
| `CURRENCY` | `cad` | Price currency |
| `MONTHS_AHEAD` | `6` | How far ahead to search |
| `MIN_NIGHTS` / `MAX_NIGHTS` | `2` / `21` | Trip lengths to consider |
| `DEAL_THRESHOLD` | `0.20` | How far below usual counts as a deal |

To change the time it runs, edit the `cron` line in the workflow (times are UTC).

## Good to know
- Prices come from real searches other travellers made in the last ~48 hours, so they're very close to live prices but can change before you book. The "See flight" button opens a live search on Aviasales with those dates.
- Deal detection gets better over time: for the first few days it compares each destination against its other dates; after 3+ days of history it uses the tracked usual price.
- GitHub pauses scheduled workflows in repos with no activity for 60 days. The daily data commits count as activity, but if it ever stops, just click **Run workflow** again.

## Run it on your own computer (optional)
Install Python 3, then:

```
set TRAVELPAYOUTS_TOKEN=your_token_here
python fetch_deals.py
python -m http.server 8000
```

and open <http://localhost:8000>.
