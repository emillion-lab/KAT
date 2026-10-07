#!/usr/bin/env python3
"""Дневен профил за София: въздух + време по часове, за сравнение на един ден със съседните.
Употреба: python3 v2/day_probe.py 2026-10-01 2026-10-08 > v2/probe.txt
"""
import json, sys, urllib.request, urllib.parse
from collections import defaultdict

LAT, LON = 42.70, 23.32
s, e = sys.argv[1], sys.argv[2]


def get(base, hourly):
    q = urllib.parse.urlencode({"latitude": LAT, "longitude": LON, "start_date": s, "end_date": e,
                                "hourly": hourly, "timezone": "Europe/Sofia"})
    with urllib.request.urlopen(f"{base}?{q}", timeout=60) as r:
        return json.load(r)["hourly"]


aq = get("https://air-quality-api.open-meteo.com/v1/air-quality",
         "pm2_5,pm10,nitrogen_dioxide,carbon_monoxide")
wx = get("https://api.open-meteo.com/v1/forecast",
         "temperature_2m,pressure_msl,wind_speed_10m,wind_gusts_10m,wind_direction_10m,"
         "relative_humidity_2m,cloud_cover_low,cloud_cover_high,precipitation")

days = defaultdict(lambda: defaultdict(list))
for src in (aq, wx):
    for i, t in enumerate(src["time"]):
        for k, v in src.items():
            if k != "time" and v[i] is not None:
                days[t[:10]][k].append(v[i])

print("ДЕН        PM2.5ср/макс  PM10ср  NO2ср  CO ср  T мин/макс  налягане  порив макс  вятър посока  RH%  ниска/висока обл  дъжд")
for d in sorted(days):
    x = days[d]
    avg = lambda k: sum(x[k]) / len(x[k]) if x[k] else float("nan")
    mx = lambda k: max(x[k]) if x[k] else float("nan")
    mn = lambda k: min(x[k]) if x[k] else float("nan")
    print(f"{d}  {avg('pm2_5'):5.1f}/{mx('pm2_5'):5.1f}  {avg('pm10'):6.1f}  {avg('nitrogen_dioxide'):5.1f}  "
          f"{avg('carbon_monoxide'):5.0f}  {mn('temperature_2m'):4.1f}/{mx('temperature_2m'):4.1f}  "
          f"{avg('pressure_msl'):7.1f}  {mx('wind_gusts_10m'):6.1f}  {avg('wind_direction_10m'):6.0f}°  "
          f"{avg('relative_humidity_2m'):4.0f}  {avg('cloud_cover_low'):4.0f}/{avg('cloud_cover_high'):4.0f}  "
          f"{sum(x['precipitation']):4.1f}")

print("\nЧАСОВЕ 2026-10-07 (PM2.5, NO2, порив, посока, T):")
for i, t in enumerate(aq["time"]):
    if t.startswith("2026-10-07"):
        j = wx["time"].index(t)
        print(f"{t[11:]}  PM2.5 {aq['pm2_5'][i]}  NO2 {aq['nitrogen_dioxide'][i]}  "
              f"порив {wx['wind_gusts_10m'][j]}  посока {wx['wind_direction_10m'][j]}°  T {wx['temperature_2m'][j]}")
