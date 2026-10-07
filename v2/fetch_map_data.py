#!/usr/bin/env python3
"""KAT v2 карта — данни за наслагване: катастрофи (katastrofi.bg, източник МВР) + прах (sensor.community).

Учтиво: по една заявка на източник, кеш в репото, ясен User-Agent.
Употреба: python3 v2/fetch_map_data.py [START] [END]
"""
import json, sys, time, urllib.request, urllib.parse
from collections import Counter
from datetime import date, timedelta

UA = {"User-Agent": "Mozilla/5.0 (KAT research; github.com/emillion-lab/KAT)", "Accept": "application/json"}
SOFIA = (42.58, 42.80, 23.15, 23.52)  # lat_min, lat_max, lon_min, lon_max
OUT = "v2/map"


def get_json(url, timeout=120):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def in_sofia(lat, lon):
    return SOFIA[0] <= lat <= SOFIA[1] and SOFIA[2] <= lon <= SOFIA[3]


def accidents(start, end):
    q = urllib.parse.urlencode({"StartDate": f"{start}T00:00:00", "EndDate": f"{end}T23:59:59"})
    data = get_json(f"https://katastrofi.bg/api/ptp/accidents/filtered?{q}", timeout=180)
    recs = data.get("accidents", data) if isinstance(data, dict) else data
    if isinstance(data, dict):
        print("отговор, ключове:", list(data.keys())[:20])
    print(f"катастрофи общо: {len(recs)}")
    if recs:
        print("полета на запис:", list(recs[0].keys()))
        print("пример:", json.dumps(recs[0], ensure_ascii=False)[:600])
    keep = []
    for r in recs:
        try:
            lat, lon = float(r.get("latitude")), float(r.get("longitude"))
        except (TypeError, ValueError):
            continue
        if in_sofia(lat, lon):
            keep.append(r)
    dkey = next((k for k in (recs[0].keys() if recs else []) if "date" in k.lower()), None)
    if dkey and keep:
        ds = sorted(str(r.get(dkey))[:10] for r in keep if r.get(dkey))
        print(f"София: {len(keep)} | дати {ds[0]} … {ds[-1]} | поле за дата: {dkey}")
        print("по месеци:", sorted(Counter(d[:7] for d in ds).items())[-14:])
    else:
        print(f"София: {len(keep)} (без разпознато поле за дата)")
    return keep, dkey


def pm24():
    d = get_json("https://data.sensor.community/static/v2/data.24h.json", timeout=180)
    out = {}
    for x in d:
        try:
            lat, lon = float(x["location"]["latitude"]), float(x["location"]["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if not in_sofia(lat, lon) or x["location"].get("indoor") in (1, "1"):
            continue
        vals = {v["value_type"]: v["value"] for v in x["sensordatavalues"]}
        if "P2" not in vals:
            continue
        try:
            p2, p1 = float(vals["P2"]), float(vals.get("P1", "nan"))
        except ValueError:
            continue
        if not (0 <= p2 < 500):
            continue
        out[x["sensor"]["id"]] = {"id": x["sensor"]["id"], "lat": round(lat, 5), "lon": round(lon, 5),
                                  "pm25": round(p2, 1), "pm10": None if p1 != p1 else round(p1, 1),
                                  "type": x["sensor"]["sensor_type"]["name"]}
    print(f"PM сензори в София (24ч): {len(out)}")
    return list(out.values())


if __name__ == "__main__":
    end = sys.argv[2] if len(sys.argv) > 2 else (date.today() - timedelta(days=1)).isoformat()
    start = sys.argv[1] if len(sys.argv) > 1 else (date.today() - timedelta(days=365)).isoformat()
    import os
    os.makedirs(OUT, exist_ok=True)
    acc, dkey = accidents(start, end)
    json.dump({"source": "katastrofi.bg (данни МВР)", "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "start": start, "end": end, "date_field": dkey, "accidents": acc},
              open(f"{OUT}/accidents_sofia.json", "w", encoding="utf-8"), ensure_ascii=False)
    pm = pm24()
    snap = {"source": "sensor.community data.24h.json", "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sensors": pm}
    json.dump(snap, open(f"{OUT}/pm24_latest.json", "w", encoding="utf-8"), ensure_ascii=False)
