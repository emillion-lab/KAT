#!/usr/bin/env python3
"""
Разузнавач за сурови данни за ПТП.

Обхожда известните български и европейски портали за отворени данни,
докладва какво е намерил и сваля годните набори. Нормализира до дневни
редове и ги слива в data/daily_archive.json.

Употреба:
    python3 tools_ptp_harvester.py --scan          само търси и докладва
    python3 tools_ptp_harvester.py --download      сваля намереното
    python3 tools_ptp_harvester.py --merge FILE    слива готов файл в архива
"""
import json, sys, os, re, io, csv, datetime, argparse
import urllib.request, urllib.parse

UA = {'User-Agent': 'kat-ptp-harvester/1.0 (road-safety research)'}
OUT_DIR = 'data/raw'
REPORT = 'data/harvest-report.md'

# ── Източници по приоритет ────────────────────────────────────────
SOURCES = [
    {
        'id': 'egov_search',
        'name': 'Портал за отворени данни (data.egov.bg)',
        'kind': 'api',
        'url': 'https://data.egov.bg/api/getDataSetList',
        'note': 'Национален портал — тук се публикуват наборите на МВР и НСИ',
    },
    {
        'id': 'egov_search_ptp',
        'name': 'data.egov.bg — търсене „пътнотранспортни"',
        'kind': 'api',
        'url': 'https://data.egov.bg/api/getResourceView?resource_uri=',
        'note': 'Изисква URI от списъка по-горе',
    },
    {
        'id': 'opendata_eu',
        'name': 'EU Open Data Portal — CARE road accidents',
        'kind': 'api',
        'url': 'https://data.europa.eu/api/hub/search/search?q=road%20accidents%20Bulgaria&limit=20',
        'note': 'Европейската база CARE съдържа български ПТП по години',
    },
    {
        'id': 'nsi',
        'name': 'НСИ — транспортни произшествия',
        'kind': 'page',
        'url': 'https://www.nsi.bg/bg/content/1900/пътнотранспортни-произшествия',
        'note': 'Годишни таблици в XLS',
    },
]

KEYWORDS = ['птп', 'пътнотранспортн', 'пътно-транспортн', 'катастроф',
            'road accident', 'traffic accident', 'пътна безопасност',
            'загинали', 'ранени']


def fetch(url, timeout=25, binary=False):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            return data if binary else data.decode('utf-8', errors='replace')
    except Exception as e:
        return None


def scan_egov():
    """Обхожда националния портал и връща наборите, свързани с ПТП."""
    found = []
    endpoints = [
        "https://data.egov.bg/api/getDataSetList",
        "https://data.egov.bg/api/v1/datasets",
        "https://data.egov.bg/api/getOrganisationDataSets",
        "https://data.egov.bg/data/search?q=%D0%9F%D0%A2%D0%9F&format=json",
    ]
    raw = None
    used = None
    for ep in endpoints:
        raw = fetch(ep)
        if raw and raw.strip()[:1] in ("{", "["):
            used = ep
            break
    if not raw:
        return found, "нито един от %d известни адреса не отговаря" % len(endpoints)
    try:
        data = json.loads(raw)
    except Exception:
        return found, "отговорът от %s не е валиден JSON" % used

    items = data if isinstance(data, list) else data.get('data', data.get('result', []))
    if not isinstance(items, list):
        return found, f'неочакван формат: {type(items).__name__}'

    for it in items:
        if not isinstance(it, dict):
            continue
        blob = json.dumps(it, ensure_ascii=False).lower()
        if any(k in blob for k in KEYWORDS):
            found.append({
                'name': it.get('name') or it.get('title') or '?',
                'uri': it.get('uri') or it.get('id') or '',
                'org': it.get('org_name') or it.get('organisation') or '',
            })
    return found, "прегледани %d набора през %s" % (len(items), used)


def scan_eu():
    raw = fetch(SOURCES[2]['url'])
    if not raw:
        return [], 'няма отговор'
    try:
        d = json.loads(raw)
    except Exception:
        return [], 'невалиден JSON'
    res = d.get('result', {}).get('results', []) if isinstance(d, dict) else []
    out = []
    for r in res[:20]:
        title = r.get('title', {})
        if isinstance(title, dict):
            title = title.get('en') or list(title.values())[0] if title else '?'
        out.append({'name': str(title)[:90], 'uri': r.get('id', ''), 'org': 'EU'})
    return out, f'върнати {len(res)} резултата'


def cmd_scan():
    lines = ['# Разузнаване за сурови данни за ПТП', '',
             f'Изпълнено: {datetime.datetime.now(datetime.timezone.utc).isoformat()}', '']

    egov, note = scan_egov()
    lines.append(f'## data.egov.bg — {note}')
    if egov:
        for e in egov[:40]:
            lines.append(f"- **{e['name']}**")
            if e['org']: lines.append(f"  - организация: {e['org']}")
            if e['uri']: lines.append(f"  - uri: `{e['uri']}`")
    else:
        lines.append('- нищо намерено по ключовите думи')
    lines.append('')

    eu, note2 = scan_eu()
    lines.append(f'## EU Open Data — {note2}')
    for e in eu[:15]:
        lines.append(f"- {e['name']}")
    lines.append('')

    lines.append('## Ръчни източници (изискват човек)')
    lines.append('- МВР, месечни бюлетини: https://www.mvr.bg/opp — PDF/XLS по общини')
    lines.append('- НСИ, годишни таблици: https://www.nsi.bg — XLS')
    lines.append('- Заявление по ЗДОИ за дневни данни: отговор до 14 дни, безплатно')

    os.makedirs('data', exist_ok=True)
    open(REPORT, 'w', encoding='utf-8').write('\n'.join(lines))
    print('\n'.join(lines))
    return egov


def cmd_download(datasets):
    """Сваля ресурсите на намерените набори."""
    os.makedirs(OUT_DIR, exist_ok=True)
    saved = []
    for ds in datasets[:10]:
        uri = ds.get('uri')
        if not uri:
            continue
        api = f'https://data.egov.bg/api/getResourceView?resource_uri={urllib.parse.quote(uri)}'
        raw = fetch(api)
        if not raw:
            continue
        safe = re.sub(r'[^a-zA-Z0-9а-яА-Я_-]+', '_', ds['name'])[:60]
        path = os.path.join(OUT_DIR, f'{safe}.json')
        open(path, 'w', encoding='utf-8').write(raw)
        saved.append(path)
        print('свален:', path, f'({len(raw)} байта)')
    return saved


def normalize_to_daily(path):
    """Свежда произволен CSV/JSON до дневни редове: дата, ПТП, загинали, ранени."""
    rows = []
    if path.endswith('.json'):
        data = json.load(open(path, encoding='utf-8'))
        records = data if isinstance(data, list) else data.get('data', data.get('records', []))
    else:
        text = open(path, encoding='utf-8', errors='replace').read()
        records = list(csv.DictReader(io.StringIO(text)))

    DATE_KEYS = ['дата', 'date', 'дата_птп', 'дата на птп', 'ден']
    DEAD_KEYS = ['загинал', 'убит', 'killed', 'dead', 'fatal']
    INJ_KEYS  = ['ранен', 'injured', 'пострадал']

    for r in records:
        if not isinstance(r, dict):
            continue
        low = {str(k).lower().strip(): v for k, v in r.items()}
        date = next((low[k] for k in low if any(d in k for d in DATE_KEYS)), None)
        if not date:
            continue
        try:
            d = str(date)[:10]
            datetime.datetime.strptime(d, '%Y-%m-%d')
        except Exception:
            continue
        def pick(keys):
            for k in low:
                if any(x in k for x in keys):
                    try: return float(str(low[k]).replace(',', '.'))
                    except Exception: pass
            return None
        rows.append({'date': d, 'dead': pick(DEAD_KEYS), 'injured': pick(INJ_KEYS)})

    # агрегиране по дата
    agg = {}
    for r in rows:
        a = agg.setdefault(r['date'], {'date': r['date'], 'ptp': 0, 'dead': 0, 'injured': 0})
        a['ptp'] += 1
        if r['dead']: a['dead'] += r['dead']
        if r['injured']: a['injured'] += r['injured']
    return sorted(agg.values(), key=lambda x: x['date'])


def cmd_merge(path):
    daily = normalize_to_daily(path)
    if not daily:
        print('нищо използваемо в', path)
        return
    arch_path = 'data/daily_archive.json'
    arch = json.load(open(arch_path, encoding='utf-8')) if os.path.exists(arch_path) else {'days': []}
    index = {d['date']: d for d in arch['days']}
    added = 0
    for row in daily:
        tgt = index.get(row['date'])
        if tgt is None:
            tgt = {'date': row['date'], 'kp_max': None, 'kp_avg': None,
                   'pressure_hpa': None, 'moon_age_days': None, 'dow': None}
            arch['days'].append(tgt); index[row['date']] = tgt
        tgt['accidents'] = {'ptp': row['ptp'], 'dead': row['dead'], 'injured': row['injured']}
        added += 1
    arch['days'].sort(key=lambda d: d['date'])
    arch['updated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    json.dump(arch, open(arch_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'слети {added} дни в архива')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--scan', action='store_true')
    p.add_argument('--download', action='store_true')
    p.add_argument('--merge', metavar='FILE')
    a = p.parse_args()

    if a.merge:
        cmd_merge(a.merge)
    elif a.download:
        found = cmd_scan()
        cmd_download(found)
    else:
        cmd_scan()
