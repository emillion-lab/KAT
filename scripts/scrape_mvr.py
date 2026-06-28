#!/usr/bin/env python3
"""
MVR Road Accidents Scraper v2
Tries multiple URL patterns + Wayback Machine fallback
"""
import urllib.request
import json
import re
import os
from datetime import datetime, timedelta, timezone

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control': 'max-age=0',
}

# Multiple URL patterns to try
MVR_URLS = [
    'https://www.mvr.bg/press/актуална-информация/актуална-информация/пътна-обстановка',
    'https://mvr.bg/press/%D0%B0%D0%BA%D1%82%D1%83%D0%B0%D0%BB%D0%BD%D0%B0-%D0%B8%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%86%D0%B8%D1%8F/%D0%BF%D1%8A%D1%82%D0%BD%D0%B0-%D0%BE%D0%B1%D1%81%D1%82%D0%B0%D0%BD%D0%BE%D0%B2%D0%BA%D0%B0',
    'https://www.mvr.bg/press',
]

BG_MONTHS = {
    'януари':1,'февруари':2,'март':3,'април':4,'май':5,'юни':6,
    'юли':7,'август':8,'септември':9,'октомври':10,'ноември':11,'декември':12
}

def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try: return raw.decode('utf-8')
            except: return raw.decode('latin-1', errors='replace')
    except Exception as e:
        print(f"  fetch failed: {e}")
        return None

def fetch_wayback(mvr_path):
    """Try to get recent version from Wayback Machine"""
    encoded = urllib.request.quote(f"https://www.mvr.bg{mvr_path}")
    # Check availability
    avail_url = f"https://archive.org/wayback/available?url={encoded}"
    try:
        with urllib.request.urlopen(avail_url, timeout=15) as r:
            data = json.loads(r.read())
            snap = data.get('archived_snapshots', {}).get('closest', {})
            if snap.get('available') and snap.get('url'):
                print(f"  Wayback snapshot: {snap['url']}")
                return fetch(snap['url'])
    except Exception as e:
        print(f"  Wayback check failed: {e}")
    return None

def parse_date_bg(text):
    text = text.lower().strip()
    m = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', text)
    if not m: return None
    day, month_bg, year = int(m.group(1)), m.group(2), int(m.group(3))
    month = BG_MONTHS.get(month_bg)
    if not month: return None
    return f"{year:04d}-{month:02d}-{day:02d}"

def parse_article_links(html):
    """Extract links to daily road reports - try multiple patterns"""
    links = []
    seen = set()
    
    # Pattern 1: пътна обстановка links
    for pat in [
        r'href="(/press[^"]*(?:пътна|patna|road)[^"]*)"\s*',
        r'href="(/press[^"]*(?:произшествия|accidents)[^"]*)"\s*',
        r'href="(/press[^"]+/\d{4}/[^"]+)"',
        r'href="(/news[^"]*(?:пътна|катастроф)[^"]*)"\s*',
    ]:
        for link in re.findall(pat, html, re.IGNORECASE | re.UNICODE):
            if link not in seen:
                seen.add(link)
                links.append('https://www.mvr.bg' + link)
    
    return links[:15]

def parse_accidents(html):
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    result = {'light': None, 'serious': None, 'dead': None, 'injured': None, 'total': None}
    patterns = {
        'light':   [r'(\d+)\s+леки\s+(?:пътно)?транспортни', r'(\d+)\s+леки\s+ПТП'],
        'serious': [r'(\d+)\s+тежки\s+(?:пътно)?транспортни', r'(\d+)\s+тежки\s+ПТП'],
        'dead':    [r'(\d+)\s+(?:са\s+)?загинали', r'(\d+)\s+(?:човека?\s+)?загина'],
        'injured': [r'(\d+)\s+(?:са\s+)?ранени', r'(\d+)\s+(?:души\s+)?пострадали'],
    }
    for key, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                for g in m.groups():
                    if g and g.isdigit():
                        result[key] = int(g); break
                if result[key] is not None: break
    if result['light'] is not None and result['serious'] is not None:
        result['total'] = result['light'] + result['serious']
    elif result['light'] is not None:
        result['total'] = result['light']
    return result

def extract_date(html, url):
    # From URL
    m = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
    if m: y,mo,d = m.groups(); return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    # From HTML
    m2 = re.search(r'(\d{1,2})\s+(януари|февруари|март|април|май|юни|юли|август|септември|октомври|ноември|декември)\s+(\d{4})',
                   html[:3000], re.IGNORECASE)
    if m2: return parse_date_bg(m2.group(0))
    return None

def load_existing():
    path = 'data/mvr_accidents.json'
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'updated': None, 'days': []}

def save(data):
    os.makedirs('data', exist_ok=True)
    with open('data/mvr_accidents.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(data['days'])} days")

def main():
    print(f"MVR Scraper v2 — {datetime.now(timezone.utc).isoformat()}")
    existing = load_existing()
    existing_dates = {d['date'] for d in existing.get('days', [])}
    new_days = []
    html = None

    # Try each MVR URL
    for mvr_url in MVR_URLS:
        print(f"Trying: {mvr_url}")
        html = fetch(mvr_url)
        if html and ('пътна' in html.lower() or 'произшествия' in html.lower() or 'mvr' in html.lower()):
            print(f"  ✓ Got content ({len(html)} chars)")
            break
        html = None

    # Fallback: Wayback Machine
    if not html:
        print("Direct access failed — trying Wayback Machine...")
        html = fetch_wayback('/press/%D0%B0%D0%BA%D1%82%D1%83%D0%B0%D0%BB%D0%BD%D0%B0-%D0%B8%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%86%D0%B8%D1%8F/%D0%BF%D1%8A%D1%82%D0%BD%D0%B0-%D0%BE%D0%B1%D1%81%D1%82%D0%B0%D0%BD%D0%BE%D0%B2%D0%BA%D0%B0')

    if not html:
        print("All sources failed — keeping existing data")
        existing['updated'] = datetime.now(timezone.utc).isoformat()
        existing['error'] = 'All sources returned no data'
        save(existing)
        return

    links = parse_article_links(html)
    print(f"Found {len(links)} article links")

    for url in links:
        try:
            article_html = fetch(url)
            if not article_html:
                # Try wayback for this article too
                path = url.replace('https://www.mvr.bg', '')
                article_html = fetch_wayback(path)
            if not article_html: continue

            date_str = extract_date(article_html, url)
            if not date_str:
                print(f"  No date in {url}")
                continue
            if date_str in existing_dates:
                print(f"  Already have {date_str}")
                continue

            acc = parse_accidents(article_html)
            new_days.append({'date': date_str, 'url': url,
                'scraped_at': datetime.now(timezone.utc).isoformat(), **acc})
            print(f"  {date_str}: light={acc['light']}, dead={acc['dead']}, injured={acc['injured']}")
        except Exception as e:
            print(f"  Error: {e}")

    all_days = existing.get('days', []) + new_days
    all_days.sort(key=lambda x: x['date'], reverse=True)
    cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    all_days = [d for d in all_days if d['date'] >= cutoff]

    result = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'source': 'МВР — Пътна обстановка',
        'note': 'Автоматично парсване от mvr.bg / archive.org',
        'days_count': len(all_days),
        'new_today': len(new_days),
        'days': all_days
    }
    save(result)
    print(f"Done — {len(new_days)} new days")

if __name__ == '__main__':
    main()
