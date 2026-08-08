#!/usr/bin/env python3
"""БТА — втора диагностика: RSS и страниране на рубриката.

Първата показа: търсачката на БТА е клиентска (JavaScript). Сървърът връща
едни и същи 174 навигационни връзки за всяка заявка, а "изминалото денонощие"
се среща 0 пъти в HTML-а. Значи през search не става.

Но адресите на статиите са четими и последователни:
  /bg/news/bulgaria/1151877-prez-izminaloto-denonoshtie-...
Значи има два други пътя: RSS канал или страниране на рубриката.
Този скрипт проверява кой от двата работи.
"""
import re, os, urllib.request, urllib.parse

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept-Language': 'bg-BG,bg;q=0.9'}
OUT = []
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); OUT.append(s)

def get(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.getcode(), r.read().decode('utf-8', 'replace')

RSS = [
    'https://www.bta.bg/bg/rss',
    'https://www.bta.bg/rss',
    'https://www.bta.bg/bg/feed',
    'https://www.bta.bg/bg/rss/bulgaria',
    'https://www.bta.bg/bg/news/bulgaria/rss',
    'https://www.bta.bg/bg/sitemap.xml',
    'https://www.bta.bg/sitemap.xml',
]

PAGES = [
    'https://www.bta.bg/bg/news/bulgaria?page=2',
    'https://www.bta.bg/bg/news/bulgaria/page/2',
    'https://www.bta.bg/bg/news/bulgaria?p=2',
    'https://www.bta.bg/bg/news/all?page=2',
]

# известен работещ адрес от по-ранно търсене — за проверка на формата на статия
KNOWN = 'https://www.bta.bg/bg/news/bulgaria/1151877-prez-izminaloto-denonoshtie-pri-23-katastrofi-v-stranata-sa-zaginali-dvama-a-28'

def main():
    os.makedirs('data', exist_ok=True)

    log('═══ RSS / SITEMAP ═══')
    for u in RSS:
        try:
            code, body = get(u)
            n_items = len(re.findall(r'<item>|<url>', body))
            log(f'  {code}  {u}  ({len(body)} знака, {n_items} записа)')
            if n_items:
                for m in re.findall(r'<loc>([^<]+)</loc>|<link>([^<]+)</link>', body)[:8]:
                    log('      ' + (m[0] or m[1])[:130])
        except Exception as ex:
            log(f'  FAIL {u} -> {str(ex)[:60]}')

    log('')
    log('═══ СТРАНИРАНЕ НА РУБРИКАТА ═══')
    base_ids = None
    for u in PAGES:
        try:
            code, body = get(u)
            ids = set(re.findall(r'/bg/news/[a-z]+/(\d{6,8})-', body))
            log(f'  {code}  {u}  ({len(ids)} статии)')
            if base_ids is None:
                base_ids = ids
            elif ids and ids != base_ids:
                log('      ← РАЗЛИЧНИ от предишната страница: страницирането РАБОТИ')
        except Exception as ex:
            log(f'  FAIL {u} -> {str(ex)[:60]}')

    log('')
    log('═══ ПРОВЕРКА НА ИЗВЕСТНА СТАТИЯ ═══')
    try:
        code, body = get(KNOWN)
        plain = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', body))
        i = plain.lower().find('изминалото денонощие')
        log(f'  HTTP {code}, "изминалото денонощие" на позиция {i}')
        if i > 0:
            log('  ТЕКСТ: ' + plain[max(0, i-120): i+800])
        # дата в мета-таговете
        for pat in [r'"datePublished"\s*:\s*"([^"]+)"',
                    r'property="article:published_time"\s+content="([^"]+)"',
                    r'<time[^>]+datetime="([^"]+)"']:
            m = re.search(pat, body)
            if m: log(f'  ДАТА ({pat[:24]}): {m.group(1)}')
    except Exception as ex:
        log(f'  FAIL -> {ex}')

    log('')
    log('═══ ДНЕШНАТА СПРАВКА ПО ID ═══')
    # статиите са с последователни ID; вземаме най-голямото видяно и слизаме
    try:
        code, body = get('https://www.bta.bg/bg/news/bulgaria')
        ids = sorted({int(x) for x in re.findall(r'/bg/news/[a-z]+/(\d{6,8})-', body)}, reverse=True)
        log(f'  най-нови ID в рубриката: {ids[:5]}')
        found = 0
        for aid in ids[:60]:
            slug_urls = re.findall(rf'/bg/news/[a-z]+/{aid}-[a-z0-9\-]+', body)
            for s in set(slug_urls):
                if re.search(r'denonosht|katastrof|ptp|ranen', s, re.I):
                    log('  ► ' + s[:140]); found += 1
        log(f'  съвпадения в текущата рубрика: {found}')
    except Exception as ex:
        log(f'  FAIL -> {ex}')

    open('data/bta_probe2.txt', 'w', encoding='utf-8').write('\n'.join(OUT))

if __name__ == '__main__':
    main()
