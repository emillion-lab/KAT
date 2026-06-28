#!/usr/bin/env python3
"""
KAT Statistics Fetcher
Pulls official road safety data from World Bank, WHO and Eurostat
Updates data/historical.json with latest available figures
"""
import urllib.request, urllib.parse, json, os
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", errors="ignore"))

def fetch_worldbank():
    """Deaths per 100k population — Bulgaria"""
    url = "https://api.worldbank.org/v2/country/BG/indicator/SH.STA.TRAF.P5?format=json&mrv=10"
    try:
        data = fetch(url)
        records = data[1] if len(data) > 1 else []
        return {r["date"]: r["value"] for r in records if r.get("value") is not None}
    except Exception as e:
        print(f"WorldBank fail: {e}")
        return {}

def fetch_who():
    """WHO road safety mortality Bulgaria"""
    url = "https://ghoapi.azureedge.net/api/RS_198?" + urllib.parse.urlencode({
        "$filter": "SpatialDim eq 'BGR'", "$top": "10", "$orderby": "TimeDim desc"
    })
    try:
        data = fetch(url)
        records = data.get("value", [])
        return {str(r["TimeDim"]): r.get("NumericValue") for r in records if r.get("NumericValue")}
    except Exception as e:
        print(f"WHO fail: {e}")
        return {}

def fetch_eurostat():
    """Eurostat - persons killed in road accidents Bulgaria"""
    # Total killed (sex=T, age=TOTAL, victim=TOT_KIL)
    url = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
           "tran_sf_roadus?format=JSON&geo=BG&sinceTimePeriod=2015"
           "&unit=NR&victim=KIL&sex=T&age=TOTAL")
    try:
        data = fetch(url)
        times = data.get("dimension", {}).get("time", {}).get("category", {}).get("index", {})
        values = data.get("value", {})
        result = {}
        for year, idx in times.items():
            val = values.get(str(idx))
            if val is not None:
                result[year] = int(val)
        return result
    except Exception as e:
        print(f"Eurostat fail: {e}")
        return {}

def load_existing():
    path = "data/historical.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

def main():
    print(f"KAT Stats Fetcher — {datetime.now(timezone.utc).isoformat()}")

    existing = load_existing()

    print("Fetching World Bank...")
    wb = fetch_worldbank()
    print(f"  {len(wb)} records: {list(wb.items())[:3]}")

    print("Fetching WHO...")
    who = fetch_who()
    print(f"  {len(who)} records: {list(who.items())[:3]}")

    print("Fetching Eurostat...")
    estat = fetch_eurostat()
    print(f"  {len(estat)} records: {list(estat.items())[:3]}")

    # Merge into historical national data
    # Keep existing hand-curated data and augment with API data
    national = existing.get("national", [])
    national_by_year = {str(r["year"]): r for r in national}

    # Update dead count from Eurostat (most reliable for BG)
    for year, dead in estat.items():
        if year in national_by_year:
            national_by_year[year]["dead"] = dead
            national_by_year[year]["dead_source"] = "Eurostat"
        else:
            national_by_year[year] = {
                "year": int(year), "dead": dead,
                "dead_source": "Eurostat",
                "total": None, "injured": None, "serious": None
            }

    # Add World Bank rate
    for year, rate in wb.items():
        if year in national_by_year:
            national_by_year[year]["deaths_per_100k"] = rate
            national_by_year[year]["deaths_per_100k_source"] = "World Bank"

    national_updated = sorted(national_by_year.values(), key=lambda x: x["year"], reverse=True)

    # Compute last available year
    years_with_dead = [r for r in national_updated if r.get("dead")]
    last_year = years_with_dead[0]["year"] if years_with_dead else 2024
    last_dead = years_with_dead[0]["dead"] if years_with_dead else 571

    result = {
        **existing,
        "updated": datetime.now(timezone.utc).isoformat(),
        "last_complete_year": last_year,
        "api_sources": {
            "worldbank": {"records": len(wb), "latest": max(wb.keys()) if wb else None},
            "who": {"records": len(who), "latest": max(who.keys()) if who else None},
            "eurostat": {"records": len(estat), "latest": max(estat.keys()) if estat else None},
        },
        "national": national_updated,
        "sofia_daily_avg": existing.get("sofia_daily_avg", {
            "note": "Средно за денонощие в София-град",
            "light": 8.2, "serious": 0.9, "dead": 0.08, "injured": 9.1
        }),
        "risk_by_weekday": existing.get("risk_by_weekday", {}),
        "risk_by_month": existing.get("risk_by_month", {}),
    }

    os.makedirs("data", exist_ok=True)
    with open("data/historical.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nSaved! Last complete year: {last_year}, dead: {last_dead}")

if __name__ == "__main__":
    main()
