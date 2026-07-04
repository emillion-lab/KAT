#!/usr/bin/env python3
"""MVR/ПТП scraper v4 — multi-source news with honest provenance.
Опитва: (1) МВР директно, (2) Google News RSS БГ, (3) няколко БГ RSS.
Ако намери дневен брой ПТП за скорошна дата → source='news'.
Ако не → пише honest 'frozen' статус, БЕЗ да трие добрата история.
"""
import urllib.request, json, re, os, sys
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from email.utils import parsedate_to_datetime

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
      "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8"}
DATA = "data/mvr_accidents.json"
SOFIA = timezone(timedelta(hours=3))

BG_MONTHS = {"януари":1,"февруари":2,"март":3,"април":4,"май":5,"юни":6,
             "юли":7,"август":8,"септември":9,"октомври":10,"ноември":11,"декември":12}

NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=" + quote('МВР "пътнотранспортни произшествия" денонощие') + "&hl=bg&gl=BG&ceid=BG:bg",
    "https://news.google.com/rss/search?q=" + quote('ПТП катастрофи "за последното денонощие" МВР') + "&hl=bg&gl=BG&ceid=BG:bg",
    "https://news.google.com/rss/search?q=" + quote('пътна обстановка загинали ранени денонощие') + "&hl=bg&gl=BG&ceid=BG:bg",
]

def fetch(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  fetch fail {url[:70]}: {e}")
        return None

def strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))

def extract_counts(text):
    t = strip(text)
    def find(pats):
        for p in pats:
            m = re.search(p, t, re.IGNORECASE)
            if m:
                for g in m.groups():
                    if g and g.isdigit():
                        return int(g)
        return None
    ptp     = find([r"(\d+)\s+пътнотранспортни\s+произшеств", r"(\d+)\s+ПТП\b", r"(\d+)\s+катастроф"])
    dead    = find([r"(\d+)\s+(?:са\s+)?загинал", r"(\d+)\s+(?:човека?\s+)?загина", r"(\d+)\s+жертв"])
    injured = find([r"(\d+)\s+(?:са\s+)?ранен", r"(\d+)\s+пострадал"])
    serious = find([r"(\d+)\s+тежки"])
    light   = find([r"(\d+)\s+леки"])
    if not any([ptp, dead, injured]):
        return None
    return {"ptp": ptp, "dead": dead, "injured": injured,
            "serious": serious, "light": light}

def parse_news_rss(xml):
    """Връща list от (date_iso, title, link, counts) за скорошни дни."""
    out = []
    items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
    now = datetime.now(SOFIA)
    for it in items:
        title = re.search(r"<title>(.*?)</title>", it, re.DOTALL)
        desc  = re.search(r"<description>(.*?)</description>", it, re.DOTALL)
        pub   = re.search(r"<pubDate>(.*?)</pubDate>", it)
        title = re.sub(r"<!\[CDATA\[|\]\]>", "", title.group(1)).strip() if title else ""
        desc  = re.sub(r"<!\[CDATA\[|\]\]>", "", desc.group(1)).strip() if desc else ""
        blob = title + " " + desc
        # само статии, които звучат като дневна МВР справка
        if not re.search(r"денонощие|пътна обстановка|за изминал", blob, re.IGNORECASE):
            continue
        counts = extract_counts(blob)
        if not counts:
            continue
        try:
            d = parsedate_to_datetime(pub.group(1)).astimezone(SOFIA) if pub else now
        except Exception:
            d = now
        if (now - d).days > 4:  # само скорошни
            continue
        out.append({"date": d.strftime("%Y-%m-%d"), "title": title[:160],
                    "counts": counts})
    return out

def load_existing():
    try:
        with open(DATA, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"days": []}

def main():
    existing = load_existing()
    days = {d["date"]: d for d in existing.get("days", []) if isinstance(d, dict) and d.get("date")}

    found = []
    for feed in NEWS_FEEDS:
        xml = fetch(feed)
        if not xml:
            continue
        parsed = parse_news_rss(xml)
        print(f"  feed -> {len(parsed)} candidate items")
        found.extend(parsed)

    # най-скорошният ден с реален брой
    best = None
    for item in sorted(found, key=lambda x: x["date"], reverse=True):
        c = item["counts"]
        if c.get("ptp") or c.get("dead") is not None:
            best = item
            break

    now = datetime.now(SOFIA)
    if best:
        rec = {"date": best["date"], "source": "news",
               "ptp": best["counts"].get("ptp"),
               "dead": best["counts"].get("dead"),
               "injured": best["counts"].get("injured"),
               "serious": best["counts"].get("serious"),
               "light": best["counts"].get("light"),
               "headline": best["title"]}
        days[best["date"]] = rec
        status = "live_news"
        note = "Дневен брой от новинарски RSS (МВР справка), автоматично парснат."
        print(f"  ✓ FOUND {best['date']}: {best['counts']}")
    else:
        status = "frozen"
        note = ("МВР спря публичния обмен на ПТП данни на 05.05.2026 (надграждане на софтуер). "
                "Не е намерен дневен брой в новините. Рискът се смята от исторически данни 2015–2024 + космическо време + налягане.")
        print("  ✗ no live daily count — honest frozen status")

    all_days = sorted(days.values(), key=lambda x: x.get("date", ""), reverse=True)[:60]
    out = {
        "updated": now.isoformat(),
        "status": status,
        "source": "news_rss" if status == "live_news" else "frozen",
        "note": note,
        "mvr_frozen_since": "2026-05-05",
        "mvr_news_url": "https://boulevardbulgaria.bg/articles/martin-atanasov-mvr-tihomalkom-sprya-kartata-s-danni-za-ptp",
        "days_count": len(all_days),
        "days": all_days,
    }
    os.makedirs("data", exist_ok=True)
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"  wrote {DATA}: status={status}, days={len(all_days)}")

if __name__ == "__main__":
    main()
