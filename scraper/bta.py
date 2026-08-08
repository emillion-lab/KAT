#!/usr/bin/env python3
"""БТА scraper — ежедневната справка на МВР, национално И за София.

Защо БТА: mvr.bg е зад Cloudflare Turnstile (403 дори на истински браузър),
а gis.mvr.bg иска token. БТА е държавна агенция, отдава се без защита и
преиздава съобщението на пресцентъра дословно — включително софийските числа,
които никъде другаде ги няма в машинно четим вид.

Как се стига до статиите (проверено):
  ✓ https://www.bta.bg/bg/news/bulgaria/rss   — 20 най-нови
  ✓ ?page=N на рубриката                      — за назад
  ✗ търсачката — клиентска, сървърът не връща резултати

Текстът НЕ е с един шаблон. Реални варианти 2025–2026:
  "станали 23 катастрофи, при които са загинали двама души и са ранени 28"
  "регистрирани 20 тежки катастрофи с 29 ранени" + отделно "няма загинали"
  "станали 10 тежки пътнотранспортни произшествия, при които са пострадали 11"
Числата са ту с цифри, ту с думи ("двама", "трима", "четирима").

Два капана, и двата ги обезвреждаме:
  1. Същият текст носи годишни суми — "от началото на годината 5693 катастрофи
     с 380 загинали". Наивен regex хваща тях. Изреченията с "от началото на"
     се махат ПРЕДИ търсенето на числа.
  2. Пълният HTML съдържа менюто на сайта с всички области ("Благоевград
     Бургас Варна... София..."), което трови търсенето на софийското изречение.
     Затова се реже само същинският текст на статията.
"""
import json, os, re, datetime, urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept-Language': 'bg-BG,bg;q=0.9'}
LOG = []
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.append(s)

def get(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')

WORDS = {'един':1,'едно':1,'една':1,'двама':2,'две':2,'трима':3,'три':3,
         'четирима':4,'четири':4,'петима':5,'пет':5,'шестима':6,'шест':6,
         'седмина':7,'седем':7,'осмина':8,'осем':8,'деветима':9,'девет':9,
         'десетима':10,'десет':10,'единадесет':11,'дванадесет':12}
NUM = r'(\d{1,4}|[а-яА-Я]{3,12})'

def num(tok):
    if not tok: return None
    t = tok.strip().lower()
    if t.isdigit():
        v = int(t)
        return v if v < 500 else None      # над 500 = годишна сума
    for w in sorted(WORDS, key=len, reverse=True):
        if t.startswith(w): return WORDS[w]
    return None

def body_text(html):
    """Само същинският текст: без меню, скриптове и странични блокове."""
    m = re.search(r'<article[\s\S]{0,200000}?</article>', html, re.I)
    chunk = m.group(0) if m else ''
    if len(chunk) < 200:
        m = re.search(r'(?:itemprop="articleBody"|class="[^"]*article[^"]*body[^"]*")'
                      r'[\s\S]{0,200000}?</div>', html, re.I)
        chunk = m.group(0) if m else ''
    if len(chunk) < 200:
        # краен вариант: описанието в мета-таговете носи цялото резюме
        m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]{80,})"', html, re.I)
        chunk = m.group(1) if m else html
    chunk = re.sub(r'<(script|style)[\s\S]*?</\1>', ' ', chunk, flags=re.I)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', chunk)).strip()

def drop_totals(t):
    return ' '.join(s for s in re.split(r'(?<=[.!?])\s+', t)
                    if not re.search(r'от\s+начало(то)?\s+на|за\s+същия\s+период|спрямо', s, re.I))

def parse(text):
    t = drop_totals(text)
    out = {}
    for pat in [r'в\s+страната\s+са\s+(?:станали|регистрирани)\s+' + NUM,
                r'са\s+(?:станали|регистрирани)\s+' + NUM + r'\s+(?:тежки\s+)?(?:пътнотранспортни|катастроф|ПТП)',
                r'при\s+' + NUM + r'\s+катастрофи']:
        m = re.search(pat, t, re.I)
        if m and num(m.group(1)) is not None:
            out['total'] = num(m.group(1)); break

    if re.search(r'(няма|без)\s+загинали', t, re.I):
        out['dead'] = 0
    else:
        for pat in [r'са\s+загинали\s+' + NUM, r'загинали\s+са\s+' + NUM,
                    NUM + r'\s+(?:човек|души)\s+(?:е\s+|са\s+)?загина',
                    r'загинал\w*\s+' + NUM]:
            m = re.search(pat, t, re.I)
            if m and num(m.group(1)) is not None:
                out['dead'] = num(m.group(1)); break

    for pat in [r'с\s+' + NUM + r'\s+ранени', r'а\s+' + NUM + r'\s+(?:души\s+)?са\s+ранени',
                r'са\s+ранени\s+' + NUM, r'са\s+пострадали\s+' + NUM,
                r'ранени\s+' + NUM + r'\s+души']:
        m = re.search(pat, t, re.I)
        if m and num(m.group(1)) is not None:
            out['injured'] = num(m.group(1)); break

    # София — само изречението, започващо с "В София"
    sof = re.search(r'В\s+София[^.]{5,300}\.', t)
    if sof:
        s = sof.group(0)
        m = re.search(NUM + r'\s+леки', s, re.I) or re.search(r'леки[^.\d]{0,25}(?:са\s+)?' + NUM, s, re.I)
        if m and num(m.group(1)) is not None: out['sofia_light'] = num(m.group(1))
        m = re.search(NUM + r'\s+тежки', s, re.I) or re.search(r'тежките\s+са\s+' + NUM, s, re.I)
        if m and num(m.group(1)) is not None: out['sofia_serious'] = num(m.group(1))
        m = re.search(r'ранени\s+(?:са\s+)?' + NUM, s, re.I) or re.search(r'с\s+' + NUM + r'\s+ранени', s, re.I)
        if m and num(m.group(1)) is not None: out['sofia_injured'] = num(m.group(1))
        out['sofia_sentence'] = s[:180]
    return out

def article_urls():
    urls = set()
    try:
        rss = get('https://www.bta.bg/bg/news/bulgaria/rss')
        urls |= set(re.findall(r'<link>\s*(https://www\.bta\.bg/bg/news/[^<\s]+)', rss))
        log(f'RSS: {len(urls)} адреса')
    except Exception as ex:
        log(f'RSS FAIL: {ex}')
    for p in range(1, 9):
        try:
            html = get(f'https://www.bta.bg/bg/news/bulgaria?page={p}')
            found = set('https://www.bta.bg' + u for u in
                        re.findall(r'href="(/bg/news/[a-z]+/\d{6,8}-[a-z0-9\-]+)"', html))
            urls |= found
        except Exception as ex:
            log(f'стр.{p} FAIL: {ex}'); break
    log(f'общо адреси: {len(urls)}')
    return [u for u in urls if re.search(r'denonosht|katastrof|ptp|ranen|zagin', u, re.I)]

def main():
    os.makedirs('data', exist_ok=True)
    cands = article_urls()
    log(f'кандидати за ежедневна справка: {len(cands)}')

    old = {}
    if os.path.exists('data/bta_daily.json'):
        try:
            old = {d['date']: d for d in json.load(open('data/bta_daily.json'))['days'] if d.get('date')}
        except Exception: pass

    days = dict(old)
    for u in cands:
        try:
            html = get(u)
        except Exception as ex:
            log(f'  FAIL {u[-50:]}: {ex}'); continue
        txt = body_text(html)
        if 'изминалото денонощие' not in txt.lower(): continue
        rec = parse(txt)
        if not rec.get('total'): 
            log(f'  ? неразпознат: {u[-60:]}'); continue
        m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', html)
        pub = m.group(1) if m else None
        if pub:  # справката е за ПРЕДНОТО денонощие
            d = (datetime.date.fromisoformat(pub) - datetime.timedelta(days=1)).isoformat()
        else:
            continue
        rec['date'] = d; rec['url'] = u; rec['published'] = pub
        days[d] = rec
        log(f"  ✓ {d}  нац={rec.get('total')} загин={rec.get('dead')} ранени={rec.get('injured')}"
            f" | София леки={rec.get('sofia_light')} тежки={rec.get('sofia_serious')}"
            f" ранени={rec.get('sofia_injured')}")

    with open('data/bta_daily.json', 'w', encoding='utf-8') as f:
        json.dump({'generated': datetime.datetime.utcnow().isoformat()+'Z',
                   'days': [days[d] for d in sorted(days)]}, f, ensure_ascii=False, indent=1)
    log(f'записани общо {len(days)} дни (нови този път: {len(days)-len(old)})')
    open('data/bta_log.txt', 'w', encoding='utf-8').write('\n'.join(LOG))

if __name__ == '__main__':
    main()
