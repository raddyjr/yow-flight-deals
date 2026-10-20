"""
YOW Flight Deals - daily fetcher.

Pulls the cheapest round-trip fares out of Ottawa (YOW) for the next several
months from the Travelpayouts / Aviasales Data API, compares each destination's
price against its own price history, and writes data/deals.json for the website.

Run:  python fetch_deals.py
Needs the TRAVELPAYOUTS_TOKEN environment variable (free at travelpayouts.com).
Uses only the Python standard library.
"""

import json
import os
import statistics
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

ORIGIN = os.environ.get("ORIGIN", "YOW")
CURRENCY = os.environ.get("CURRENCY", "cad")
MONTHS_AHEAD = int(os.environ.get("MONTHS_AHEAD", "6"))
MIN_NIGHTS, MAX_NIGHTS = 2, 21          # ignore odd trip lengths
DEAL_THRESHOLD = 0.20                   # 20% under usual price = "deal"
HISTORY_DAYS = 120                      # how much price history to keep
MARKER = os.environ.get("TRAVELPAYOUTS_MARKER", "")  # optional affiliate id

API = "https://api.travelpayouts.com"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DEALS_FILE = os.path.join(DATA_DIR, "deals.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
PLACES_FILE = os.path.join(DATA_DIR, "places.json")

REGIONS = {
    "Canada": {"CA"},
    "USA": {"US"},
    "Mexico & Caribbean": {
        "MX", "CU", "DO", "JM", "BS", "BB", "AW", "CW", "TC", "KY", "LC", "AG",
        "PR", "VC", "GD", "TT", "SX", "MF", "BM", "VG", "VI", "KN", "DM", "GP", "MQ", "HT",
    },
    "Central & South America": {
        "CR", "PA", "BZ", "GT", "HN", "SV", "NI", "CO", "PE", "BR", "AR", "CL",
        "EC", "UY", "PY", "BO", "VE",
    },
    "Europe": {
        "GB", "IE", "FR", "DE", "IT", "ES", "PT", "NL", "BE", "CH", "AT", "GR",
        "IS", "DK", "NO", "SE", "FI", "PL", "CZ", "HU", "HR", "RO", "BG", "MT",
        "LU", "SK", "SI", "EE", "LV", "LT", "RS", "ME", "AL", "CY", "BA", "MK",
    },
    "Africa & Middle East": {
        "MA", "EG", "ZA", "KE", "TZ", "ET", "NG", "GH", "SN", "TN", "AE", "QA",
        "IL", "JO", "TR", "SA", "LB", "OM", "BH", "KW",
    },
    "Asia & Pacific": {
        "JP", "KR", "CN", "HK", "TW", "TH", "VN", "SG", "MY", "ID", "PH", "IN",
        "LK", "NP", "AU", "NZ", "FJ", "KH", "MV",
    },
}


def region_for(country):
    for name, codes in REGIONS.items():
        if country in codes:
            return name
    return "Other"


def get_json(url, params=None, token=None, retries=3):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    headers = {"Accept": "application/json", "User-Agent": "yow-flight-deals/1.0"}
    if token:
        headers["X-Access-Token"] = token
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # network blips, 429s, etc.
            if attempt == retries - 1:
                raise
            print(f"  retrying after error: {exc}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data, pretty=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2 if pretty else None,
                  separators=None if pretty else (",", ":"))


def load_places():
    """IATA code -> {city, country}. Cached; refreshed every 30 days."""
    cached = load_json(PLACES_FILE, {})
    if cached.get("codes") and time.time() - cached.get("fetched", 0) < 30 * 86400:
        return cached["codes"]

    print("Downloading city/airport names...")
    cities = get_json(f"{API}/data/en/cities.json")
    airports = get_json(f"{API}/data/en/airports.json")
    codes = {}
    city_by_code = {}
    for c in cities:
        name = c.get("name") or (c.get("name_translations") or {}).get("en") or c["code"]
        city_by_code[c["code"]] = name
        codes[c["code"]] = {"city": name, "country": c.get("country_code", "")}
    for a in airports:
        if a.get("code") and a["code"] not in codes:
            codes[a["code"]] = {
                "city": city_by_code.get(a.get("city_code"), a.get("name") or a["code"]),
                "country": a.get("country_code", ""),
            }
    save_json(PLACES_FILE, {"fetched": time.time(), "codes": codes})
    return codes


def months_to_search():
    today = date.today()
    y, m = today.year, today.month
    out = []
    for _ in range(MONTHS_AHEAD):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def fetch_fares(token):
    """All cheap round trips from ORIGIN, one call per departure month."""
    fares = []
    for month in months_to_search():
        for page in (1, 2):
            params = {
                "origin": ORIGIN,
                "departure_at": month,
                "one_way": "false",
                "unique": "false",
                "sorting": "price",
                "currency": CURRENCY,
                "limit": 1000,
                "page": page,
            }
            resp = get_json(f"{API}/aviasales/v3/prices_for_dates", params, token)
            batch = resp.get("data") or []
            print(f"  {month} page {page}: {len(batch)} fares")
            fares.extend(batch)
            if len(batch) < 1000:
                break
            time.sleep(1)
    return fares


def booking_link(fare):
    link = fare.get("link") or ""
    if not link:
        dep = fare.get("departure_at", "")[:10]
        ret = (fare.get("return_at") or "")[:10]
        dd = dep[8:10] + dep[5:7]
        rd = (ret[8:10] + ret[5:7]) if ret else ""
        link = f"/search/{ORIGIN}{dd}{fare['destination']}{rd}1"
    url = "https://www.aviasales.com" + link
    if MARKER:
        url += ("&" if "?" in url else "?") + f"marker={MARKER}"
    return url


def nights(fare):
    try:
        d = datetime.fromisoformat(fare["departure_at"][:10])
        r = datetime.fromisoformat(fare["return_at"][:10])
        return (r - d).days
    except (KeyError, TypeError, ValueError):
        return None


def build_deals(fares, places, history, today_str):
    # Keep sensible trips, then group by destination city.
    by_dest = {}
    for f in fares:
        n = nights(f)
        if n is None or not (MIN_NIGHTS <= n <= MAX_NIGHTS) or not f.get("price"):
            continue
        dest = f.get("destination")
        if not dest or dest == ORIGIN:
            continue
        f["_nights"] = n
        by_dest.setdefault(dest, []).append(f)

    deals = []
    for dest, options in by_dest.items():
        options.sort(key=lambda f: f["price"])
        best = options[0]
        price = best["price"]

        past = [p for d, p in history.get(dest, {}).items() if d != today_str]
        if len(past) >= 3:
            baseline, basis = statistics.median(past), "history"
        else:
            # Not enough history yet: compare against this destination's other dates today.
            baseline, basis = statistics.median(f["price"] for f in options), "today"
        savings = (baseline - price) / baseline if baseline else 0

        place = places.get(dest) or places.get(best.get("destination_airport", "")) or {}
        country = place.get("country", "")
        deals.append({
            "destination": dest,
            "airport": best.get("destination_airport", dest),
            "city": place.get("city", dest),
            "country": country,
            "region": region_for(country),
            "price": round(price),
            "currency": CURRENCY.upper(),
            "departure": best["departure_at"][:10],
            "return": best["return_at"][:10],
            "nights": best["_nights"],
            "airline": best.get("airline", ""),
            "stops": best.get("transfers", 0),
            "return_stops": best.get("return_transfers", 0),
            "duration_min": best.get("duration_to") or best.get("duration"),
            "link": booking_link(best),
            "usual_price": round(baseline),
            "baseline_basis": basis,
            "savings_pct": round(savings * 100),
            "is_deal": savings >= DEAL_THRESHOLD,
            "trend": [p for _, p in sorted(history.get(dest, {}).items())][-30:],
            "other_dates": [
                {"departure": o["departure_at"][:10], "return": o["return_at"][:10],
                 "price": round(o["price"]), "link": booking_link(o)}
                for o in options[1:4]
            ],
        })

    deals.sort(key=lambda d: (not d["is_deal"], -d["savings_pct"], d["price"]))
    return deals


def update_history(history, deals, today_str):
    for d in deals:
        history.setdefault(d["destination"], {})[today_str] = d["price"]
    cutoff = date.fromordinal(date.today().toordinal() - HISTORY_DAYS).isoformat()
    for dest in list(history):
        history[dest] = {k: v for k, v in history[dest].items() if k >= cutoff}
        if not history[dest]:
            del history[dest]
    return history


def main():
    token = os.environ.get("TRAVELPAYOUTS_TOKEN", "").strip()
    if not token:
        sys.exit("Set TRAVELPAYOUTS_TOKEN (free token from https://www.travelpayouts.com).")

    today_str = date.today().isoformat()
    places = load_places()
    print(f"Searching fares from {ORIGIN}...")
    fares = fetch_fares(token)
    if not fares:
        sys.exit("API returned no fares - keeping yesterday's data.")

    history = load_json(HISTORY_FILE, {})
    deals = build_deals(fares, places, history, today_str)
    history = update_history(history, deals, today_str)

    save_json(DEALS_FILE, {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "origin": ORIGIN,
        "currency": CURRENCY.upper(),
        "fares_scanned": len(fares),
        "deal_threshold_pct": round(DEAL_THRESHOLD * 100),
        "demo": False,
        "deals": deals,
    }, pretty=True)
    save_json(HISTORY_FILE, history)
    hot = sum(d["is_deal"] for d in deals)
    print(f"Done: {len(deals)} destinations, {hot} deals, {len(fares)} fares scanned.")


if __name__ == "__main__":
    main()
