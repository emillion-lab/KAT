#!/usr/bin/env python3
"""KAT v2 — сурови данни за свързване: трафик ↔ катастрофи ↔ застрахователни щети.

Записва в v2/raw/:
  sofia_accidents_daily.csv  — дневно за София от katastrofi.bg (МВР), 2021→днес:
                               date, n, with_casualties, injured, died
  kfn_ibnr_<година>.xlsx     — КФН: брой/стойност на предявени и изплатени претенции по ГО
  apple_bg.csv               — Apple Mobility „driving“ за България (2020–2022, дневно)
"""
import csv, io, json, os, urllib.request, urllib.parse
from collections import defaultdict
from datetime import date

UA = {"User-Agent": "Mozilla/5.0 (KAT research; github.com/emillion-lab/KAT)"}
OUT = "v2/raw"
SOFIA = (42.58, 42.80, 23.15, 23.52)


def get(url, timeout=240):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def accidents():
    days = defaultdict(lambda: [0, 0, 0, 0])
    for y in range(2021, date.today().year + 1):
        q = urllib.parse.urlencode({"StartDate": f"{y}-01-01T00:00:00", "EndDate": f"{y}-12-31T23:59:59"})
        d = json.loads(get(f"https://katastrofi.bg/api/ptp/accidents/filtered?{q}"))
        n = 0
        for a in d.get("accidents", []):
            lat, lon = a.get("latitude") or 0, a.get("longitude") or 0
            if not (SOFIA[0] <= lat <= SOFIA[1] and SOFIA[2] <= lon <= SOFIA[3]):
                continue
            k = str(a.get("crashDate"))[:10]
            inj, died = int(a.get("injuredCount") or 0), int(a.get("diedCount") or 0)
            r = days[k]
            r[0] += 1; r[1] += 1 if inj + died else 0; r[2] += inj; r[3] += died
            n += 1
        print(f"катастрофи {y}: София {n}")
    with open(f"{OUT}/sofia_accidents_daily.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "n", "with_casualties", "injured", "died"])
        for k in sorted(days):
            w.writerow([k, *days[k]])


def kfn():
    for y in range(2018, date.today().year):
        ok = False
        for m in ["01", "02", "03", "04", "05"]:
            url = f"https://www.fsc.bg/wp-content/uploads/{y + 1}/{m}/IBNR_31_12_{y}.xlsx"
            try:
                b = get(url, 60)
                if b[:2] == b"PK":
                    open(f"{OUT}/kfn_ibnr_{y}.xlsx", "wb").write(b)
                    print(f"КФН {y}: {url} ({len(b)}B)")
                    ok = True
                    break
            except Exception:
                pass
        if not ok:
            print(f"КФН {y}: не е намерен по стандартния адрес")


def apple():
    b = get("https://raw.githubusercontent.com/ActiveConclusion/COVID19_mobility/master/apple_reports/apple_mobility_report.csv")
    rows = [l for l in b.decode("utf-8", "replace").splitlines() if l.startswith("Bulgaria,") or l.startswith("country,")]
    open(f"{OUT}/apple_bg.csv", "w").write("\n".join(rows) + "\n")
    subs = sorted({l.split(",")[2] for l in rows[1:]})
    print(f"Apple: {len(rows) - 1} реда, подрегиони: {subs[:10]}")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for fn in (kfn, apple, accidents):
        try:
            fn()
        except Exception as e:
            print(f"{fn.__name__}: ERR {e}")
