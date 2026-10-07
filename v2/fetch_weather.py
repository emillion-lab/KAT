#!/usr/bin/env python3
"""KAT v2 — дневни метео/светлинни променливи за България.

Източник: Open-Meteo historical-forecast API (без ключ).
Шест града, усреднени — защото ПТП броят е национален.

Ключови променливи (дневно, светлата част 07:00–18:59 местно):
  high_cc        — средна висока облачност, % (цирус, вкл. от следи)
  diffuse_frac   — разсеяна / обща слънчева радиация (0–1): колко от
                   светлината идва разсеяна през облаци → мярка за
                   „пречупването“ от хипотезата
  contrail_hours — часове с условия за трайни следи на 250 hPa
                   (T ≤ −40 °C и влажност спрямо лед ≥ 100%)
Контроли: rain_mm, rain_hours, low_cc, temp_c, dp24 (промяна налягане 24ч)
"""
import json, math, sys, urllib.request, urllib.parse
from collections import defaultdict
from datetime import date, timedelta

CITIES = {
    "Sofia": (42.70, 23.32), "Plovdiv": (42.14, 24.75), "Varna": (43.21, 27.91),
    "Burgas": (42.50, 27.47), "Ruse": (43.85, 25.97), "StaraZagora": (42.43, 25.64),
}
HOURLY = ["temperature_2m", "precipitation", "cloud_cover_low", "cloud_cover_high",
          "shortwave_radiation", "diffuse_radiation", "pressure_msl",
          "temperature_250hPa", "relative_humidity_250hPa"]
DAY_H = range(7, 19)


def rh_ice(rh_w, t):
    ew = 6.112 * math.exp(17.62 * t / (243.12 + t))
    ei = 6.112 * math.exp(22.46 * t / (272.62 + t))
    return rh_w * ew / ei


def fetch(start, end):
    q = {
        "latitude": ",".join(str(v[0]) for v in CITIES.values()),
        "longitude": ",".join(str(v[1]) for v in CITIES.values()),
        "start_date": start, "end_date": end,
        "hourly": ",".join(HOURLY), "timezone": "Europe/Sofia",
    }
    url = "https://historical-forecast-api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.load(r)
    return data if isinstance(data, list) else [data]


def per_city_daily(h):
    days = defaultdict(lambda: defaultdict(list))
    for i, ts in enumerate(h["time"]):
        d, hr = ts[:10], int(ts[11:13])
        rec = days[d]
        g = lambda k: (h.get(k) or [None] * len(h["time"]))[i]
        rec["p"].append(g("pressure_msl"))
        rec["t"].append(g("temperature_2m"))
        pr = g("precipitation")
        rec["rain"].append(pr)
        if hr in DAY_H:
            rec["hcc"].append(g("cloud_cover_high"))
            rec["lcc"].append(g("cloud_cover_low"))
            rec["sw"].append(g("shortwave_radiation"))
            rec["df"].append(g("diffuse_radiation"))
            t250, rh250 = g("temperature_250hPa"), g("relative_humidity_250hPa")
            if t250 is not None and rh250 is not None:
                rec["con"].append(1 if (t250 <= -40 and rh_ice(rh250, t250) >= 100) else 0)
    out = {}
    mean = lambda xs: (sum(x for x in xs if x is not None) / max(1, sum(x is not None for x in xs))) if any(x is not None for x in xs) else None
    for d, r in days.items():
        sw = sum(x for x in r["sw"] if x is not None)
        df = sum(x for x in r["df"] if x is not None)
        rain = [x for x in r["rain"] if x is not None]
        out[d] = {
            "high_cc": mean(r["hcc"]), "low_cc": mean(r["lcc"]), "temp_c": mean(r["t"]),
            "p_mean": mean(r["p"]),
            "diffuse_frac": (df / sw) if sw > 0 else None,
            "contrail_hours": sum(r["con"]) if r["con"] else None,
            "rain_mm": sum(rain) if rain else None,
            "rain_hours": sum(1 for x in rain if x >= 0.2) if rain else None,
        }
    return out


def main(start, end):
    cities = fetch(start, end)
    per = [per_city_daily(c["hourly"]) for c in cities]
    dates = sorted(set().union(*[p.keys() for p in per]))
    rows, prev_p = [], None
    for d in dates:
        agg = {}
        for k in per[0][dates[0]].keys():
            vals = [p[d][k] for p in per if d in p and p[d][k] is not None]
            agg[k] = round(sum(vals) / len(vals), 4) if vals else None
        agg["dp24"] = round(agg["p_mean"] - prev_p, 2) if (agg["p_mean"] is not None and prev_p is not None) else None
        prev_p = agg["p_mean"]
        rows.append({"date": d, **agg})
    has_250 = any(r["contrail_hours"] is not None for r in rows)
    return {"source": "Open-Meteo historical-forecast API", "cities": list(CITIES),
            "daylight_hours": "07-18 Europe/Sofia", "has_250hPa": has_250, "days": rows}


if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else "2026-05-25"
    end = sys.argv[2] if len(sys.argv) > 2 else (date.today() - timedelta(days=1)).isoformat()
    out = sys.argv[3] if len(sys.argv) > 3 else "v2/weather_daily.json"
    res = main(start, end)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"weather: {len(res['days'])} дни, 250hPa={'да' if res['has_250hPa'] else 'НЕ'} → {out}")
