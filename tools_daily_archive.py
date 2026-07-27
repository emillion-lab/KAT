import json, urllib.request, datetime, os

def get(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'kat-daily-archive/1.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print('fetch failed:', url, e)
        return None

today = (datetime.datetime.utcnow() + datetime.timedelta(hours=3)).strftime('%Y-%m-%d')

kp_max = kp_avg = None
raw = get('https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json')
if raw:
    hdr = raw[0]
    ti = hdr.index('time_tag')
    vals = [float(row[1]) for row in raw[1:] if row[ti][:10] == today]
    if vals:
        kp_max, kp_avg = max(vals), sum(vals)/len(vals)

pressure = None
om = get('https://api.open-meteo.com/v1/forecast?latitude=42.6977&longitude=23.3219&current=surface_pressure')
if om:
    pressure = (om.get('current') or {}).get('surface_pressure')

MOON_REF = datetime.datetime(2000, 1, 6, 18, 14)
SYN = 29.530588853
now = datetime.datetime.utcnow()
moon_age = ((now - MOON_REF).total_seconds() / 86400) % SYN

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
data['updated'] = datetime.datetime.utcnow().isoformat()
json.dump(data, open(path, 'w'), ensure_ascii=False, indent=2)
print('записан ред:', row)
