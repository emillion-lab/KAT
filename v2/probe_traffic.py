#!/usr/bin/env python3
"""Диагностика на източници за трафик и застрахователни щети. Само чете и отпечатва."""
import io, json, urllib.request, urllib.parse, zipfile, re

UA = {"User-Agent": "Mozilla/5.0 (KAT research; github.com/emillion-lab/KAT)"}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.headers.get("content-type", ""), r.read()


def show(name, url, n=700):
    try:
        st, ct, b = get(url)
        print(f"\n### {name}\n{st} {ct} {len(b)}B {url}\n{b[:n].decode('utf-8', 'replace')}")
        return b
    except Exception as e:
        print(f"\n### {name}\nERR {url} {e}")


# 1. TomTom Traffic Index — вътрешни ендпойнти на сайта
for path in ["dailyStats/BGR_sofia", "liveHourly/BGR_sofia", "dailyStats/BGR_Sofia", "liveHourly/BGR_Sofia"]:
    show(f"TomTom {path}", f"https://api.midway.tomtom.com/ranking/{path}", 900)

# 2. katastrofi.bg — колко назад стигат данните (по година, само брой)
print("\n### katastrofi.bg по години (цялата страна / София)")
for y in range(2015, 2027):
    q = urllib.parse.urlencode({"StartDate": f"{y}-01-01T00:00:00", "EndDate": f"{y}-12-31T23:59:59"})
    try:
        _, _, b = get(f"https://katastrofi.bg/api/ptp/accidents/filtered?{q}", timeout=240)
        d = json.loads(b)
        acc = d.get("accidents", [])
        sof = [a for a in acc if 42.58 <= (a.get("latitude") or 0) <= 42.80 and 23.15 <= (a.get("longitude") or 0) <= 23.52]
        inj = sum(1 for a in sof if (a.get("injuredCount") or 0) + (a.get("diedCount") or 0) > 0)
        print(f"{y}: total={d.get('totalCount')} returned={len(acc)} sofia={len(sof)} sofia_с_пострадали={inj}")
    except Exception as e:
        print(f"{y}: ERR {e}")

# 3. КФН — xlsx с претенции по ГО
b = show("КФН IBNR 2023", "https://www.fsc.bg/wp-content/uploads/2024/02/IBNR_31_12_2023.xlsx", 0)
if b:
    try:
        z = zipfile.ZipFile(io.BytesIO(b))
        print("листове:", [n for n in z.namelist() if n.startswith("xl/worksheets/")])
        ss = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        strs = re.findall(r"<t[^>]*>([^<]*)</t>", ss)
        print("низове (първите 120):", strs[:120])
    except Exception as e:
        print("xlsx ERR", e)
show("КФН листинг", "https://www.fsc.bg/?s=%D0%BF%D1%80%D0%B5%D0%B4%D1%8F%D0%B2%D0%B5%D0%BD%D0%B8+%D0%BF%D1%80%D0%B5%D1%82%D0%B5%D0%BD%D1%86%D0%B8%D0%B8", 300)

# 4. Apple Mobility (driving) — архив, 2020–2022
b = show("Apple mobility архив", "https://raw.githubusercontent.com/ActiveConclusion/COVID19_mobility/master/apple_reports/apple_mobility_report.csv", 300)
if b:
    lines = [l for l in b.decode("utf-8", "replace").splitlines() if "Sofia" in l or "Bulgaria" in l]
    print(f"редове за България/София: {len(lines)}")
    print("\n".join(lines[:5]))
