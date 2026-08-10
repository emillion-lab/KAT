#!/usr/bin/env python3
"""Публикува текущата оценка на риска като малък JSON за външни приложения.

Защо: шофьорското приложение (APK) носи собствено, вградено копие на
изчислението — оттам "0.88× Спокойна среда" и "Kp 2.0", докато KAT показва
6/10 и 6/10. Всяка промяна в модела иначе изисква нов APK.

С този файл приложението чете готова стойност вместо да смята. Моделът се
поправя на едно място и всичко останало се обновява само.

Формула: същата като в engine.js. Ако се разминат, тук е дублирането —
затова коефициентите са преписани буквално, с бележка да се сменят заедно.

Изход: data/risk_now.json — под 1 KB, обновяван на всеки час.
"""
import json, os, datetime, urllib.request

# ── коефициенти: ТОЧНО копие от engine.js ───────────────────────────────────
WD   = [0.797,1.074,1.037,1.014,1.052,1.120,0.905]            # getDay 0=Нд
MO   = [0.943,0.916,0.888,0.923,0.963,1.056,1.088,1.106,1.063,1.065,1.013,0.970]
CUTS = [0.837,0.926,0.987,1.038,1.078,1.122,1.175,1.289,1.474]
H_WD = [1.007,0.942,1.046,0.959,0.939,1.004,1.102]
H_MO = [0.741,0.736,0.791,0.861,1.001,1.154,1.263,1.319,1.148,1.032,1.008,0.927]
H_CUTS=[0.771,0.894,0.977,1.047,1.123,1.200,1.253,1.333,1.411]

def rain_f(mm, cm):
    f = 1.347 if mm>=20 else 1.200 if mm>=10 else 1.113 if mm>=5 else \
        1.044 if mm>=2 else 1.004 if mm>=0.5 else 0.964
    if cm>=5: f=max(f,1.404)
    elif cm>=2: f=max(f,1.243)
    elif cm>=0.5: f=max(f,1.052)
    return f

def harm_rain(mm, cm):
    f = 1.301 if mm>=20 else 1.178 if mm>=10 else 1.062 if mm>=5 else \
        1.019 if mm>=2 else 0.988 if mm>=0.5 else 0.978
    if cm>=5: f=max(f,1.239)
    elif cm>=2: f=max(f,1.106)
    elif cm>=0.5: f=max(f,0.957)
    return f

def cloud_f(s):
    if s is None: return 1.0
    return 1.175 if s<0.15 else 1.071 if s<0.35 else 1.026 if s<0.55 else 0.999 if s<0.75 else 0.975

def harm_cloud(s):
    if s is None: return 1.0
    return 1.142 if s<0.15 else 1.043 if s<0.35 else 0.948 if s<0.55 else 0.979 if s<0.75 else 0.988

def ice_f(tmin, precip):
    if tmin is None: return 1.0
    if tmin<=0 and precip>0.5: return 1.18
    if tmin<=-3: return 1.06
    if tmin<=0: return 1.03
    return 1.0

def wind_f(k):
    if k is None: return 1.0
    return 1.09 if k>=60 else 1.04 if k>=40 else 1.0

def ampl_f(tmin, tmax, sun, mon):
    if tmin is None or tmax is None: return 1.0
    if sun is not None and sun<0.6: return 1.0
    r = tmax-tmin
    if r<14: return 1.0
    sp = 3<=mon<=5
    if r>=17: return 1.061 if sp else 1.046
    return 1.033 if sp else 1.022

def xmas_f(d):
    m, day = d.month, d.day
    if m==1:  return 0.547 if day==1 else 0.774 if day==2 else 1.0
    if m!=12: return 1.0
    if day==31: return 0.561
    if day>=27: return 0.85
    if day>=24: return 1.0
    if day==23: return 1.35
    if day>=21: return 1.22
    if day>=19: return 1.18
    if day>=16: return 1.12
    return 1.0

FIXED = {(1,1),(3,3),(5,1),(5,6),(5,24),(9,6),(9,22),(12,24),(12,25),(12,26)}
EASTER = {2026:(4,12), 2027:(5,2), 2028:(4,16)}
def holiday(d):
    if (d.month, d.day) in FIXED: return True
    e = EASTER.get(d.year)
    if e:
        ed = datetime.date(d.year, e[0], e[1])
        if -2 <= (d-ed).days <= 1: return True
    return False

def score(mult, cuts):
    s = 1
    for c in cuts:
        if mult >= c: s += 1
    return max(1, min(10, s))

def main():
    tz = datetime.timezone(datetime.timedelta(hours=3))
    today = datetime.datetime.now(tz).date()
    url = ('https://api.open-meteo.com/v1/forecast?latitude=42.6975&longitude=23.3242'
           '&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,'
           'wind_speed_10m_max,sunshine_duration,daylight_duration'
           '&forecast_days=4&timezone=Europe%2FSofia')
    d = json.load(urllib.request.urlopen(url, timeout=60))['daily']

    days = []
    for i in range(4):
        date = today + datetime.timedelta(days=i)
        rain = d['precipitation_sum'][i] or 0
        snow = d['snowfall_sum'][i] or 0
        tmin, tmax = d['temperature_2m_min'][i], d['temperature_2m_max'][i]
        wind = d['wind_speed_10m_max'][i]
        sun = (d['sunshine_duration'][i]/d['daylight_duration'][i]
               if d['sunshine_duration'][i] is not None and d['daylight_duration'][i] else None)

        dow = (date.weekday()+1) % 7          # към getDay: 0=Нд
        mon = date.month
        common = (ice_f(tmin, rain+snow) * wind_f(wind) * xmas_f(date)
                  * ampl_f(tmin, tmax, sun, mon)
                  * (0.809 if holiday(date) else 1.0)
                  * (0.885 if holiday(date - datetime.timedelta(days=1)) else 1.0))
        car  = rain_f(rain,snow)*cloud_f(sun)*WD[dow]*MO[mon-1]*common
        harm = harm_rain(rain,snow)*harm_cloud(sun)*H_WD[dow]*H_MO[mon-1]*common
        days.append({
            'date': date.isoformat(),
            'car': score(car, CUTS), 'harm': score(harm, H_CUTS),
            'car_mult': round(car,3), 'harm_mult': round(harm,3),
            'rain': round(rain,1), 'snow': round(snow,1),
            'tmin': tmin, 'tmax': tmax,
        })

    out = {'generated': datetime.datetime.now(tz).isoformat(timespec='minutes'),
           'source': 'KAT · МВР 2015–2025', 'days': days}
    os.makedirs('data', exist_ok=True)
    with open('data/risk_now.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    t = days[0]
    print(f"днес {t['date']}: кола {t['car']}/10, човек {t['harm']}/10")

if __name__ == '__main__':
    main()
