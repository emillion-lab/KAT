#!/usr/bin/env python3
"""БТА scraper — ежедневната справка на МВР, национално И за София.

Защо БТА, а не mvr.bg: сайтът на министерството е зад Cloudflare Turnstile и
връща 403 дори на истински браузър. БТА е държавна агенция и преиздава
съобщението на пресцентъра дословно, включително софийските числа — които
досега липсваха напълно.

Текстът НЕ е с един шаблон. Реални варианти от 2025-2026:
  "станали 23 катастрофи, при които са загинали двама души и са ранени 28 души"
  "регистрирани 20 тежки катастрофи с 29 ранени" + отделно "няма загинали"
  "станали 10 тежки пътнотранспортни произшествия, при които са пострадали 11"
Числата са ту с цифри, ту с думи ("двама", "трима", "четирима").

Капан: същият текст съдържа и годишни суми — "от началото на годината 5693
катастрофи с 380 загинали". Наивен regex хваща тях. Затова всяко изречение с
"от началото на" се изхвърля ПРЕДИ да се търсят числа.

Изход: data/bta_daily.json — по един запис на ден:
  {date, total, dead, injured, sofia_light, sofia_serious, sofia_injured, url}
"""
import json, os, re, sys, datetime, urllib.request, urllib.parse

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept-Language': 'bg-BG,bg;q=0.9'}
LOG = []
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.append(s)

def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.getcode(), r.read().decode('utf-8', 'replace')

# ─── числителни с думи ───
WORDS = {'един':1,'един човек':1,'едно':1,'една':1,'двама':2,'двама души':2,'две':2,'двe':2,
         'трима':3,'три':3,'четирима':4,'четири':4,'петима':5,'пет':5,'шестима':6,'шест':6,
         'седмина':7,'седем':7,'осмина':8,'осем':8,'деветима':9,'девет':9,'десетима':10,'десет':10}

def num(tok):
    if tok is None: return None
    tok = tok.strip().lower()
    if tok.isdigit(): return int(tok)
    for w in sorted(WORDS, key=len, reverse=True):
        if tok.startswith(w): return WORDS[w]
    return None

NUM = r'(\d{1,4}|[а-я]{3,10})'

def clean(text):
    """Маха изреченията с натрупани суми — те съдържат най-големите числа."""
    keep = []
    for s in re.split(r'(?<=[.!?])\s+', text):
        if re.search(r'от\s+начало(то)?\s+на|за\s+същия\s+период|спрямо', s, re.I):
            continue
        keep.append(s)
    return ' '.join(keep)

def parse(text):
    t = clean(re.sub(r'\s+', ' ', text))
    out = {}

    # ── национално: брой ПТП ──
    for pat in [r'в\s+страната\s+са\s+(?:станали|регистрирани)\s+' + NUM,
                r'са\s+(?:станали|регистрирани)\s+' + NUM + r'\s+(?:тежки\s+)?(?:пътнотранспортни|катастроф|ПТП)']:
        m = re.search(pat, t, re.I)
        if m and num(m.group(1)) is not None:
            out['total'] = num(m.group(1)); break

    # ── национално: загинали ──
    if re.search(r'(няма|без)\s+загинали', t, re.I):
        out['dead'] = 0
    else:
        for pat in [r'загинали\s+са\s+' + NUM,
                    r'са\s+загинали\s+' + NUM,
                    NUM + r'\s+(?:човек|души)\s+(?:е\s+)?загинал',
                    r'при\s+които\s+(?:един\s+)?(\w+)\s+човек\s+е\s+загинал']:
            m = re.search(pat, t, re.I)
            if m and num(m.group(1)) is not None:
                out['dead'] = num(m.group(1)); break

    # ── национално: ранени ──
    for pat in [r'с\s+' + NUM + r'\s+ранени',
                r'(?:са\s+)?ранени\s+' + NUM,
                r'са\s+пострадали\s+' + NUM,
                NUM + r'\s+(?:души\s+)?са\s+ранени']:
        m = re.search(pat, t, re.I)
        if m and num(m.group(1)) is not None:
            out['injured'] = num(m.group(1)); break

    # ── София ──
    sof = re.search(r'В\s+София[^.]*\.', t, re.I)
    if sof:
        s = sof.group(0)
        m = re.search(NUM + r'\s+леки', s, re.I) or re.search(r'леки[^\d]{0,20}' + NUM, s, re.I)
        if m and num(m.group(1)) is not None: out['sofia_light'] = num(m.group(1))
        m = re.search(NUM + r'\s+тежки', s, re.I) or re.search(r'тежките\s+са\s+' + NUM, s, re.I)
        if m and num(m.group(1)) is not None: out['sofia_serious'] = num(m.group(1))
        m = re.search(r'ранени\s+(?:са\s+)?' + NUM, s, re.I) or re.search(r'с\s+' + NUM + r'\s+ранени', s, re.I)
        if m and num(m.group(1)) is not None: out['sofia_injured'] = num(m.group(1))
        out['sofia_sentence'] = s[:200]
    return out

def search_bta(page=1):
    q = urllib.parse.quote('през изминалото денонощие катастрофи')
    return f'https://www.bta.bg/bg/search?query={q}&page={page}'

def main():
    os.makedirs('data', exist_ok=True)
    # 1) проверка на достъпа
    try:
        code, body = get('https://www.bta.bg/bg')
        log(f'БТА достъп: HTTP {code}, {len(body)} знака')
        if 'turnstile' in body.lower() or 'cloudflare' in body.lower():
            log('ВНИМАНИЕ: открита защита Cloudflare в отговора')
    except Exception as ex:
        log(f'БТА недостъпна: {ex}')
        open('data/bta_log.txt','w',encoding='utf-8').write('\n'.join(LOG)); return

    # 2) търсене на статии
    found = {}
    for p in range(1, 4):
        try:
            code, body = get(search_bta(p))
        except Exception as ex:
            log(f'търсене стр.{p} FAIL: {ex}'); continue
        links = set(re.findall(r'href="(/bg/news/[^"]+)"', body))
        log(f'търсене стр.{p}: {len(links)} връзки')
        for href in links:
            if not re.search(r'denonoshtie|katastrof', href, re.I): continue
            url = 'https://www.bta.bg' + href
            if url in found: continue
            try:
                c2, b2 = get(url)
            except Exception as ex:
                log(f'  статия FAIL {href[:60]}: {ex}'); continue
            txt = re.sub(r'<[^>]+>', ' ', b2)
            txt = re.sub(r'&nbsp;', ' ', txt)
            md = re.search(r'(\d{4}-\d{2}-\d{2})', b2)
            rec = parse(txt)
            if not rec.get('total'): continue
            rec['url'] = url
            rec['date'] = md.group(1) if md else None
            found[url] = rec
            log(f"  ✓ {rec.get('date')} нац={rec.get('total')} загин={rec.get('dead')} "
                f"ранени={rec.get('injured')} | София леки={rec.get('sofia_light')} "
                f"тежки={rec.get('sofia_serious')} ранени={rec.get('sofia_injured')}")

    log(f'общо разпознати статии: {len(found)}')
    days = {}
    for rec in found.values():
        if rec.get('date'): days[rec['date']] = rec
    with open('data/bta_daily.json', 'w', encoding='utf-8') as f:
        json.dump({'generated': datetime.datetime.utcnow().isoformat()+'Z',
                   'days': [days[d] for d in sorted(days)]}, f, ensure_ascii=False, indent=1)
    log(f'записани {len(days)} дни в data/bta_daily.json')
    open('data/bta_log.txt','w',encoding='utf-8').write('\n'.join(LOG))

if __name__ == '__main__':
    main()
