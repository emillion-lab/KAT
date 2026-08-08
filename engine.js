/* ═══════════════════════════════════════════════════════════════════════
   KAT — двигател за оценка на пътния риск
   Калибриран върху 4018 дни реални данни от МВР (2015–2025, без 2020).
   Проверен out-of-sample: ноември 2025 средна грешка 11.1%, корелация 0.84;
   декември 2025 средна грешка 10.5%, систематично отклонение −0.3%.

   ВАЖНО за праговете: изчислени са от ТОЧНО СЪЩАТА формула по-долу, не от
   регресионна прогноза. Предишната версия смесваше двете и месечният
   множител за август сам надхвърляше горния праг — заради което всеки
   августовски ден излизаше 10/10 и скалата умираше за цял месец.
   ═══════════════════════════════════════════════════════════════════════ */

/* --- Скала 1: РИСК ЗА КОЛАТА (брой ПТП) --- */
const WD_FACTOR = [0.797,1.074,1.037,1.014,1.052,1.120,0.905];  // getDay: 0=Нд
const MO_FACTOR = [0.943,0.916,0.888,0.923,0.963,1.056,
                   1.088,1.106,1.063,1.065,1.013,0.970];
const RISK_CUTS = [0.837,0.926,0.987,1.038,1.078,1.122,1.175,1.289,1.474];

/* --- Скала 2: РИСК ЗА ЧОВЕКА (загинали + ранени) ---
   Разминава се със скала 1 най-силно сезонно: август има +10% ПТП,
   но +32% пострадали. Неделя е тиха за ламарината, но не за хората. */
const H_WD  = [1.007,0.942,1.046,0.959,0.939,1.004,1.102];
const H_MO  = [0.741,0.736,0.791,0.861,1.001,1.154,
               1.263,1.319,1.148,1.032,1.008,0.927];
const H_CUTS= [0.771,0.894,0.977,1.047,1.123,1.200,1.253,1.333,1.411];

/* Сезонно тегло на "режима" — устойчивостта варира силно по месеци.
   През юли почти не съществува (r=0.05), през януари е основен (r=0.45). */
const REG_W = [0.45,0.35,0.18,0.25,0.14,0.06,0.05,0.12,0.19,0.12,0.08,0.42];

/* ---------- фактори, които ВЛИЯЯТ ---------- */

function rainEffect(mm, cm){                    // r = +0.366, най-силният
  let f = mm>=20?1.347 : mm>=10?1.200 : mm>=5?1.113
        : mm>=2?1.044  : mm>=0.5?1.004 : 0.964;
  if(cm>=5)        f=Math.max(f,1.404);         // r = +0.278
  else if(cm>=2)   f=Math.max(f,1.243);
  else if(cm>=0.5) f=Math.max(f,1.052);
  return f;
}
function harmRain(mm, cm){
  let f = mm>=20?1.301 : mm>=10?1.178 : mm>=5?1.062
        : mm>=2?1.019  : mm>=0.5?0.988 : 0.978;
  /* сняг вдига броя силно, но пострадалите — далеч по-малко:
     бавното каране дава много ламарина и малко кръв */
  if(cm>=5)        f=Math.max(f,1.239);
  else if(cm>=2)   f=Math.max(f,1.106);
  else if(cm>=0.5) f=Math.max(f,0.957);
  return f;
}
function cloudEffect(s){                        // r = -0.293, втори по сила
  if(s==null) return 1.0;
  return s<0.15?1.175 : s<0.35?1.071 : s<0.55?1.026 : s<0.75?0.999 : 0.975;
}
function harmCloud(s){
  if(s==null) return 1.0;
  return s<0.15?1.142 : s<0.35?1.043 : s<0.55?0.948 : s<0.75?0.979 : 0.988;
}
/* Денонощна амплитуда — прагът между 13 и 14°C е рязък. Проверено само
   сред ясни дни: амплитуда и слънчевост са колинеарни (r=+0.66), тъй че
   механизмът остава хипотеза, макар ефектът да е реален. */
function amplitudeEffect(tmin, tmax, sun, mon){
  if(tmin==null || tmax==null) return 1.0;
  if(sun!=null && sun<0.6) return 1.0;
  const r = tmax - tmin;
  if(r < 14) return 1.0;
  const spring = (mon>=3 && mon<=5);
  if(r >= 17) return spring?1.061:1.046;
  return spring?1.033:1.022;
}
/* Предколеден трафик и новогодишна яма. */
function xmasEffect(date){
  const m = date.getMonth(), d = date.getDate();
  /* 31 декември и 1 януари са наполовина по-спокойни от обичайното.
     Ефектът е в 10 от 10 години (×0.56, ст.откл 0.12) — един от най-
     стабилните в целия модел. Хората вече са пристигнали където празнуват,
     магазините затварят рано, трафикът изчезва. */
  if(m === 0){                                  // януари
    if(d === 1) return 0.547;
    if(d === 2) return 0.774;
    return 1.0;
  }
  if(m !== 11) return 1.0;                      // декември
  if(d === 31) return 0.561;
  if(d >= 27)  return 0.85;                     // 27-30: затишие след Коледа
  if(d >= 24)  return 1.0;
  if(d === 23) return 1.35;                     // най-рисковият ден в годината
  if(d >= 21)  return 1.22;
  if(d >= 19)  return 1.18;
  if(d >= 16)  return 1.12;
  return 1.0;
}
function iceEffect(tmin, precip){
  if(tmin==null) return 1.0;
  if(tmin <= 0 && precip > 0.5) return 1.18;
  if(tmin <= -3) return 1.06;
  if(tmin <= 0)  return 1.03;
  return 1.0;
}
function windEffect(kmh){
  if(kmh==null) return 1.0;
  return kmh>=60?1.09 : kmh>=40?1.04 : 1.0;
}
function fogEffect(vis){
  if(vis==null) return 1.0;
  return vis<200?1.22 : vis<500?1.12 : vis<1000?1.05 : 1.0;
}
/* Празник ×0.809 — значително по-спокойно. Денят СЛЕД празник е -11.5%.
   Денят ПРЕДИ празник няма ефект (1.0005, CI пресича 1). */
function holidayEffect(st){ return st===2 ? 0.809 : 1.0; }

/* ---------- фактори, ПРОВЕРЕНИ и ОТПАДНАЛИ ----------
   Kp геомагнитен : r=-0.023; нищо при закъснения 0–7 дни
   Лунна фаза     : проверена в BG, UK и US — фазите се разминават
   Δ налягане     : r=-0.060
   Жега/обезводняване, витамин D, заслепяване при залез, планетарни цикли
   Всички остават видими в интерфейса, но не участват в оценката.        */

function scoreFrom(mult, cuts){
  let s = 1;
  for(const c of cuts) if(mult >= c) s++;
  return Math.max(1, Math.min(10, s));
}

function calcRisk(env, date, opts){
  const dow = date.getDay(), mon = date.getMonth()+1;
  const hs  = holidayStatus(date);
  const rain = env.rain ?? 0, snow = env.snow ?? 0;
  const reg  = (opts && opts.noRegime) ? {mult:1.0, active:false} : regimeEffect(mon);

  const common = iceEffect(env.tmin, rain+snow) * windEffect(env.wind)
               * fogEffect(env.vis) * holidayEffect(hs)
               * xmasEffect(date)
               * amplitudeEffect(env.tmin, env.tmax, env.sun, mon)
               * afterHoliday(date) * reg.mult;

  const carMult  = rainEffect(rain,snow) * cloudEffect(env.sun)
                 * WD_FACTOR[dow] * MO_FACTOR[mon-1] * common;
  const harmMult = harmRain(rain,snow)  * harmCloud(env.sun)
                 * H_WD[dow] * H_MO[mon-1] * common;

  return {
    carScore : scoreFrom(carMult,  RISK_CUTS),
    harmScore: scoreFrom(harmMult, H_CUTS),
    carMult, harmMult, hs, regime: reg
  };
}

function afterHoliday(date){
  const prev = new Date(date.getTime() - 86400000);
  return holidayStatus(prev) === 2 ? 0.885 : 1.0;
}

/* Режим: остатъчната аварийност се влачи ~седмица напред. Потвърдено в
   три държави, включително върху американските смъртни катастрофи.
   Причината е неизвестна. Изисква пресни данни от МВР; без тях — неутрален. */
function regimeEffect(mon){
  const off = {mult:1.0, active:false, n:0};
  const days = (S.mvrDays||[]).filter(d=>d && d.date && mvTotal(d)!=null)
    .sort((a,b)=>b.date.localeCompare(a.date)).slice(0,5);
  if(days.length < 3) return off;
  const logs = [];
  for(const e of days){
    const dt = new Date(e.date+'T12:00:00');
    if((Date.now()-dt)/86400000 > 7) continue;
    const exp = baseDaily() * WD_FACTOR[dt.getDay()] * MO_FACTOR[dt.getMonth()];
    const act = mvTotal(e);
    if(!exp || !act || act<=0) continue;
    logs.push(Math.log(act/exp));
  }
  if(logs.length < 3) return off;
  const avg = logs.reduce((a,b)=>a+b,0)/logs.length;
  const w = REG_W[mon-1];
  return {mult: Math.max(0.85, Math.min(1.18, Math.exp(w*avg))),
          active:true, n:logs.length, w};
}

/* `ptp` НЕ се ползва: полето смесва национални тежки ПТП (16–33/ден) с
   единични областни заглавия ("в Разградско три катастрофи" → 3).
   `injured` идва от едно и също изречение, покритие 80%, медиана ~27. */
function mvTotal(m){
  if(!m) return null;
  if(m.sofia_light != null) return m.sofia_light;
  if(m.injured != null) return m.injured;
  if(m.light != null || m.serious != null) return (m.light||0)+(m.serious||0);
  return null;
}
function baseDaily(){ return (S.historical && S.historical.base_daily) || 27; }

/* Български празници, включително подвижните великденски дни */
const EASTER = {2024:'05-05',2025:'04-20',2026:'04-12',2027:'05-02',2028:'04-16'};
function holidayStatus(date){
  const y = date.getFullYear();
  const md = String(date.getMonth()+1).padStart(2,'0')+'-'+String(date.getDate()).padStart(2,'0');
  const fixed = ['01-01','03-03','05-01','05-06','05-24','09-06','09-22','12-24','12-25','12-26'];
  if(fixed.includes(md)) return 2;
  if(EASTER[y]){
    const e = new Date(y+'-'+EASTER[y]+'T12:00:00');
    for(let o=-2;o<=1;o++){
      const d2 = new Date(e.getTime()+o*86400000);
      if(d2.getMonth()===date.getMonth() && d2.getDate()===date.getDate()) return 2;
    }
  }
  return 0;
}

const SCORE_COLORS = ['#22c55e','#4ade80','#a3e635','#d9e021','#fbbf24',
                      '#fb923c','#f97316','#f2621f','#ef4444','#dc2626'];
const scoreColor = s => SCORE_COLORS[Math.max(1,Math.min(10,s))-1];
