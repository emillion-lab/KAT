#!/usr/bin/env python3
"""Диагностика върху ИЗВЕСТНА статия — върви автоматично преди скрейпа.

Три пускания подред дадоха "129 статии, 0 с ежедневна справка", макар по-ранна
проба да намери фразата в конкретна статия. Значи или фразата не стига до
проверката, или тези 129 статии просто не съдържат справката.

Този скрипт не гадае: тегли известен адрес, за който сме сигурни, и записва
какво точно вижда — дължина, къде е фразата, и самия текст около нея. Пише се
при всяко пускане, за да не чакаме ръчно потвърждение.
"""
import re, os, json, datetime, urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept-Language': 'bg-BG,bg;q=0.9'}
OUT = []
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); OUT.append(s)

def get(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')

def plain(html):
    h = re.sub(r'<(script|style)[\s\S]*?</\1>', ' ', html, flags=re.I)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h)).strip()

KNOWN = ('https://www.bta.bg/bg/news/bulgaria/1151877-prez-izminaloto-'
         'denonoshtie-pri-23-katastrofi-v-stranata-sa-zaginali-dvama-a-28')

def main():
    os.makedirs('data', exist_ok=True)

    log('═══ 1. ИЗВЕСТНА СТАТИЯ ═══')
    try:
        html = get(KNOWN)
        t = plain(html)
        log(f'  HTTP ok, HTML {len(html)} знака, чист текст {len(t)} знака')
        occ = [m.start() for m in re.finditer(r'(?:изминалото|последното)\s+денонощие', t, re.I)]
        log(f'  срещания на фразата: {occ}')
        for i in occ[:4]:
            log(f'    @{i}: ...{t[max(0,i-90):i+320]}...')
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
        log(f'  datePublished: {m.group(1) if m else "НЯМА"}')
    except Exception as ex:
        log(f'  FAIL: {ex}')

    log('')
    log('═══ 2. КАКВО ИМА В RSS ПРАВО СЕГА ═══')
    try:
        rss = get('https://www.bta.bg/bg/news/bulgaria/rss')
        titles = re.findall(r'<title>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</title>', rss)
        links  = re.findall(r'<link>\s*(https://www\.bta\.bg/bg/news/[^<\s]+)', rss)
        log(f'  заглавия: {len(titles)}, връзки: {len(links)}')
        for tt in titles[1:12]:
            log('    · ' + tt[:110])
    except Exception as ex:
        log(f'  RSS FAIL: {ex}')

    log('')
    log('═══ 3. ТЪРСЕНЕ НА СПРАВКАТА В ПОСЛЕДНИТЕ СТАТИИ ═══')
    urls = set()
    try:
        rss = get('https://www.bta.bg/bg/news/bulgaria/rss')
        urls |= set(re.findall(r'<link>\s*(https://www\.bta\.bg/bg/news/[^<\s]+)', rss))
    except Exception: pass
    for p in range(1, 4):
        try:
            h = get(f'https://www.bta.bg/bg/news/bulgaria?page={p}')
            urls |= set('https://www.bta.bg' + u for u in
                        re.findall(r'href="(/bg/news/[a-z]+/\d{6,8}-[a-z0-9\-]+)"', h))
        except Exception: pass
    log(f'  кандидати: {len(urls)}')
    found = 0
    for u in sorted(urls, reverse=True)[:60]:
        try: t = plain(get(u))
        except Exception: continue
        if re.search(r'(?:изминалото|последното)\s+денонощие', t, re.I):
            found += 1
            i = re.search(r'(?:изминалото|последното)\s+денонощие', t, re.I).start()
            log(f'  ✓ {u[-60:]}')
            log(f'      {t[max(0,i-80):i+260]}')
            if found >= 3: break
    log(f'  намерени: {found}')
    if not found:
        log('  ЗАКЛЮЧЕНИЕ: справката не е сред последните статии в рубрика "България".')
        log('  Възможно е БТА да я публикува в друга рубрика или да е спряла.')

    open('data/bta_diag.txt', 'w', encoding='utf-8').write('\n'.join(OUT))

if __name__ == '__main__':
    main()
