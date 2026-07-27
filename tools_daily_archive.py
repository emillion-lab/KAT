import json, urllib.request, datetime, os

def get(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'kat-daily-archive/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print('fetch failed:', url, e)
        return None

today = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)).strftime('%Y-%m-%d')

kp_max = kp_avg = None
raw = get('https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json')
if raw and isinstance(raw, list) and len(raw) > 1:
    hdr = raw[0]
    if isinstance(hdr, list):
        try:
            ti = hdr.index('time_tag')
            ki = hdr.index('Kp') if 'Kp' in hdr else hdr.index('kp_index') if 'kp_index' in hdr else 1
            vals = []
            for row in raw[1:]:
                if isinstance(row, list) and len(row) > max(ti, ki) and str(row[ti])[:10] == today:
                    try: vals.append(float(row[ki]))
                    except (TypeError, ValueError): pass
            if vals:
                kp_max, kp_avg = max(vals), sum(vals) / len(vals)
        except (ValueError, IndexError) as e:
            print('Kp parse issue:', e)
    elif isinstance(hdr, dict):
        # алтернативен формат: списък от обекти {time_tag, kp_index/Kp}
        vals = []
        for row in raw:
            if not isinstance(row, dict): continue
            tt = row.get('time_tag', '')
            if str(tt)[:10] != today: continue
            v = row.get('kp_index', row.get('Kp', row.get('kp')))
            try:
                if v is not None: vals.append(float(v))
            except (TypeError, ValueError): pass
        if vals:
            kp_max, kp_avg = max(vals), sum(vals) / len(vals)
        else:
            print('unexpected Kp format, sample:', str(raw[:1])[:200])
    else:
        print('unexpected Kp format:', type(hdr))

pressure = None
om = get('https://api.open-meteo.com/v1/forecast?latitude=42.6977&longitude=23.3219&current=surface_pressure')
if om:
    pressure = (om.get('current') or {}).get('surface_pressure')

MOON_REF = datetime.datetime(2000, 1, 6, 18, 14)
SYN = 29.530588853
now = datetime.datetime.now(datetime.timezone.utc)
moon_age = ((now.replace(tzinfo=None) - MOON_REF).total_seconds() / 86400) % SYN

row = {
    'date': today,
    'kp_max': kp_max,
    'kp_avg': round(kp_avg, 2) if kp_avg else None,
    'pressure_hpa': pressure,
    'moon_age_days': round(moon_age, 2),
    'dow': now.weekday(),
    'accidents': None,
}

path = 'data/daily_archive.json'
if os.path.exists(path):
    data = json.load(open(path))
else:
    data = {
        'note': 'Дневен архив: Kp, налягане, луна — трупа се от 2026-07-27. '
                'Произшествия се добавят отделно, когато има надежден източник.',
        'days': [],
    }
data['days'] = [d for d in data['days'] if d['date'] != today] + [row]
data['days'].sort(key=lambda d: d['date'])
data['updated'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(data, open(path, 'w'), ensure_ascii=False, indent=2)
print('записан ред:', row)
