#!/usr/bin/env python3
"""
MVR Road Accidents Scraper - tries direct + proxies
"""
import urllib.request
import urllib.parse
import json
import re
import os
import gzip
from datetime import datetime, timedelta, timezone

MVR_URL = 'https://www.mvr.bg/press/%D0%B0%D0%BA%D1%82%D1%83%D0%B0%D0%BB%D0%BD%D0%B0-%D0%B8%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%86%D0%B8%D1%8F/%D0%B0%D0%BA%D1%82%D1%83%D0%B0%D0%BB%D0%BD%D0%B0-%D0%B8%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%86%D0%B8%D1%8F/%D0%BF%D1%8A%D1%82%D0%BD%D0%B0-%D0%BE%D0%B1%D1%81%D1%82%D0%B0%D0%BD%D0%BE%D0%B2%D0%BA%D0%B0'

BG_MONTHS = {
    'януари':1,'февруари':2,'март':3,'април':4,'май':5,'юни':6,
    'юли':7,'август':8,'септември':9,'октомври':10,'ноември':11,'декември':12
}

UA_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36',
]

def fetch_raw(url, ua=None, timeout=15):
    headers = {
        'User-Agent': ua or UA_LIST[0],
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'bg-BG,bg;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        if r.headers.get('Content-Encoding') == 'gzip':
            data = gzip.decompress(data)
        return data.decode('utf-8', errors='replace')

def fetch_page(target_url):
    # 1. Try direct with each UA
    for ua in UA_LIST:
        try:
            text = fetch_raw(target_url, ua=ua)
            if len(text) > 500:
                print(f"  Direct OK ({len(text)} chars)")
                return text
        except Exception as e:
            print(f"  Direct UA failed: {e}")

    # 2. Try proxies
    proxies = [
        f'https://api.allorigins.win/raw?url={urllib.parse.quote(target_url, safe="")}',
        f'https://corsproxy.io/?{urllib.parse.quote(target_url, safe="")}',
        f'https://api.codetabs.com/v1/proxy?quest={urllib.parse.quote(target_url, safe="")}',
        f'https://thingproxy.freeboard.io/fetch/{target_url}',
    ]
    for proxy_url in proxies:
        try:
            text = fetch_raw(proxy_url, ua='KAT-scraper/1.0', timeout=20)
            if len(text) > 500:
                print(f"  Proxy OK: {proxy_url[:60]}")
                return text
            print(f"  Proxy empty: {proxy_url[:50]}")
        except Exception as e:
            print(f"  Proxy fail: {proxy_url[:50]}: {e}")

    print(f"  ALL METHODS FAILED: {target_url[:60]}")
    return None

def parse_date_bg(text):
    text = text.lower().strip()
    m = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', text)
    if not m:
        return None
    day, month_bg, year = int(m.group(1)), m.group(2), int(m.group(3))
    month = BG_MONTHS.get(month_bg)
    if not month:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"

def parse_links(html):
    seen = set()
    links = []
    for pat in [
        r'href="(/press[^"]+(?:пътни|произшествия|инциденти)[^"]*)"',
        r'href="(/press/[^"]+/\d{4}/[^"]+)"',
        r'href="(/press[^"]+пътна[^"]+)"',
    ]:
        for l in re.findall(pat, html, re.IGNORECASE):
            if l not in seen:
                seen.add(l)
                links.append('https://www.mvr.bg' + l)
    return links[:10]

def parse_accidents(html):
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    result = {'light': None, 'serious': None, 'dead': None, 'injured': None, 'total': None}
    pats = {
        'light':   [r'(\d+)\s+леки\s+(?:пътно)?транспортни', r'(\d+)\s+леки\s+ПТП'],
        'serious': [r'(\d+)\s+тежки\s+(?:пътно)?транспортни', r'(\d+)\s+тежки\s+ПТП'],
        'dead':    [r'(\d+)\s+(?:са\s+)?загинали', r'(\d+)\s+(?:човека?\s+)?загина'],
        'injured': [r'(\d+)\s+(?:са\s+)?ранени', r'(\d+)\s+(?:души\s+)?пострадали'],
    }
    for key, patterns in pats.items():
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                for g in m.groups():
                    if g and g.isdigit():
                        result[key] = int(g)
                        break
                if result[key] is not None:
                    break
    if result['light'] is not None and result['serious'] is not None:
        result['total'] = result['light'] + result['serious']
    elif result['light'] is not None:
        result['total'] = result['light']
    return result

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
    print(f"MVR Scraper — {datetime.now(timezone.utc).isoformat()}")
    existing = load_existing()
    existing_dates = {d['date'] for d in existing.get('days', [])}
    new_days = []

    list_html = fetch_page(MVR_URL)
    if not list_html:
        print("Cannot reach MVR — keeping existing data")
        existing['updated'] = datetime.now(timezone.utc).isoformat()
        existing['error'] = 'All fetch methods blocked by MVR'
        save(existing)
        return

    links = parse_links(list_html)
    print(f"Found {len(links)} article links")

    for url in links:
        try:
            html = fetch_page(url)
            if not html:
                continue
            date_str = None
            m = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
            if m:
                y, mo, d = m.groups()
                date_str = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
            else:
                m2 = re.search(r'(\d{1,2})\s+(януари|февруари|март|април|май|юни|юли|август|септември|октомври|ноември|декември)\s+(\d{4})', html, re.IGNORECASE)
                if m2:
                    date_str = parse_date_bg(m2.group(0))
            if not date_str or date_str in existing_dates:
                continue
            acc = parse_accidents(html)
            new_days.append({'date': date_str, 'url': url,
                             'scraped_at': datetime.now(timezone.utc).isoformat(), **acc})
            print(f"  {date_str}: {acc}")
        except Exception as e:
            print(f"  Error {url[:50]}: {e}")

    all_days = existing.get('days', []) + new_days
    all_days.sort(key=lambda x: x['date'], reverse=True)
    cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    all_days = [d for d in all_days if d['date'] >= cutoff]

    save({
        'updated': datetime.now(timezone.utc).isoformat(),
        'source': 'МВР — Пътна обстановка',
        'note': 'Парснато автоматично от mvr.bg.',
        'days_count': len(all_days),
        'new_today': len(new_days),
        'days': all_days
    })
    print(f"Done. {len(new_days)} new days added.")

if __name__ == '__main__':
    main()
