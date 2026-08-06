"""Recalibrate KAT risk engine from MVR 2015-2025 analysis.

Method: multiple regression on log(accidents / 90d baseline), controlling for
year, month and weekday. Out-of-sample validated on 2024-2025 (731 unseen days).
Old engine: MAE 17.62, R2 = -0.26 (worse than predicting the mean).
New engine: MAE 11.59, R2 = +0.44.
"""
import io

src = io.open('index.html', encoding='utf-8').read()
count = 0


def rep(old, new):
    global src, count
    c = src.count(old)
    assert c == 1, 'MARKER x%d: %r' % (c, old[:80])
    src = src.replace(old, new)
    count += 1


# ---------------------------------------------------------------- 1. effects
rep(
"""/* Kp — обърната U-крива: при Kp>7.5 хората си стоят вкъщи и ПТП намаляват */
function kpEffect(kp){
  if(kp>=7.5)return 0.95; if(kp>=6)return 1.08;
  if(kp>=5)return 1.14;   if(kp>=3)return 1.05; return 1.0;
}
function pressEffect(dp){
  if(dp>=10)return 1.14; if(dp>=5)return 1.08; if(dp>=2)return 1.03; return 1.0;
}
function moonEffect(age){
  const n=Math.abs(Math.sin((age/29.53)*Math.PI));
  return n>0.85?1.06:n>0.6?1.03:1.0;
}
function rainEffect(rainMm, snowCm){
  let f = 1.0;
  if(rainMm>=10)f=1.25; else if(rainMm>=3)f=1.16; else if(rainMm>=0.5)f=1.08;
  if(snowCm>=5)f=Math.max(f,1.38); else if(snowCm>0)f=Math.max(f,1.24);
  return f;
}""",
"""/* ═══ КАЛИБРИРАНО ВЪРХУ МВР 2015–2025 (4018 дни) ═══
   ОТПАДНАЛИ ФАКТОРИ — проверени и незначими:
     Kp геомагнитен : r=-0.023; лагове 0–7 дни всички под шума
     Лунна фаза     : пермутационен p=0.76 — сигналът е артефакт
     Δ налягане     : r=-0.060
     Жега (обезводняване): +1.0%, доверителният интервал пресича нулата
   Оставени като 1.0, за да не изкривяват резултата.                        */
function kpEffect(kp){ return 1.0; }
function pressEffect(dp){ return 1.0; }
function moonEffect(age){ return 1.0; }

/* Валеж (mm/24ч) — най-силният фактор, r=+0.366 */
function rainEffect(rainMm, snowCm){
  let f;
  if(rainMm>=20)      f=1.347;
  else if(rainMm>=10) f=1.200;
  else if(rainMm>=5)  f=1.113;
  else if(rainMm>=2)  f=1.044;
  else if(rainMm>=0.5)f=1.004;
  else                f=0.964;
  if(snowCm>=5)       f=Math.max(f,1.404);   /* сняг, r=+0.278 */
  else if(snowCm>=2)  f=Math.max(f,1.243);
  else if(snowCm>=0.5)f=Math.max(f,1.052);
  return f;
}

/* Облачност — втори по сила, r=-0.293. sun = слънчеви часове / светла част */
function cloudEffect(sun){
  if(sun==null) return 1.0;
  if(sun<0.15) return 1.175;
  if(sun<0.35) return 1.071;
  if(sun<0.55) return 1.026;
  if(sun<0.75) return 0.999;
  return 0.975;
}

/* Предколеден трафик — най-силният календарен ефект след метеото.
   23 декември е най-рисковият ден в годината: +35%. Спада рязко на 24-ти. */
function xmasEffect(date){
  if(date.getMonth()!==11) return 1.0;
  const d=date.getDate();
  if(d>=24)  return 1.0;
  if(d===23) return 1.35;
  if(d>=21)  return 1.22;
  if(d>=19)  return 1.18;
  if(d>=16)  return 1.12;
  return 1.0;
}

/* Режим — остатъчната аварийност се влачи напред: r=+0.31 на 1 ден,
   полуживот 5 дни, изчезва към 8-ия. Коефициент 0.469 върху средното
   от последните 3 дни. Изисква ПРЕСНИ МВР данни; без тях е неутрален. */
function regimeEffect(){
  const off={mult:1.0, active:false, n:0};
  const days=(S.mvrDays||[]).filter(d=>d&&d.date&&mvTotal(d)!=null)
    .sort((a,b)=>b.date.localeCompare(a.date)).slice(0,3);
  if(days.length<2) return off;
  const logs=[];
  for(const e of days){
    const dt=new Date(e.date+'T12:00:00');
    if((Date.now()-dt)/86400000 > 7) continue;
    const exp=baseDaily()*weekdayFactor(dt.getDay())*monthFactor(dt.getMonth()+1)*xmasEffect(dt);
    const act=mvTotal(e);
    if(!exp||!act||act<=0) continue;
    logs.push(Math.log(act/exp));
  }
  if(logs.length<2) return off;
  const avg=logs.reduce((a,b)=>a+b,0)/logs.length;
  return {mult:Math.max(0.85,Math.min(1.18,Math.exp(0.469*avg))), active:true, n:logs.length};
}""")

# --------------------------------------------------------------- 2. holiday
rep(
"function holidayEffect(st){ return st===2?1.10 : st===1?1.14 : 1.0; } // денят ПРЕДИ празник е най-натоварен (пътуване)",
"""/* Празник ×0.809 — значително по-спокойно. Денят ПРЕДИ празник няма
   ефект (1.0005, CI пресича 1); старото 1.14 беше погрешно. */
function holidayEffect(st){ return st===2?0.809 : 1.0; }""")

# ---------------------------------------------------------- 3. weekday/month
rep(
"""function weekdayFactor(dow){
  const wd = S.historical?.risk_by_weekday;
  if(wd){
    const key = Object.keys(wd).find(k=>{
      // ключове тип '0_monday' (Пн=0) → JS dow (Нд=0)
      const map = {monday:1,tuesday:2,wednesday:3,thursday:4,friday:5,saturday:6,sunday:0};
      const name = k.split('_')[1];
      return map[name]===dow;
    });
    if(key) return wd[key];
  }
  return [0.82,0.88,0.93,0.98,1.28,1.22,0.78][dow]||1.0;
}""",
"""/* Ден от седмицата — JS getDay(): 0=Неделя. Калибрирано от 4018 дни.
   Старите стойности бяха силно сгрешени (Чт 1.28 срещу реални 1.05,
   Пн 0.88 срещу 1.07) и out-of-sample даваха R²=-0.26 — по-зле от нищо.
   Историческият JSON вече не се ползва за тези коефициенти. */
const WD_FACTOR=[0.797,1.074,1.037,1.014,1.052,1.120,0.905];
function weekdayFactor(dow){ return WD_FACTOR[dow]||1.0; }""")

rep(
"""function monthFactor(mon1){ // 1–12
  const md = S.historical?.risk_by_month;
  if(md){
    const key = Object.keys(md).find(k=>k.startsWith(mon1+'_'));
    if(key) return md[key];
  }
  return 1.0;
}""",
"""/* Месец 1–12 — пик август (+11%), дъно март (-11%). */
const MO_FACTOR=[0.943,0.916,0.888,0.923,0.963,1.056,1.088,1.106,1.063,1.065,1.013,0.970];
function monthFactor(mon1){ return MO_FACTOR[mon1-1]||1.0; }""")

# -------------------------------------------------------------- 4. calcRisk
rep(
"""function calcRisk(env, date){
  const dow = date.getDay(), mon = date.getMonth()+1;
  const hs  = holidayStatus(date);
  const envMult = Math.min(1.9,
    kpEffect(env.kp??2) * pressEffect(env.dp??0) * moonEffect(env.moonAge??calcMoonAge(date))
    * rainEffect(env.rain??0, env.snow??0) * iceEffect(env.tmin, (env.rain??0)+(env.snow??0))
    * windEffect(env.wind) * fogEffect(env.vis) * holidayEffect(hs) * hailEffect(env.wcode)
    * ((env.kp>=5 && env.dp>=10)?1.06:1.0)
  );
  const wf = weekdayFactor(dow), mf = monthFactor(mon);
  const expected = baseDaily() * wf * mf * envMult;
  const totalMult = envMult * ((wf*mf)||1);
  const riskScore = Math.max(0, Math.min(10, Math.round((totalMult-0.8)*11)));
  return { expected: Math.round(expected*10)/10, riskScore, envMult, wf, mf, hs };
}""",
"""/* Скала 1–10 = децили на прогнозата от 4018 дни. Всяко ниво е ~10% от
   дните, така че «7/10» значи «по-лошо от 70% от дните» — не абстракция.
   Валидация: реалните ПТП на всяко ниво съвпадат с прогнозата (±2%). */
const RISK_CUTS=[0.782,0.853,0.913,0.952,0.991,1.030,1.069,1.114,1.178];
function scoreFromMult(m){
  let s=1; for(const c of RISK_CUTS){ if(m>=c) s++; }
  return Math.max(1,Math.min(10,s));
}

function calcRisk(env, date, opts){
  const dow = date.getDay(), mon = date.getMonth()+1;
  const hs  = holidayStatus(date);
  const reg = (opts&&opts.noRegime) ? {mult:1.0,active:false,n:0} : regimeEffect();
  const envMult = Math.min(1.9,
    rainEffect(env.rain??0, env.snow??0)
    * cloudEffect(env.sun)
    * iceEffect(env.tmin, (env.rain??0)+(env.snow??0))
    * windEffect(env.wind) * fogEffect(env.vis) * hailEffect(env.wcode)
    * holidayEffect(hs)
  );
  const wf = weekdayFactor(dow), mf = monthFactor(mon), xf = xmasEffect(date);
  const totalMult = envMult * wf * mf * xf * reg.mult;
  const expected  = baseDaily() * totalMult;
  return { expected: Math.round(expected*10)/10, riskScore: scoreFromMult(totalMult),
           envMult, wf, mf, xf, hs, totalMult, regime:reg };
}""")

# ----------------------------------------------------------- 5. colour scale
rep(
"const lvOf = s => s<=2?0:s<=5?1:s<=7?2:3;",
"""/* Скала 1–10 → цвят: плавен преход зелено → жълто → оранжево → червено,
   така че нивото се чете интуитивно без легенда. */
const SCORE_COLORS=['#22c55e','#4ade80','#a3e635','#d9e021','#fbbf24',
                    '#fb923c','#f97316','#f2621f','#ef4444','#dc2626'];
const scoreColor = s => SCORE_COLORS[Math.max(1,Math.min(10,s))-1];
const lvOf = s => s<=3?0:s<=6?1:s<=8?2:3;""")

# -------------------------------------------------------- 6. sunshine intake
rep(
"+'&daily=surface_pressure_max,surface_pressure_min,precipitation_sum,snowfall_sum,wind_speed_10m_max,temperature_2m_min,weather_code'",
"+'&daily=surface_pressure_max,surface_pressure_min,precipitation_sum,snowfall_sum,wind_speed_10m_max,temperature_2m_min,weather_code,sunshine_duration,daylight_duration'")

rep(
"""    if(d.daily){
      const dm=d.daily.surface_pressure_max,dn=d.daily.surface_pressure_min;""",
"""    if(d.daily){
      const _sd=d.daily.sunshine_duration, _dl=d.daily.daylight_duration;
      if(_sd&&_dl&&_sd[1]!=null&&_dl[1]) S.sunToday=_sd[1]/_dl[1];
      const dm=d.daily.surface_pressure_max,dn=d.daily.surface_pressure_min;""")

rep(
"""          wcode:d.daily.weather_code?.[idx],
        };""",
"""          wcode:d.daily.weather_code?.[idx],
          sun:(d.daily.sunshine_duration?.[idx]!=null && d.daily.daylight_duration?.[idx])
              ? d.daily.sunshine_duration[idx]/d.daily.daylight_duration[idx] : null,
        };""")

rep(
"  rainNow:0, snowNow:0, windNow:0, visNow:null,",
"  rainNow:0, snowNow:0, windNow:0, visNow:null, sunToday:null,")

rep(
"""    rain:S.rainNow, snow:S.snowNow, wind:S.windNow, vis:S.visNow,
    tmin:S.temp!=null?parseFloat(S.temp):null,
  };""",
"""    rain:S.rainNow, snow:S.snowNow, wind:S.windNow, vis:S.visNow,
    sun:S.sunToday,
    tmin:S.temp!=null?parseFloat(S.temp):null,
  };""")

rep(
"""      rain: daily.rain??0, snow: daily.snow??0,
      wind: daily.wind, tmin: daily.tmin, vis:null, wcode: daily.wcode,
    };""",
"""      rain: daily.rain??0, snow: daily.snow??0, sun: daily.sun,
      wind: daily.wind, tmin: daily.tmin, vis:null, wcode: daily.wcode,
    };""")

# -------------------------------------------------------------- 7. UI colour
rep(
"""  document.getElementById('sl-score').textContent = r.riskScore+'/10';
  document.getElementById('sl-score').style.color = lvColors[lv];""",
"""  document.getElementById('sl-score').textContent = r.riskScore+'/10';
  document.getElementById('sl-score').style.color = scoreColor(r.riskScore);""")

rep(
"""  document.getElementById('sl-road').textContent = k.roadLevels[lv];
  document.getElementById('sl-road').style.color = lvColors[lv];""",
"""  document.getElementById('sl-road').textContent = k.roadLevels[lv];
  document.getElementById('sl-road').style.color = scoreColor(r.riskScore);""")

# ------------------------------------------------------------ 8. explanation
rep(
"""    ? '📊 Очакван брой ПТП в София-град според модела: историческа база 2015–2024 (ден · месец) × среда (космическо време · дъжд/сняг · градушка/буря · лед · вятър · налягане · луна · празници).'
    : '📊 Expected crashes in Sofia per the model: 2015–2024 historical baseline (weekday · month) × environment (space weather · rain/snow · ice · wind · pressure · moon · holidays).';""",
"""    ? '📊 Модел, калибриран върху 4018 дни реални МВР данни (2015–2025). Скалата 1–10 са децили: 7/10 значи по-лошо от 70% от дните. Фактори: ден · месец × валеж/сняг · облачност · лед · вятър · празници · предколеден трафик. Геомагнитните бури и лунните фази са проверени и отпаднали като незначими.'
    : '📊 Model calibrated on 4018 days of real MVR data (2015–2025). The 1–10 scale is deciles: 7/10 means worse than 70% of days. Factors: weekday · month × precipitation · cloud · ice · wind · holidays · pre-Christmas traffic. Geomagnetic storms and lunar phases were tested and dropped as insignificant.';""")

io.open('index.html', 'w', encoding='utf-8').write(src)
print('PATCHED %d blocks OK' % count)
