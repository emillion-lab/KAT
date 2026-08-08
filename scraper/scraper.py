#!/usr/bin/env python3
"""МВР ArcGIS scraper — v2, откри истинския сървър: gis.mvr.bg.

Първото пускане намери services?f=json на gis.mvr.bg с папка MVR_Incident —
точно там трябва да е слоят с ПТП. Тази версия слиза в папката и намира
конкретната услуга и слой номер, вместо да гадае.
"""
import json, os, re, sys, csv, datetime, urllib.request, urllib.parse

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept': 'application/json,*/*'}
LOG = []

def log(*a):
    line = ' '.join(str(x) for x in a)
    print(line, flush=True)
    LOG.append(line)

def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.getcode(), r.headers.get('Content-Type', ''), r.read().decode('utf-8', 'replace')

ROOT = "https://gis.mvr.bg/arcgis/rest/services"

def list_folder(path=""):
    url = f"{ROOT}/{path}?f=json".replace("//", "/").replace("https:/", "https://")
    code, ct, body = get(url)
    return json.loads(body)

def walk_all():
    """Обхожда всички папки, връща списък (пълен_път, тип) за всяка услуга."""
    services = []
    root = list_folder("")
    log("папки в корена:", root.get('folders'))
    folders = root.get('folders', [])
    for fo in folders:
        try:
            j = list_folder(fo)
        except Exception as ex:
            log(f"  папка {fo} FAIL: {ex}")
            continue
        svcs = j.get('services', [])
        log(f"  папка {fo}: {len(svcs)} услуги")
        for s in svcs:
            services.append((f"{fo}/{s['name'].split('/')[-1]}", s['type']))
        for sub in j.get('folders', []):
            try:
                j2 = list_folder(f"{fo}/{sub}")
                for s in j2.get('services', []):
                    services.append((f"{fo}/{sub}/{s['name'].split('/')[-1]}", s['type']))
                log(f"    подпапка {fo}/{sub}: {len(j2.get('services', []))} услуги")
            except Exception as ex:
                log(f"    подпапка {fo}/{sub} FAIL: {ex}")
    return services

def inspect_service(name, typ):
    url = f"{ROOT}/{name}/{typ}?f=json"
    try:
        code, ct, body = get(url)
        j = json.loads(body)
    except Exception as ex:
        log(f"    inspect FAIL {name} -> {ex}")
        return []
    layers = j.get('layers', [])
    out = []
    for lyr in layers:
        out.append((f"{ROOT}/{name}/{typ}/{lyr['id']}", lyr.get('name', '')))
    return out

DATE_HINTS = ('date', 'dat', 'datum', 'time', 'дата')
DEAD_HINTS = ('dead', 'kill', 'fatal', 'zagin', 'загин')
INJ_HINTS  = ('inj', 'ranen', 'wound', 'ранен', 'постр')
AREA_HINTS = ('obl', 'area', 'region', 'district', 'област', 'oblast', 'grad', 'city')

def pick(fields, hints):
    for f in fields:
        lf = f.lower()
        if any(h in lf for h in hints):
            return f
    return None

def probe_layer(layer_url, layer_name):
    try:
        code, ct, body = get(layer_url + '?f=json')
        j = json.loads(body)
    except Exception as ex:
        log(f"    layer probe FAIL {layer_url} -> {ex}")
        return None
    fields = [f.get('name') for f in j.get('fields', [])]
    if not fields:
        return None
    hits = sum(1 for hint_group in (DATE_HINTS, DEAD_HINTS, INJ_HINTS) if pick(fields, hint_group))
    log(f"    слой {layer_name}: {layer_url}")
    log(f"      полета: {fields[:30]}")
    log(f"      съвпадения по ключови думи: {hits}/3")
    return {'url': layer_url, 'name': layer_name, 'fields': fields, 'hits': hits}

def to_date(v):
    if v is None: return None
    if isinstance(v, (int, float)):
        try: return datetime.datetime.utcfromtimestamp(v/1000).date().isoformat()
        except Exception: return None
    s = str(v)[:10]
    for f in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
        try: return datetime.datetime.strptime(s, f).date().isoformat()
        except ValueError: pass
    return None

def fetch_features(layer):
    url = layer['url'] + '/query?' + urllib.parse.urlencode({
        'where': '1=1', 'outFields': '*', 'returnGeometry': 'false',
        'f': 'json', 'resultRecordCount': 4000})
    code, ct, body = get(url, timeout=180)
    j = json.loads(body)
    if 'error' in j:
        log(f"    query error: {j['error']}")
        return []
    feats = j.get('features', [])
    log(f"    изтеглени записи: {len(feats)}")
    return feats

def normalize(feats, layer):
    fields = layer['fields']
    fd, fdd, fi, fa = pick(fields, DATE_HINTS), pick(fields, DEAD_HINTS), pick(fields, INJ_HINTS), pick(fields, AREA_HINTS)
    log(f"    полета: дата={fd} загинали={fdd} ранени={fi} област={fa}")
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
            rec['sofia_total'] += 1; rec['sofia_dead'] += dead; rec['sofia_injured'] += inj
    return dict(sorted(days.items()))

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
    services = walk_all()
    log(f"общо услуги: {len(services)}")
    candidates = []
    for name, typ in services:
        low = name.lower()
        # приоритет на услуги, чието име подсказва ПТП/инциденти
        score = sum(w in low for w in ('incident', 'ptp', 'accident', 'катастроф', 'zagin'))
        candidates.append((score, name, typ))
    candidates.sort(key=lambda x: -x[0])
    log("топ кандидати по име:")
    for score, name, typ in candidates[:10]:
        log(f"  [{score}] {name} ({typ})")

    best = None
    for score, name, typ in candidates[:15]:
        layers = inspect_service(name, typ)
        for lurl, lname in layers:
            probed = probe_layer(lurl, f"{name}/{lname}")
            if probed and probed['hits'] >= 2:
                best = probed
                break
        if best:
            break

    if not best:
        log("НЯМА СЛОЙ С ДОСТАТЪЧНО СЪВПАДЕНИЯ — виж пълния списък по-горе")
    else:
        try:
            days = normalize(fetch_features(best), best)
            if days: write_all(days, best)
            else: log("слоят е намерен, но 0 дни се разпознаха — виж имената на полетата")
        except Exception as ex:
            log(f"теглене се провали: {ex}")

    os.makedirs('data', exist_ok=True)
    with open('data/discovery.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(LOG))

if __name__ == '__main__':
    main()
