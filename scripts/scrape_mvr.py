#!/usr/bin/env python3
"""
MVR Road Accidents Scraper
Runs daily via GitHub Actions → writes data/mvr_accidents.json
"""
import urllib.request
import json
import re
import os
from datetime import datetime, timedelta, timezone

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'bg,en;q=0.9',
}

MVR_LIST_URL = 'https://www.mvr.bg/press/%D0%B0%D0%BA%D1%82%D1%83%D0%B0%D0%BB%D0%BD%D0%B0-%D0%B8%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%86%D0%B8%D1%8F/%D0%B0%D0%BA%D1%82%D1%83%D0%B0%D0%BB%D0%BD%D0%B0-%D0%B8%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%86%D0%B8%D1%8F/%D0%BF%D1%8A%D1%82%D0%BD%D0%B0-%D0%BE%D0%B1%D1%81%D1%82%D0%B0%D0%BD%D0%BE%D0%B2%D0%BA%D0%B0'

BG_MONTHS = {
    'януари':1,'февруари':2,'март':3,'април':4,'май':5,'юни':6,
    'юли':7,'август':8,'септември':9,'октомври':10,'ноември':11,'декември':12
}

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode('utf-8', errors='replace')

def parse_date_bg(text):
    """Parse Bulgarian date like '18 Април 2026' → '2026-04-18'"""
    text = text.lower().strip()
    m = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', text)
    if not m:
        return None
    day, month_bg, year = int(m.group(1)), m.group(2), int(m.group(3))
    month = BG_MONTHS.get(month_bg)
    if not month:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"

def parse_article_links(html):
    """Extract links to individual daily reports from the list page."""
    # MVR uses standard <a href="..."> links with Bulgarian text
    pattern = r'href="(/press[^"]+пътни[^"]*(?:произшествия|инциденти)[^"]*)"'
    links = re.findall(pattern, html, re.IGNORECASE)
    # Also try date-titled links
    pattern2 = r'href="(/press/[^"]+/\d{4}/[^"]+)"'
    links += re.findall(pattern2, html, re.IGNORECASE)
    seen = set()
    result = []
    for l in links:
        if l not in seen:
            seen.add(l)
            result.append('https://www.mvr.bg' + l)
    return result[:10]  # last 10 days max

def extract_date_from_title(html):
    """Try to find the report date inside the article."""
    # Look for Bulgarian date pattern in title or heading
    m = re.search(r'(\d{1,2})\s+(януари|февруари|март|април|май|юни|юли|август|септември|октомври|ноември|декември)\s+(\d{4})',
                  html, re.IGNORECASE)
    if m:
        return parse_date_bg(m.group(0))
    return None

def parse_accidents(html):
    """
    Extract accident numbers from MVR daily report text.
    MVR format (Bulgarian):
    'регистрирани X леки пътнотранспортни произшествия'
    'X тежки пътнотранспортни произшествия'  
    'X загинали', 'X ранени'
    """
    # Strip HTML tags for easier parsing
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)

    result = {
        'light': None,    # леки ПТП
        'serious': None,  # тежки ПТП
        'dead': None,     # загинали
        'injured': None,  # ранени
        'total': None,    # общо ПТП
        'source_text': text[:500]  # snippet for debugging
    }

    # Patterns for Bulgarian accident text
    patterns = {
        'light':   [
            r'(\d+)\s+леки\s+(?:пътно)?транспортни',
            r'леки\s+(?:пътно)?транспортни\s+произшествия[^.]*?(\d+)',
            r'(\d+)\s+леки\s+ПТП',
        ],
        'serious': [
            r'(\d+)\s+тежки\s+(?:пътно)?транспортни',
            r'тежки\s+(?:пътно)?транспортни\s+произшествия[^.]*?(\d+)',
            r'(\d+)\s+тежки\s+ПТП',
        ],
        'dead': [
            r'(\d+)\s+(?:са\s+)?загинали',
            r'загинали\s+(\d+)',
            r'(\d+)\s+(?:човека?\s+)?загина',
        ],
        'injured': [
            r'(\d+)\s+(?:са\s+)?ранени',
            r'ранени\s+(\d+)',
            r'(\d+)\s+(?:души\s+)?(?:са\s+)?пострадали',
        ],
    }

    for key, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                # find the actual number group (not always group 1)
                for g in m.groups():
                    if g and g.isdigit():
                        result[key] = int(g)
                        break
                if result[key] is not None:
                    break

    # Total = light + serious if both found
    if result['light'] is not None and result['serious'] is not None:
        result['total'] = result['light'] + result['serious']
    elif result['light'] is not None:
        result['total'] = result['light']

    return result

def load_existing():
    """Load existing data file if present."""
    path = 'data/mvr_accidents.json'
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'updated': None, 'days': []}

def save(data):
    os.makedirs('data', exist_ok=True)
    path = 'data/mvr_accidents.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(data['days'])} days to {path}")

def main():
    print(f"Starting MVR scraper — {datetime.now(timezone.utc).isoformat()}")
    
    existing = load_existing()
    existing_dates = {d['date'] for d in existing.get('days', [])}
    new_days = []

    try:
        print(f"Fetching list: {MVR_LIST_URL}")
        list_html = fetch(MVR_LIST_URL)
        links = parse_article_links(list_html)
        print(f"Found {len(links)} article links")

        for url in links:
            try:
                print(f"  Fetching: {url}")
                html = fetch(url)

                # Try to get date from URL first
                date_str = None
                url_date = re.search(r'/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
                if url_date:
                    y,mo,d = url_date.groups()
                    date_str = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
                else:
                    date_str = extract_date_from_title(html)

                if not date_str:
                    print(f"    Could not parse date from {url}")
                    continue

                if date_str in existing_dates:
                    print(f"    Already have {date_str}, skipping")
                    continue

                accidents = parse_accidents(html)
                day_data = {
                    'date': date_str,
                    'url': url,
                    'scraped_at': datetime.now(timezone.utc).isoformat(),
                    **accidents
                }
                new_days.append(day_data)
                print(f"    {date_str}: light={accidents['light']}, serious={accidents['serious']}, "
                      f"dead={accidents['dead']}, injured={accidents['injured']}")

            except Exception as e:
                print(f"    Error fetching {url}: {e}")

    except Exception as e:
        print(f"Error fetching list page: {e}")
        # Write empty update so GitHub Actions doesn't fail
        existing['updated'] = datetime.now(timezone.utc).isoformat()
        existing['error'] = str(e)
        save(existing)
        return

    # Merge new with existing, sort by date desc
    all_days = existing.get('days', []) + new_days
    all_days.sort(key=lambda x: x['date'], reverse=True)
    # Keep last 90 days
    cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    all_days = [d for d in all_days if d['date'] >= cutoff]

    result = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'source': 'МВР — Пътна обстановка',
        'note': 'Данните са парснати автоматично от mvr.bg. Може да съдържат грешки.',
        'days_count': len(all_days),
        'new_today': len(new_days),
        'days': all_days
    }
    save(result)
    print(f"Done. {len(new_days)} new days added.")

if __name__ == '__main__':
    main()
