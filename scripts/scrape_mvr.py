#!/usr/bin/env python3
"""MVR Scraper v3 — MVR direct + Bulgarian news RSS fallback"""
import urllib.request, json, re, os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
    "Referer": "https://www.mvr.bg/",
}

BG_MONTHS = {"януари":1,"февруари":2,"март":3,"април":4,"май":5,"юни":6,
              "юли":7,"август":8,"септември":9,"октомври":10,"ноември":11,"декември":12}

RSS_SOURCES = [
    "https://bntnews.bg/rss.php",
    "https://btvnovinite.bg/rss.xml",
    "https://nova.bg/rss",
    "https://www.dir.bg/rss/news.xml",
    "https://news.google.com/rss/search?q="+quote("МВР пътна обстановка катастрофи")+"&hl=bg&gl=BG&ceid=BG:bg",
]

def fetch(url, hdrs=None):
    req = urllib.request.Request(url, headers=hdrs or HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  fetch {url[:60]}: {e}")
        return None

def parse_date_bg(text):
    m = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", text.lower())
    if not m: return None
    mo = BG_MONTHS.get(m.group(2))
    if not mo: return None
    return f"{m.group(3)}-{mo:02d}-{int(m.group(1)):02d}"

def parse_accidents(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    def find(pats):
        for p in pats:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                for g in m.groups():
                    if g and g.isdigit(): return int(g)
        return None
    light   = find([r"(\d+)\s+леки\s+(?:пътно)?транспортни", r"(\d+)\s+леки\s+ПТП"])
    serious = find([r"(\d+)\s+тежки\s+(?:пътно)?транспортни", r"(\d+)\s+тежки\s+ПТП"])
    dead    = find([r"(\d+)\s+(?:са\s+)?загинали", r"(\d+)\s+(?:човека?\s+)?загина"])
    injured = find([r"(\d+)\s+(?:са\s+)?ранени", r"(\d+)\s+пострадали"])
    return {"light":light,"serious":serious,"dead":dead,"injured":injured,
            "total": light+serious if light and serious else light}

def try_mvr_direct():
    """Try MVR website directly"""
    urls = [
        "https://www.mvr.bg/press/%D0%B0%D0%BA%D1%82%D1%83%D0%B0%D0%BB%D0%BD%D0%B0-%D0%B8%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%86%D0%B8%D1%8F/%D0%B0%D0%BA%D1%82%D1%83%D0%B0%D0%BB%D0%BD%D0%B0-%D0%B8%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%86%D0%B8%D1%8F/%D0%BF%D1%8A%D1%82%D0%BD%D0%B0-%D0%BE%D0%B1%D1%81%D1%82%D0%B0%D0%BD%D0%BE%D0%B2%D0%BA%D0%B0",
        "https://www.mvr.bg/press",
    ]
    for url in urls:
        html = fetch(url)
        if html and "пътн" in html.lower():
            print(f"  MVR direct OK: {len(html)} chars")
            return html
    return None

def try_rss_sources(existing_dates):
    """Parse Bulgarian news RSS for accident reports"""
    days = []
    for rss_url in RSS_SOURCES:
        html = fetch(rss_url, {"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml,*/*"})
        if not html:
            continue
        print(f"  RSS OK: {rss_url[:50]}")
        items = re.findall(r"<item>(.*?)</item>", html, re.DOTALL)
        for item in items:
            # Check if accident-related
            kws = ["катастроф","пътен инцидент","пострадал","произшествие","загинал","ранени","ПТП"]
            if not any(k.lower() in item.lower() for k in kws):
                continue
            # Get title and link
            title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item, re.DOTALL)
            link_m  = re.search(r"<link>([^<]+)</link>", item)
            date_m  = re.search(r"<pubDate>(.*?)</pubDate>", item)
            if not title_m or not link_m:
                continue
            title = title_m.group(1).strip()
            link  = link_m.group(1).strip()
            # Parse date
            date_str = None
            if date_m:
                # RSS date format: Mon, 28 Jun 2026 10:00:00 +0000
                try:
                    from email.utils import parsedate
                    pd = parsedate(date_m.group(1))
                    if pd: date_str = f"{pd[0]:04d}-{pd[1]:02d}-{pd[2]:02d}"
                except: pass
            if not date_str:
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if date_str in existing_dates:
                continue
            # Fetch full article for numbers
            article = fetch(link)
            acc = parse_accidents(article or item)
            if acc.get("dead") is not None or acc.get("light") is not None:
                days.append({"date":date_str,"url":link,"title":title,
                    "source":"news_rss","scraped_at":datetime.now(timezone.utc).isoformat(),**acc})
                existing_dates.add(date_str)
                print(f"  Found: {date_str} — {title[:60]}")
    return days

def load_existing():
    path = "data/mvr_accidents.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"updated": None, "days": []}

def save(data):
    os.makedirs("data", exist_ok=True)
    with open("data/mvr_accidents.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(data['days'])} days")

def main():
    print(f"MVR Scraper v3 — {datetime.now(timezone.utc).isoformat()}")
    existing = load_existing()
    existing_dates = {d["date"] for d in existing.get("days", [])}
    new_days = []

    # 1. Try MVR direct
    print("\n1. Trying MVR direct...")
    mvr_html = try_mvr_direct()
    if mvr_html:
        links = re.findall(r'href="(/press[^"]*(?:пътна|произшествия)[^"]*)"', mvr_html, re.IGNORECASE)
        links = list(dict.fromkeys(["https://www.mvr.bg"+l for l in links]))[:8]
        print(f"  Found {len(links)} links")
        for url in links:
            art = fetch(url)
            if not art: continue
            ud = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
            date = f"{ud.group(1)}-{int(ud.group(2)):02d}-{int(ud.group(3)):02d}" if ud else parse_date_bg(art[:3000])
            if not date or date in existing_dates: continue
            acc = parse_accidents(art)
            new_days.append({"date":date,"url":url,"source":"mvr.bg",
                "scraped_at":datetime.now(timezone.utc).isoformat(),**acc})
            existing_dates.add(date)
            print(f"  MVR: {date} light={acc['light']} dead={acc['dead']}")

    # 2. Try news RSS if MVR gave nothing
    if not new_days:
        print("\n2. Trying Bulgarian news RSS...")
        new_days += try_rss_sources(existing_dates)

    # Merge and save
    all_days = existing.get("days", []) + new_days
    all_days.sort(key=lambda x: x["date"], reverse=True)
    cutoff = (datetime.now()-timedelta(days=90)).strftime("%Y-%m-%d")
    all_days = [d for d in all_days if d["date"] >= cutoff]

    result = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "МВР / Новинарски RSS",
        "note": "Автоматично парсване",
        "days_count": len(all_days),
        "new_today": len(new_days),
        "days": all_days
    }
    save(result)
    print(f"\nDone — {len(new_days)} new")

if __name__ == "__main__":
    main()
