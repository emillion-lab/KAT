"""По-дълбоко страниране: справката потъва бързо сред новините на БТА.

Диагностиката показа, че парсването е наред — известната статия се чете
изрядно, включително софийското изречение с числата. Липсва само намирането:
БТА публикува стотици новини на ден, ежедневната справка излиза около 11:00
и след няколко часа вече не е сред последните 53 статии, а RSS пази 21.

Затова: 25 страници вместо 6, и двата варианта на параметъра, плюс рубриките
"България" и "Всички". При час на пускане това дава запас от няколко дни.
"""
import io

src = io.open('scraper/bta.py', encoding='utf-8').read()
count = 0

def rep(old, new):
    global src, count
    c = src.count(old)
    assert c == 1, 'MARKER x%d: %r' % (c, old[:70])
    src = src.replace(old, new); count += 1

rep("""    for sec in ['bulgaria', 'all']:
        for p in range(1, 7):
            for q in ('page', 'p'):
                try:
                    html = get(f'https://www.bta.bg/bg/news/{sec}?{q}={p}')
                    urls |= set('https://www.bta.bg' + u for u in
                        re.findall(r'href="(/bg/news/[a-z]+/\\d{6,8}-[a-z0-9\\-]+)"', html))
                except Exception:
                    pass""",
"""    for sec in ['bulgaria', 'all']:
        for p in range(1, 26):
            before = len(urls)
            for q in ('page', 'p'):
                try:
                    html = get(f'https://www.bta.bg/bg/news/{sec}?{q}={p}')
                    urls |= set('https://www.bta.bg' + u for u in
                        re.findall(r'href="(/bg/news/[a-z]+/\\d{6,8}-[a-z0-9\\-]+)"', html))
                except Exception:
                    pass
            if len(urls) == before:      # страницирането свърши
                break""")

# новите статии са с най-голям номер — проверяваме ги първи, но не спираме рано
rep("""    checked = hit = 0
    for u in candidates():""",
"""    checked = hit = 0
    def key(u):
        m = re.search(r'/(\\d{6,8})-', u)
        return int(m.group(1)) if m else 0
    for u in sorted(candidates(), key=key, reverse=True):""")

io.open('scraper/bta.py', 'w', encoding='utf-8').write(src)
print('PATCHED %d blocks OK' % count)
