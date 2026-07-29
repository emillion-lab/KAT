import json, urllib.request, datetime
url = ('https://api.open-meteo.com/v1/forecast?latitude=42.6977&longitude=23.3219'
       '&hourly=precipitation_probability,precipitation&forecast_days=2&timezone=Europe%2FSofia')
req = urllib.request.Request(url, headers={'User-Agent':'kat/1.0'})
d = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
t, p, mm = d['hourly']['time'], d['hourly']['precipitation_probability'], d['hourly']['precipitation']
now = datetime.datetime.now()
print('София — следващите 14 часа:')
shown = 0
for i, ts in enumerate(t):
    dt = datetime.datetime.fromisoformat(ts)
    if dt < now: continue
    h = round((dt-now).total_seconds()/3600)
    if h > 14: break
    flag = ' ← ДЪЖД' if (p[i] >= 50 or mm[i] > 0.15) else ''
    print(f'  {ts[11:16]} (+{h:2d}ч)  {p[i]:3d}%  {mm[i]:.1f}mm{flag}')
    shown += 1
first = next((i for i,ts in enumerate(t)
              if datetime.datetime.fromisoformat(ts) >= now and (p[i]>=50 or mm[i]>0.15)), None)
print()
if first is None:
    print('→ няма дъжд в наличната прогноза')
else:
    dt = datetime.datetime.fromisoformat(t[first])
    print(f'→ първи дъжд: {t[first][:16]} след {round((dt-now).total_seconds()/3600)}ч ({p[first]}%)')
