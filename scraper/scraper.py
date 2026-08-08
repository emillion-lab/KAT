#!/usr/bin/env python3
"""МВР ArcGIS scraper — открива endpoint-а, тегли, нормализира, архивира.

Ключовото различие спрямо стария скрейп: не се четат новинарски заглавия.
Оттам идваха 8 от 30 дни покритие за ПТП и стойности като "3" (заглавие за
една област, взето за национално число). ArcGIS слоят дава инцидент по
инцидент, с дата, координати и тежест — тоест София се отделя без да се гадае.

Изход:
  data/latest.json               последното състояние + агрегати за деня
  data/history/YYYY/MM/DD.json   дневен архив, само при промяна
  data/daily.csv                 дата, ПТП, загинали, ранени (нац. + София)
  data/discovery.txt             какво е намерено при търсенето на endpoint

Скриптът НЕ се проваля тихо: ако слоят не се намери, discovery.txt казва
какво точно е било пробвано и с какъв отговор.
"""
import json, os, re, sys, csv, datetime, urllib.request, urllib.parse, urllib.error

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept': 'application/json,text/html,*/*',
      'Accept-Language': 'bg-BG,bg;q=0.9'}
LOG = []

def log(*a):
    line = ' '.join(str(x) for x in a)
    print(line, flush=True)
    LOG.append(line)

def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.getcode(), r.headers.get('Content-Type', ''), r.read().decode('utf-8', 'replace')

# ─────────────────────────── 1. откриване на слоя ───────────────────────────
# Страници, в чийто HTML/JS може да стои адресът на ArcGIS услугата.
SEEDS = [
    "https://www.mvr.bg/ptp",
    "https://ptp.mvr.bg/",
    "https://www.mvr.bg/gdnp",
]
# Пряко пробвани адреси, ако в HTML няма нищо.
DIRECT = [
    "https://services.arcgis.com/lJXqXsx2f8xnZWDL/arcgis/rest/services?f=json",
    "https://services8.arcgis.com/rest/services?f=json",
    "https://gis.mvr.bg/arcgis/rest/services?f=json",
    "https://ptp.mvr.bg/arcgis/rest/services?f=json",
]

ARC_RE = re.compile(
    r'https?://[A-Za-z0-9._\-]+/(?:arcgis|server)/rest/services/[A-Za-z0-9._%\-/]+'
    r'/(?:Feature|Map)Server(?:/\d+)?', re.I)
ANY_ARC_RE = re.compile(r'https?://[A-Za-z0-9._\-]*arcgis[A-Za-z0-9._\-]*/[^\s"\'<>]{0,200}', re.I)

def discover():
    found = set()
    for u in SEEDS:
        try:
            code, ct, body = get(u)
            log(f"seed {code} {u} ({len(body)} chars)")
            for m in ARC_RE.finditer(body):
                found.add(m.group(0))
            for m in ANY_ARC_RE.finditer(body):
                found.add(m.group(0))
            # ArcGIS dashboards често се зареждат в iframe
            for m in re.finditer(r'<iframe[^>]+src="([^"]+)"', body, re.I):
                src = m.group(1)
                if src.startswith('//'): src = 'https:' + src
                if src.startswith('/'):  src = '/'.join(u.split('/')[:3]) + src
                if not src.startswith('http'): continue
                try:
                    c2, _, b2 = get(src)
                    log(f"  iframe {c2} {src[:90]}")
                    for m2 in ARC_RE.finditer(b2): found.add(m2.group(0))
                    for m2 in ANY_ARC_RE.finditer(b2): found.add(m2.group(0))
                except Exception as ex:
                    log(f"  iframe FAIL {src[:70]} -> {ex}")
        except Exception as ex:
            log(f"seed FAIL {u} -> {ex}")
    log(f"кандидати от HTML: {len(found)}")
    for f in sorted(found):
        log("  ", f)
    return sorted(found)

def probe_layer(url):
    """Проверява дали адресът е FeatureServer слой с полезни полета."""
    base = url.split('?')[0].rstrip('/')
    if not re.search(r'/(Feature|Map)Server(/\d+)?$', base, re.I):
        return None
    if not re.search(r'/\d+$', base):
        base += '/0'
    try:
        code, ct, body = get(base + '?f=json')
        j = json.loads(body)
    except Exception as ex:
        log(f"  probe FAIL {base} -> {ex}")
        return None
    fields = [f.get('name') for f in j.get('fields', [])]
    if not fields:
        return None
    log(f"  СЛОЙ {base}")
    log(f"    име: {j.get('name')}  записи: {j.get('maxRecordCount')}")
    log(f"    полета: {fields[:25]}")
    return {'url': base, 'name': j.get('name'), 'fields': fields}

# ─────────────────────────── 2. теглене и нормализиране ─────────────────────
DATE_HINTS  = ('date', 'dat', 'datum', 'time', 'vreme', 'дата')
DEAD_HINTS  = ('dead', 'kill', 'fatal', 'zagin', 'загин')
INJ_HINTS   = ('inj', 'ranen', 'wound', 'ранен', 'постр')
AREA_HINTS  = ('obl', 'area', 'region', 'district', 'област', 'oblast')

def pick(fields, hints):
    for f in fields:
        lf = f.lower()
        if any(h in lf for h in hints):
            return f
    return None

def fetch_features(layer):
    url = layer['url'] + '/query?' + urllib.parse.urlencode({
        'where': '1=1', 'outFields': '*', 'returnGeometry': 'true',
        'f': 'json', 'resultRecordCount': 4000})
    code, ct, body = get(url, timeout=180)
    j = json.loads(body)
    feats = j.get('features', [])
    log(f"изтеглени записи: {len(feats)}")
    return feats

def to_date(v):
    if v is None: return None
    if isinstance(v, (int, float)):           # ArcGIS epoch ms
        try: return datetime.datetime.utcfromtimestamp(v/1000).date().isoformat()
        except Exception: return None
    s = str(v)[:10]
    for f in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
        try: return datetime.datetime.strptime(s, f).date().isoformat()
        except ValueError: pass
    return None

def normalize(feats, layer):
    fields = layer['fields']
    fd  = pick(fields, DATE_HINTS)
    fdd = pick(fields, DEAD_HINTS)
    fi  = pick(fields, INJ_HINTS)
    fa  = pick(fields, AREA_HINTS)
    log(f"полета: дата={fd} загинали={fdd} ранени={fi} област={fa}")
    days = {}
    for ft in feats:
        at = ft.get('attributes', {})
        d = to_date(at.get(fd)) if fd else None
        if not d: continue
        rec = days.setdefault(d, {'date': d, 'total': 0, 'dead': 0, 'injured': 0,
                                  'sofia_total': 0, 'sofia_dead': 0, 'sofia_injured': 0})
        dead = int(at.get(fdd) or 0) if fdd else 0
        inj  = int(at.get(fi)  or 0) if fi  else 0
        rec['total'] += 1; rec['dead'] += dead; rec['injured'] += inj
        area = str(at.get(fa) or '') if fa else ''
        if 'софия' in area.lower() or 'sofia' in area.lower():
            rec['sofia_total'] += 1
            rec['sofia_dead'] += dead
            rec['sofia_injured'] += inj
    return dict(sorted(days.items()))

# ─────────────────────────── 3. запис ───────────────────────────────────────
def write_all(days, layer):
    os.makedirs('data/history', exist_ok=True)
    with open('data/latest.json', 'w', encoding='utf-8') as f:
        json.dump({'generated': datetime.datetime.utcnow().isoformat()+'Z',
                   'source': layer['url'], 'days': list(days.values())},
                  f, ensure_ascii=False, indent=1)
    for d, rec in days.items():
        y, m, dd = d.split('-')
        p = f'data/history/{y}/{m}'
        os.makedirs(p, exist_ok=True)
        fn = f'{p}/{dd}.json'
        new = json.dumps(rec, ensure_ascii=False, sort_keys=True)
        if os.path.exists(fn) and open(fn, encoding='utf-8').read() == new:
            continue
        open(fn, 'w', encoding='utf-8').write(new)
    with open('data/daily.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['date','total','dead','injured','sofia_total','sofia_dead','sofia_injured'])
        for d, r in days.items():
            w.writerow([d, r['total'], r['dead'], r['injured'],
                        r['sofia_total'], r['sofia_dead'], r['sofia_injured']])
    log(f"записани {len(days)} дни")

def main():
    layer = None
    for cand in discover():
        layer = probe_layer(cand)
        if layer: break
    if not layer:
        log("HTML не даде слой — пробвам преки адреси")
        for u in DIRECT:
            try:
                code, ct, body = get(u)
                log(f"direct {code} {u}")
                log("  " + body[:400])
            except Exception as ex:
                log(f"direct FAIL {u} -> {ex}")
    if layer:
        try:
            days = normalize(fetch_features(layer), layer)
            if days: write_all(days, layer)
            else: log("НЯМА разпознати дати — виж имената на полетата по-горе")
        except Exception as ex:
            log(f"теглене се провали: {ex}")
    else:
        log("СЛОЯТ НЕ Е ОТКРИТ — виж списъка с кандидати по-горе")

    os.makedirs('data', exist_ok=True)
    with open('data/discovery.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(LOG))

if __name__ == '__main__':
    main()
