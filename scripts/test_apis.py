#!/usr/bin/env python3
"""Test international road safety APIs and SAVE results to JSON"""
import urllib.request, urllib.parse, json, os
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json,*/*"}

sources = [
    ("worldbank",
     "https://api.worldbank.org/v2/country/BG/indicator/SH.STA.TRAF.P5?format=json&mrv=5"),
    ("who_gho",
     "https://ghoapi.azureedge.net/api/RS_198?" + urllib.parse.urlencode({"$filter": "SpatialDim eq 'BGR'", "$top": "5"})),
    ("eurostat_road",
     "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/tran_sf_roadus?format=JSON&geo=BG&sinceTimePeriod=2020"),
    ("eurostat_deaths",
     "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/tran_sf_roadse?format=JSON&geo=BG&sinceTimePeriod=2020"),
    ("oecd_irtad",
     "https://stats.oecd.org/SDMX-JSON/data/IRTAD_ACCIDENTS_CAUSES/BGR.../all?startTime=2020&format=json"),
]

results = {"tested_at": datetime.now(timezone.utc).isoformat(), "sources": {}}

for name, url in sources:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read().decode("utf-8", errors="ignore")
            try:
                parsed = json.loads(data)
                results["sources"][name] = {
                    "status": "ok",
                    "size": len(data),
                    "preview": str(parsed)[:500]
                }
                print(f"OK {name}: {len(data)} chars")
            except:
                results["sources"][name] = {"status": "ok_not_json", "size": len(data), "preview": data[:200]}
                print(f"OK {name} (not JSON): {len(data)} chars")
    except Exception as e:
        results["sources"][name] = {"status": "fail", "error": str(e)}
        print(f"FAIL {name}: {e}")

os.makedirs("data", exist_ok=True)
with open("data/api_test_results.json", "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("Results saved to data/api_test_results.json")
