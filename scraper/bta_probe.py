#!/usr/bin/env python3
"""Диагностика на БТА: какви адреси реално връща търсенето.

Първото пускане показа: сайтът е достъпен (HTTP 200, без Cloudflare), но и
трите страници дадоха едни и същи 174 връзки — значи ?page= не работи — и
нито един адрес не съдържа 'denonoshtie' или 'katastrof'.

Този скрипт не парсва нищо. Само записва какво вижда, за да се види дали
търсачката изобщо работи и как изглеждат адресите на нужните статии.
"""
import re, json, os, urllib.request, urllib.parse, collections

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept-Language': 'bg-BG,bg;q=0.9'}
OUT = []
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); OUT.append(s)

def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.getcode(), r.read().decode('utf-8', 'replace')

CANDIDATES = [
    ('търсене v1', 'https://www.bta.bg/bg/search?query=' + urllib.parse.quote('денонощие катастрофи')),
    ('търсене v2', 'https://www.bta.bg/bg/search?q='     + urllib.parse.quote('денонощие катастрофи')),
    ('търсене v3', 'https://www.bta.bg/bg/search/'       + urllib.parse.quote('денонощие катастрофи')),
    ('рубрика България', 'https://www.bta.bg/bg/news/bulgaria'),
    ('начална', 'https://www.bta.bg/bg'),
]

def main():
    os.makedirs('data', exist_ok=True)
    all_links = collections.Counter()

    for name, url in CANDIDATES:
        try:
            code, body = get(url)
        except Exception as ex:
            log(f'{name}: FAIL {ex}'); continue
        links = re.findall(r'href="(/bg/news/[^"#?]+)"', body)
        uniq = sorted(set(links))
        log(f'{name}: HTTP {code}, {len(body)} знака, {len(uniq)} уникални /bg/news/ връзки')
        for l in uniq: all_links[l] += 1
        # показваме първите 12 адреса, за да се види формата им
        for l in uniq[:12]:
            log('    ' + l[:120])
        # има ли изобщо думата в текста на страницата
        plain = re.sub(r'<[^>]+>', ' ', body)
        hits = len(re.findall(r'изминалото денонощие', plain, re.I))
        log(f'    срещания на "изминалото денонощие" в текста: {hits}')
        log('')

    # кои адреси приличат на ежедневната справка
    log('=== адреси, съдържащи ключови думи ===')
    pat = re.compile(r'denonosht|katastrof|patn|ptp|ranen|zagin', re.I)
    hits = [l for l in all_links if pat.search(l)]
    log(f'намерени: {len(hits)}')
    for l in hits[:40]:
        log('  ' + l[:140])

    # ако има поне един — теглим го и записваме суровия текст за проверка
    if hits:
        u = 'https://www.bta.bg' + hits[0]
        try:
            code, body = get(u)
            plain = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', body))
            i = plain.lower().find('денонощие')
            log('')
            log('=== примерен текст от ' + u[:100])
            log(plain[max(0, i-200): i+900])
        except Exception as ex:
            log(f'примерна статия FAIL: {ex}')

    open('data/bta_probe.txt', 'w', encoding='utf-8').write('\n'.join(OUT))

if __name__ == '__main__':
    main()
