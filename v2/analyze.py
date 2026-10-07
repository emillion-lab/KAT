#!/usr/bin/env python3
"""KAT v2 — тест: светлина/висока облачност/условия за следи → ПТП.

Хипотези, записани ПРЕДИ да се види резултатът:
  H1 diffuse_frac   (дял разсеяна светлина) — повече разсейване → повече ранени
  H2 high_cc        (висока облачност)      — повече → повече ранени
  H3 contrail_hours (условия за трайни следи на 250 hPa) — повече → повече ранени
Основен изход: ранени за денонощие (национално). Вторичен: тежки ПТП.
Праг: p < 0.05/3 (Бонферони) И посока IRR > 1.
Плацебо: стойността на УТРЕШНИЯ ден. Ако „утре“ предсказва колкото „днес“,
връзката идва от времето/фронтовете, не от самия фактор.

Опровергаване: ако след контрол за дъжд, ниска облачност, температура,
налягане, ден от седмицата и празници IRR-ът не е > 1 със значимост —
хипотезата не е подкрепена от тези данни.
"""
import json, math, re, sys
import numpy as np, pandas as pd
import statsmodels.formula.api as smf

ACC, WX, OUT = "data/mvr_accidents.json", "v2/weather_daily.json", "v2"
HOLIDAYS = {"2026-09-06", "2026-09-22", "2026-05-24", "2026-05-01", "2026-05-06"}
XS = {"diffuse_frac": "H1 разсеяна светлина", "high_cc": "H2 висока облачност",
      "contrail_hours": "H3 условия за следи (250 hPa)"}
ALPHA = 0.05 / 3

ROAD = re.compile(r"катастроф|ПТП|пътнотранспорт|на пътя|по пътищата|пътни", re.I)
FIRE = re.compile(r"пожар", re.I)
REGIONAL = re.compile(r"\b[А-Я][а-я]+ско\b|област", re.U)
INJ = re.compile(r"(\d{1,3})(?:-?м[аи])?\s+(?:души\s+)?(?:са\s+)?(?:ранен|пострада)", re.I)


def clean(days):
    rows, flags = [], []
    for d in days:
        h, inj, ser = d.get("headline", ""), d.get("injured"), d.get("serious")
        reason = None
        if FIRE.search(h) and not ROAD.search(h):
            reason, inj, ser = "заглавие за пожари, не за ПТП", None, None
        else:
            m = INJ.search(h)
            if m and inj is not None and int(m.group(1)) != inj and int(m.group(1)) >= 8:
                flags.append((d["date"], f"ранени {inj} → {m.group(1)} (поправено по заглавието)"))
                inj = int(m.group(1))
            if inj is not None and inj < 8:
                reason, inj = f"ранени={d.get('injured')} — неправдоподобно за цялата страна", None
            if REGIONAL.search(h) and (d.get("ptp") or 0) < 10:
                reason = (reason + "; " if reason else "") + "областна справка, не национална"
                inj, ser = None, None
        if reason:
            flags.append((d["date"], reason))
        rows.append({"date": d["date"], "injured": inj, "serious": ser})
    return pd.DataFrame(rows), flags


def fit(df, y, x, extra=""):
    f = f"{y} ~ {x}{extra} + C(dow_g) + holiday + log_rain + low_cc_z + temp_c_z + dp24_z + trend"
    try:
        m = smf.negativebinomial(f, data=df).fit(disp=0, maxiter=200)
        kind = "NegBin"
    except Exception:
        m = smf.poisson(f, data=df).fit(disp=0, cov_type="HC1")
        kind = "Poisson-HC1"
    b, se, p = m.params[x], m.bse[x], m.pvalues[x]
    return {"model": kind, "n": int(m.nobs), "irr": round(math.exp(b), 3),
            "ci95": [round(math.exp(b - 1.96 * se), 3), round(math.exp(b + 1.96 * se), 3)],
            "p": round(float(p), 4), "mde_pct": round((math.exp(2.8 * se) - 1) * 100, 1)}


def main():
    acc = json.load(open(ACC, encoding="utf-8"))
    wx = pd.DataFrame(json.load(open(WX, encoding="utf-8"))["days"])
    a, flags = clean(acc["days"])
    df = wx.merge(a, on="date", how="left")
    df["d"] = pd.to_datetime(df["date"])
    df["dow_g"] = df["d"].dt.dayofweek.map(lambda w: "Fri-Sun" if w >= 4 else "Mon-Thu")
    df["holiday"] = df["date"].isin(HOLIDAYS).astype(int)
    df["log_rain"] = np.log1p(df["rain_mm"].fillna(0))
    df["trend"] = (df["d"] - df["d"].min()).dt.days / 30.0
    z = lambda s: (s - s.mean()) / s.std()
    for c in ["low_cc", "temp_c", "dp24"]:
        df[c + "_z"] = z(df[c]).fillna(0)
    res = {"n_days_weather": len(df), "flags": flags, "tests": {}}
    for x in XS:
        if df[x].isna().all():
            res["tests"][x] = {"skipped": "няма данни"}
            continue
        df[x + "_z"] = z(df[x])
        df[x + "_lead_z"] = df[x + "_z"].shift(-1)
        df[x + "_lag_z"] = df[x + "_z"].shift(1)
        t = {}
        for y in ["injured", "serious"]:
            sub = df.dropna(subset=[y, x + "_z", x + "_lead_z", x + "_lag_z"])
            if len(sub) < 25:
                t[y] = {"skipped": f"само {len(sub)} дни"}
                continue
            t[y] = {
                "same_day": fit(sub, y, x + "_z"),
                "prev_day": fit(sub, y, x + "_lag_z"),
                "placebo_next_day": fit(sub, y, x + "_lead_z"),
            }
        r = t.get("injured", {}).get("same_day")
        t["verdict"] = ("ПОДКРЕПЕНА" if r and r["irr"] > 1 and r["p"] < ALPHA else
                        "НЕ Е ПОДКРЕПЕНА" if r else "НЕДОСТАТЪЧНО ДАННИ")
        res["tests"][x] = t
    # описателно: терциали на H1
    if "diffuse_frac_z" in df:
        s = df.dropna(subset=["injured", "diffuse_frac"]).copy()
        s["tert"] = pd.qcut(s["diffuse_frac"], 3, labels=["ниско", "средно", "високо"])
        res["tertiles_diffuse"] = {k: {"days": int(len(g)), "injured_mean": round(g["injured"].mean(), 1),
                                       "rain_mm_mean": round(g["rain_mm"].mean(), 1)}
                                   for k, g in s.groupby("tert", observed=True)}
    df.drop(columns=["d"]).to_csv(f"{OUT}/days.csv", index=False)
    json.dump(res, open(f"{OUT}/results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(f"{OUT}/report.md", "w", encoding="utf-8").write(report(res, df))
    print(open(f"{OUT}/report.md", encoding="utf-8").read())


def fmt(r):
    if not r or "skipped" in r:
        return (r or {}).get("skipped", "—")
    return f"IRR {r['irr']} [{r['ci95'][0]}–{r['ci95'][1]}], p={r['p']}, n={r['n']}"


def report(res, df):
    L = ["# KAT v2 — светлина, висока облачност и условия за следи срещу ПТП", "",
         f"Дни с метео: {res['n_days_weather']}. Ранени (чисти): {int(df['injured'].notna().sum())}. "
         f"Тежки ПТП: {int(df['serious'].notna().sum())}.", "",
         "## ⚠ Проблемни дни (изключени или поправени)", ""]
    L += [f"- **{d}** — {why}" for d, why in res["flags"]] or ["- няма"]
    L += ["", "## Резултати (IRR на 1 стандартно отклонение; >1 = повече ранени)", "",
          f"Праг за значимост: p < {ALPHA:.4f} (Бонферони за 3 хипотези).", ""]
    for x, name in XS.items():
        t = res["tests"][x]
        L.append(f"### {name} — **{t.get('verdict', t.get('skipped'))}**")
        for y in ["injured", "serious"]:
            if y not in t:
                continue
            ty = t[y]
            lab = "ранени" if y == "injured" else "тежки ПТП"
            if "skipped" in ty:
                L.append(f"- {lab}: {ty['skipped']}")
                continue
            L += [f"- {lab}, същия ден: {fmt(ty['same_day'])} · откриваем ефект ≥ ±{ty['same_day']['mde_pct']}%",
                  f"- {lab}, предния ден: {fmt(ty['prev_day'])}",
                  f"- {lab}, плацебо (утрешния ден): {fmt(ty['placebo_next_day'])}"]
        L.append("")
    if "tertiles_diffuse" in res:
        L += ["## Разсеяна светлина по терциали (сурово, без контроли)", "",
              "| терциал | дни | ранени средно | дъжд мм средно |", "|---|---|---|---|"]
        L += [f"| {k} | {v['days']} | {v['injured_mean']} | {v['rain_mm_mean']} |"
              for k, v in res["tertiles_diffuse"].items()]
        L.append("")
    L += ["## Ограничения", "",
          "- ПТП са национални и дневни, парснати от новинарски заглавия; няма час и място на катастрофата.",
          "  Затова не може да се сравни ден/нощ — най-силният тест за „светлинна“ хипотеза.",
          "- ~3–4 месеца данни: тестът хваща само големи ефекти (виж „откриваем ефект“).",
          "- Висока облачност и следи вървят заедно с фронтове; плацебото (утрешния ден) показва дали",
          "  връзката е от фактора или от времето около него.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
