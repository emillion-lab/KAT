#!/usr/bin/env python3
"""Test international road safety APIs from GitHub Actions"""
import urllib.request, urllib.parse, json

HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}

sources = [
    ("World Bank BG traffic deaths",
     "https://api.worldbank.org/v2/country/BG/indicator/SH.STA.TRAF.P5?format=json&mrv=5"),
    ("WHO GHO road safety BG",
     "https://ghoapi.azureedge.net/api/RS_198?%24filter=SpatialDim%20eq%20%27BGR%27&%24top=5"),
    ("IRTAD OECD BG",
     "https://stats.oecd.org/SDMX-JSON/data/IRTAD_ACCIDENTS_CAUSES/BGR.../all?startTime=2020"),
    ("Eurostat road accidents",
     "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/tran_sf_roadus?format=JSON&geo=BG&time=2020,2021,2022,2023"),
    ("ETSC road deaths BG",
     "https://etsc.eu/wp-json/wp/v2/posts?search=Bulgaria&per_page=3"),
]

for name, url in sources:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read().decode('utf-8', errors='ignore')
            print(f"OK {name}: {len(data)} chars")
            print(f"   {data[:300]}")
    except Exception as e:
        print(f"FAIL {name}: {e}")

