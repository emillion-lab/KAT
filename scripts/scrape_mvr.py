#!/usr/bin/env python3
"""MVR/ПТП scraper v5 — news backfill edition.
Ново спрямо v4:
  • BACKFILL_DAYS (env) — обхожда Google News RSS с after:/before: прозорци назад във времето
  • Чете и ТЯЛОТО на статията (следва линка), не само заглавието
  • Разбира словесни числа: "Четирима са загинали" → 4
  • Извлича и София-специфичния брой: "В София са регистрирани N леки пътни инцидента" → sofia_light
  • Датата на данните = денят ПРЕДИ публикацията ("за изминалото денонощие")
Никога не трие стари дни — само добавя/обогатява.
"""
import urllib.request, json, re, os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from email.utils import parsedate_to_datetime

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
      "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8"}
DATA = "data/mvr_accidents.json"
SOFIA = timezone(timedelta(hours=3))
BACKFILL_DAYS = int(os.environ.get("BACKFILL_DAYS", "3"))

QUERIES = [
    'МВР катастрофи денонощие пострадали',
    '"за денонощието" катастрофи загинали',
    'статистика МВР катастрофи "леки пътни инцидента"',
    'пътнотранспортни произшествия "изминалото денонощие"',
]

WORD_NUM = {"един":1,"една":1,"едно":1,"двама":2,"два":2,"две":2,"трима":3,"три":3,
            "четирима":4,"четири":4,"петима":5,"пет":5,"шестима":6,"шест":6,
            "седмина":7,"седем":7,"осмина":8,"осем":8,"деветима":9,"девет":9,
            "десетима":10,"десет":10,"единадесет":11,"дванадесет":12}
NUM_RE = r"(\d+|" + "|".join(WORD_NUM.keys()) + r")"

def to_int(s):
    s = s.strip().lower()
    return int(s) if s.isdigit() else WORD_NUM.get(s)


def decode_gnews(link):
    """news.google.com/rss/articles/CBMi... → оригиналният URL е base64-кодиран в id-то."""
    import base64 as b64
    m = re.search(r"articles/([^?/]+)", link)
    if not m:
        return None
    tok = m.group(1)
    try:
        pad = tok + "=" * (-len(tok) % 4)
        rawb = b64.urlsafe_b64decode(pad)
        urls = re.findall(rb"https?://[\x20-\x7e]+?(?=[\x00-\x1f\xd2\x01]|$)", rawb)
        for u in urls:
            s = u.decode("ascii", "ignore").strip()
            if "google.com" not in s and len(s) > 12:
                return s
    except Exception:
        pass
    return None

def fetch(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  fetch fail {url[:70]}: {e}")
        return None

def strip_html(html):
    html = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.DOTALL|re.IGNORECASE)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))

def find_num(t, pats):
    for p in pats:
        m = re.search(p, t, re.IGNORECASE)
        if m:
            for g in m.groups():
                if g:
                    v = to_int(g)
                    if v is not None:
                        return v
    return None

def extract_counts(text):
    t = strip_html(text)
    ptp     = find_num(t, [NUM_RE + r"\s+пътнотранспортни\s+произшеств",
                           r"при\s+" + NUM_RE + r"\s+катастроф",
                           NUM_RE + r"\s+катастроф", NUM_RE + r"\s+ПТП\b"])
    dead    = find_num(t, [NUM_RE + r"\s+(?:души\s+)?(?:са\s+)?загинал",
                           NUM_RE + r"\s+(?:човека?\s+)?загина", NUM_RE + r"\s+жертв"])
    injured = find_num(t, [NUM_RE + r"\s+(?:души\s+)?(?:са\s+)?(?:ранен|пострадал)"])
    serious = find_num(t, [r"[Тт]ежките\s+(?:пътнотранспортни\s+произшествия|ПТП|катастрофи)[^.]{0,40}?са\s+" + NUM_RE,
                           NUM_RE + r"\s+тежки"])
    sofia_light = find_num(t, [r"[Вв]\s+София\s+са\s+регистрирани\s+" + NUM_RE + r"\s+леки",
                               r"[Нн]а\s+територията\s+на\s+СДВР[^.]{0,60}?" + NUM_RE + r"\s+(?:леки|ПТП|инцидент)",
                               r"[Вв]\s+София[^.]{0,60}?" + NUM_RE + r"\s+(?:леки\s+)?(?:пътни\s+)?инцидент"])
    if not any(v is not None for v in [ptp, dead, injured, sofia_light]):
        return None
    return {"ptp": ptp, "dead": dead, "injured": injured,
            "serious": serious, "light": None, "sofia_light": sofia_light}

def looks_like_daily(blob):
    return re.search(r"денонощие|пътна обстановка|за изминал|черна статистика", blob, re.IGNORECASE)

def rss_items(xml):
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.DOTALL):
        g = lambda tag: (re.search(rf"<{tag}>(.*?)</{tag}>", it, re.DOTALL) or [None,""])[1] if re.search(rf"<{tag}>", it) else ""
        title = re.sub(r"<!\[CDATA\[|\]\]>", "", g("title")).strip()
        desc  = re.sub(r"<!\[CDATA\[|\]\]>", "", g("description")).strip()
        link  = re.sub(r"<!\[CDATA\[|\]\]>", "", g("link")).strip()
        pub   = g("pubDate")
        out.append((title, desc, link, pub))
    return out

def better(new, old):
    """Обогати old запис с полета от new, без да губиш нищо."""
    merged = dict(old)
    for k, v in new.items():
        if v is not None and merged.get(k) is None:
            merged[k] = v
    return merged

def main():
    try:
        data = json.load(open(DATA, encoding="utf-8"))
    except Exception:
        data = {"days": []}
    days = {d["date"]: d for d in data.get("days", []) if d.get("date")}
    now = datetime.now(SOFIA)
    found = 0

    # Прозорци: последните BACKFILL_DAYS, на стъпки от 5 дни
    windows = []
    end = now.date() + timedelta(days=1)
    start_limit = now.date() - timedelta(days=BACKFILL_DAYS)
    cur = end
    while cur > start_limit:
        w_start = max(start_limit, cur - timedelta(days=5))
        windows.append((w_start, cur))
        cur = w_start
    print(f"Backfill: {BACKFILL_DAYS} дни, {len(windows)} прозореца, {len(QUERIES)} заявки")

    seen_links = set()
    for (w1, w2) in windows:
        for q in QUERIES:
            full_q = f"{q} after:{w1.isoformat()} before:{w2.isoformat()}"
            url = "https://news.google.com/rss/search?q=" + quote(full_q) + "&hl=bg&gl=BG&ceid=BG:bg"
            xml = fetch(url)
            if not xml:
                continue
            for title, desc, link, pub in rss_items(xml):
                if link in seen_links:
                    continue
                seen_links.add(link)
                blob = title + " " + desc
                if not looks_like_daily(blob):
                    continue
                counts = extract_counts(blob)
                # ако заглавието няма достатъчно числа — пробвай тялото на статията
                if not counts or counts.get("sofia_light") is None:
                    real_url = decode_gnews(link) or link
                    body = fetch(real_url)
                    if body:
                        body_counts = extract_counts(body[:40000])
                        if body_counts:
                            counts = better(body_counts, counts or {})
                if not counts:
                    continue
                try:
                    d = parsedate_to_datetime(pub).astimezone(SOFIA)
                except Exception:
                    d = now
                date_iso = (d - timedelta(days=1)).date().isoformat()  # данните са за предния ден
                entry = {"date": date_iso, "source": "news", **counts,
                         "headline": title[:160]}
                if date_iso in days:
                    days[date_iso] = better(entry, days[date_iso])
                else:
                    days[date_iso] = entry
                    found += 1
                    print(f"  + {date_iso}: ПТП={counts.get('ptp')} София_леки={counts.get('sofia_light')} загинали={counts.get('dead')} | {title[:70]}")

    # чистка: съседни дни с идентични числа са една и съща статия, препубликувана със закъснение
    ordered = sorted(days.values(), key=lambda x: x["date"])
    cleaned = []
    for d_ in ordered:
        if cleaned:
            p = cleaned[-1]
            from datetime import date as _date
            d1 = _date.fromisoformat(p["date"]); d2 = _date.fromisoformat(d_["date"])
            same = all(p.get(k) == d_.get(k) for k in ("ptp","dead","injured"))
            has_num = any(d_.get(k) is not None for k in ("ptp","dead","injured"))
            if (d2 - d1).days == 1 and same and has_num:
                print(f"  – дубликат: {d_['date']} == {p['date']} (препубликация), пропускам")
                continue
        cleaned.append(d_)
    days = {d_["date"]: d_ for d_ in cleaned}
    data["days"] = sorted(days.values(), key=lambda x: x["date"], reverse=True)
    data["updated"] = now.isoformat()
    data["days_count"] = len(data["days"])
    data["status"] = "live_news" if found or data["days"] else "frozen"
    data["source"] = "Google News RSS — дневни МВР справки (backfill v5)"
    data.setdefault("mvr_news_url", "https://boulevardbulgaria.bg/articles/martin-atanasov-mvr-tihomalkom-sprya-kartata-s-danni-za-ptp")
    json.dump(data, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Готово: {found} нови дни, общо {len(data['days'])}")

if __name__ == "__main__":
    main()
