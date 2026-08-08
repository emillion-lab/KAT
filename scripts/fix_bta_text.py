"""Поправка на извличането на текста в БТА scraper.

v3 прегледа 131 статии и не намери нито една с ежедневната справка, макар
диагностиката преди това да я откри в известна статия на позиция 13.
Причината: body_text() режеше по <article> / meta description и пропускаше
същинското тяло, така че фразата изобщо не стигаше до проверката.

Поправката работи върху целия текст, но избягва два капана:

1. Фразата се среща поне два пъти — веднъж в <title> и веднъж в тялото.
   Заглавието е съкратено ("при 23 катастрофи ... са загинали двама"), а
   тялото е пълно. Затова се взима ПОСЛЕДНОТО срещане, не първото.

2. Между заглавието и тялото стои менюто на БТА, което изброява всички
   области: "Благоевград Бургас Варна ... София София - област ...".
   Ако не се изреже, търсенето на "В София" хваща менюто вместо изречението
   с числата. Менюто се маха по характерния си край ("Ямбол").
"""
import io

src = io.open('scraper/bta.py', encoding='utf-8').read()
count = 0

def rep(old, new):
    global src, count
    c = src.count(old)
    assert c == 1, 'MARKER x%d: %r' % (c, old[:80])
    src = src.replace(old, new); count += 1

rep('''def body_text(html):
    m = re.search(r'<article[\\s\\S]{0,200000}?</article>', html, re.I)
    chunk = m.group(0) if m else ''
    if len(chunk) < 200:
        m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]{60,})"', html, re.I)
        chunk = m.group(1) if m else ''
    if len(chunk) < 200:
        m = re.search(r'(?:itemprop="articleBody"|class="[^"]*body[^"]*")[\\s\\S]{0,120000}?</div>', html, re.I)
        chunk = m.group(0) if m else html
    chunk = re.sub(r'<(script|style)[\\s\\S]*?</\\1>', ' ', chunk, flags=re.I)
    return re.sub(r'\\s+', ' ', re.sub(r'<[^>]+>', ' ', chunk)).strip()''',
'''MENU_END = re.compile(r'Ямбол[^А-Яа-я]{0,80}', re.I)

def plain(html):
    h = re.sub(r'<(script|style)[\\s\\S]*?</\\1>', ' ', html, flags=re.I)
    return re.sub(r'\\s+', ' ', re.sub(r'<[^>]+>', ' ', h)).strip()

def body_text(html):
    """Тялото на статията, без заглавието и без менюто с областите.

    Фразата се среща и в <title>, и в тялото. Заглавието е съкратено, тялото
    е пълно — затова взимаме ПОСЛЕДНОТО срещане. Менюто на БТА стои между
    двете и изброява всички области, включително София; ако не се изреже,
    "В София" се хваща от менюто вместо от изречението с числата."""
    t = plain(html)
    # изрязваме менюто: то свършва на последната област по азбучен ред
    m = list(MENU_END.finditer(t[:20000]))
    if m:
        t = t[m[-1].end():]
    occ = [x.start() for x in re.finditer(r'(?:изминалото|последното)\\s+денонощие', t, re.I)]
    if not occ:
        return t[:4000]
    start = max(0, occ[-1] - 200)
    return t[start:start + 2000]''')

rep("""        txt = body_text(html)
        if 'изминалото денонощие' not in txt.lower() and 'последното денонощие' not in txt.lower():
            continue""",
"""        full = plain(html)
        if not re.search(r'(?:изминалото|последното)\\s+денонощие', full, re.I):
            continue
        txt = body_text(html)""")

io.open('scraper/bta.py', 'w', encoding='utf-8').write(src)
print('PATCHED %d blocks OK' % count)
