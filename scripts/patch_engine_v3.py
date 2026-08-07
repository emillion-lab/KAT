"""KAT risk engine v3.

Adds, on top of v2:
  1. Second scale: harm risk (people) alongside crash risk (cars).
     Calibrated separately on killed+injured, 2015-2025 excl. 2020.
     Biggest divergence is seasonal: Aug x1.10 crashes but x1.32 harm;
     Feb x0.90 crashes but x0.74 harm. Sunday is quiet for cars, normal for people.
  2. Seasonal regime weight. Regime autocorrelation measured by month:
     Jan .45  Feb .35  Mar .18  Apr .25  May .14  Jun .06
     Jul .05  Aug .12  Sep .19  Oct .12  Nov .08  Dec .42
     Flat 0.469 over-weighted summer, where the regime barely exists.
  3. Diurnal amplitude >=14C under clear sky (x1.03; x1.06 in spring).
     Threshold is sharp between 13 and 14 degrees; below it, nothing.
  4. Day after a public holiday x0.885 (CI -14.6 .. -8.3).
  5. Hardened regime input: mvTotal no longer trusts the mixed `ptp` field
     (it blends national serious-crash counts with single-region headlines,
     e.g. "three crashes in Razgrad"), and the regime needs 3 fresh days.
"""
import io

src = io.open('index.html', encoding='utf-8').read()
count = 0

def rep(old, new):
    global src, count
    c = src.count(old)
    assert c == 1, 'MARKER x%d: %r' % (c, old[:90])
    src = src.replace(old, new); count += 1


# ------------------------------------------------------- 1. harm-scale tables
rep(
"""const RISK_CUTS=[0.782,0.853,0.913,0.952,0.991,1.030,1.069,1.114,1.178];""",
"""const RISK_CUTS=[0.782,0.853,0.913,0.952,0.991,1.030,1.069,1.114,1.178];

/* ═══ СКАЛА 2 — РИСК ЗА ЧОВЕКА (загинали + ранени) ═══
   Отделно калибрирана. Разминава се със скалата за колата най-силно
   сезонно: август ×1.10 по брой ПТП, но ×1.32 по пострадали;
   февруари ×0.90 и ×0.74. Неделя е тиха за ламарината, но не за хората. */
const H_WD=[1.007,0.942,1.046,0.959,0.939,1.004,1.102];
const H_MO=[0.741,0.736,0.791,0.861,1.001,1.154,1.263,1.319,1.148,1.032,1.008,0.927];
const H_CUTS=[0.729,0.794,0.861,0.936,0.990,1.056,1.113,1.181,1.267];
function harmRain(rainMm,snowCm){
  let f;
  if(rainMm>=20)      f=1.301;
  else if(rainMm>=10) f=1.178;
  else if(rainMm>=5)  f=1.062;
  else if(rainMm>=2)  f=1.019;
  else if(rainMm>=0.5)f=0.988;
  else                f=0.978;
  /* сняг вдига броя силно, но пострадалите — далеч по-малко:
     бавно каране дава много ламарина и малко кръв */
  if(snowCm>=5)       f=Math.max(f,1.239);
  else if(snowCm>=2)  f=Math.max(f,1.106);
  else if(snowCm>=0.5)f=Math.max(f,0.957);
  return f;
}
function harmCloud(sun){
  if(sun==null) return 1.0;
  if(sun<0.15) return 1.142;
  if(sun<0.35) return 1.043;
  if(sun<0.55) return 0.948;
  if(sun<0.75) return 0.979;
  return 0.988;
}
function harmScore(m){
  let s=1; for(const c of H_CUTS){ if(m>=c) s++; }
  return Math.max(1,Math.min(10,s));
}""")

# ------------------------------------------- 2. amplitude + day-after-holiday
rep(
"""/* Режим — остатъчната аварийност се влачи напред""",
"""/* Денонощна амплитуда — праг между 13 и 14°C е рязък: под него нищо,
   над него значимо. Проверено само сред ясни дни, за да не се бърка с
   облачността (двете са колинеарни, r=+0.66). Механизмът остава хипотеза. */
function amplitudeEffect(tmin,tmax,sun,mon1){
  if(tmin==null||tmax==null) return 1.0;
  if(sun!=null && sun<0.6) return 1.0;
  const r=tmax-tmin;
  if(r<14) return 1.0;
  const spring=(mon1>=3&&mon1<=5);
  if(r>=17) return spring?1.061:1.046;
  return spring?1.033:1.022;
}

/* Ден СЛЕД празник — възстановяване, слаб трафик. -11.5%, CI[-14.6,-8.3] */
function afterHolidayEffect(date){
  const prev=new Date(date.getTime()-86400000);
  return holidayStatus(prev)===2 ? 0.885 : 1.0;
}

/* Сезонно тегло на режима. Автокорелацията варира силно по месец —
   през юли режимът практически не съществува (r=0.05), през януари е
   основен фактор (r=0.45). Постоянното 0.469 надценяваше лятото. */
const REG_W=[0.45,0.35,0.18,0.25,0.14,0.06,0.05,0.12,0.19,0.12,0.08,0.42];

/* Режим — остатъчната аварийност се влачи напред""")

# ------------------------------------------------------- 3. regime hardening
rep(
"""  const days=(S.mvrDays||[]).filter(d=>d&&d.date&&mvTotal(d)!=null)
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
  return {mult:Math.max(0.85,Math.min(1.18,Math.exp(0.469*avg))), active:true, n:logs.length};""",
"""  const days=(S.mvrDays||[]).filter(d=>d&&d.date&&mvTotal(d)!=null)
    .sort((a,b)=>b.date.localeCompare(a.date)).slice(0,5);
  if(days.length<3) return off;
  const logs=[];
  for(const e of days){
    const dt=new Date(e.date+'T12:00:00');
    if((Date.now()-dt)/86400000 > 7) continue;
    const exp=baseDaily()*weekdayFactor(dt.getDay())*monthFactor(dt.getMonth()+1)*xmasEffect(dt);
    const act=mvTotal(e);
    if(!exp||!act||act<=0) continue;
    logs.push(Math.log(act/exp));
  }
  /* Изискваме 3 пресни дни: при 2 един изтърван ден върти скора без причина */
  if(logs.length<3) return off;
  const avg=logs.reduce((a,b)=>a+b,0)/logs.length;
  const w=REG_W[new Date().getMonth()];
  return {mult:Math.max(0.85,Math.min(1.18,Math.exp(w*avg))), active:true, n:logs.length, w};""")

# --------------------------------------------------- 4. mvTotal de-poisoning
rep(
"""function mvTotal(m){
  if(!m) return null;
  if(m.sofia_light!=null) return m.sofia_light; // София-специфичен брой — нашата серия
  if(m.ptp!=null) return m.ptp;
  if(m.light!=null||m.serious!=null) return (m.light||0)+(m.serious||0);
  return null;
}""",
"""function mvTotal(m){
  if(!m) return null;
  if(m.sofia_light!=null) return m.sofia_light; // София-специфичен брой — нашата серия
  /* `ptp` НЕ се ползва: полето смесва национални тежки ПТП (16-33/ден) с
     единични областни заглавия ("в Разградско три катастрофи" → 3).
     Покритие 36%, а стойностите са несъпоставими. `injured` идва от едно и
     също изречение на МВР, има 80% покритие и стабилна медиана ~27. */
  if(m.injured!=null) return m.injured;
  if(m.light!=null||m.serious!=null) return (m.light||0)+(m.serious||0);
  return null;
}""")

# ------------------------------------------------------------- 5. calcRisk
rep(
"""  const wf = weekdayFactor(dow), mf = monthFactor(mon), xf = xmasEffect(date);
  const totalMult = envMult * wf * mf * xf * reg.mult;
  const expected  = baseDaily() * totalMult;
  return { expected: Math.round(expected*10)/10, riskScore: scoreFromMult(totalMult),
           envMult, wf, mf, xf, hs, totalMult, regime:reg };""",
"""  const wf = weekdayFactor(dow), mf = monthFactor(mon), xf = xmasEffect(date);
  const af = amplitudeEffect(env.tmin, env.tmax, env.sun, mon);
  const ah = afterHolidayEffect(date);
  const totalMult = envMult * wf * mf * xf * af * ah * reg.mult;
  const expected  = baseDaily() * totalMult;

  /* Скала 2 — риск за ЧОВЕКА. Същата структура, свои коефициенти. */
  const harmMult = Math.min(1.9,
      harmRain(env.rain??0, env.snow??0) * harmCloud(env.sun)
      * iceEffect(env.tmin, (env.rain??0)+(env.snow??0))
      * windEffect(env.wind) * fogEffect(env.vis) * hailEffect(env.wcode)
      * holidayEffect(hs)
    ) * H_WD[dow] * H_MO[mon-1] * xf * af * ah * reg.mult;

  return { expected: Math.round(expected*10)/10,
           riskScore: scoreFromMult(totalMult),
           harmScore: harmScore(harmMult),
           envMult, wf, mf, xf, af, ah, hs, totalMult, harmMult, regime:reg };""")

io.open('index.html','w',encoding='utf-8').write(src)
print('PATCHED %d blocks OK' % count)
