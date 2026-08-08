/* ═══ KAT — интерфейс ═══ */
const S = { historical:null, mvrDays:[], wx:null, err:[] };
let lang = localStorage.getItem('kat-lang') || 'bg';
const $ = id => document.getElementById(id);
const BG = () => lang==='bg';

const L = {
  bg:{ car:'🚗 ЗА КОЛАТА', harm:'🧍 ЗА ЧОВЕКА',
       days:['неделя','понеделник','вторник','сряда','четвъртък','петък','събота'],
       lv:['Спокойно','Обичайно','Повишено внимание','Висок риск'],
       normal:'около обичайното',
       above:p=>`с ~${p}% над обичайното`,
       below:p=>`с ~${p}% под обичайното`,
       both:(c,h)=>`Ламарина ${c} · за хората ${h}`,
       gapCar:'Много удари, но по-леки — типично за сняг и дъжд. Пази ламарината.',
       gapHarm:'Малко катастрофи, но тежки. Спокойните дни са по-опасни за живота.',
       holiday:'🎉 празник' },
  en:{ car:'🚗 CARS', harm:'🧍 PEOPLE',
       days:['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'],
       lv:['Calm','Normal','Heightened','High risk'],
       normal:'about normal',
       above:p=>`~${p}% above normal`,
       below:p=>`~${p}% below normal`,
       both:(c,h)=>`Bodywork ${c} · people ${h}`,
       gapCar:'Many crashes, milder ones — typical of snow and rain.',
       gapHarm:'Few crashes, but severe. Quiet days are deadlier.',
       holiday:'🎉 holiday' }
};
const T = () => L[lang];
const lvOf = s => s<=3?0 : s<=6?1 : s<=8?2 : 3;

async function boot(){
  try{
    const [wx,hist] = await Promise.all([ fetchWeather(), fetchHistorical() ]);
    S.wx = wx; S.historical = hist;
  }catch(e){ S.err.push(e.message); }
  try{ S.mvrDays = await fetchMvr(); }catch(e){ S.err.push('МВР: '+e.message); }
  render();
}

async function fetchWeather(){
  const u = 'https://api.open-meteo.com/v1/forecast?latitude=42.6975&longitude=23.3242'
    + '&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,'
    + 'wind_speed_10m_max,weather_code,sunshine_duration,daylight_duration'
    + '&forecast_days=4&timezone=Europe%2FSofia';
  const r = await fetch(u);
  if(!r.ok) throw new Error('метео '+r.status);
  return r.json();
}
async function fetchHistorical(){
  try{ const r = await fetch('data/historical.json'); return r.ok ? r.json() : null; }
  catch{ return null; }
}
async function fetchMvr(){
  const r = await fetch('data/mvr_accidents.json');
  if(!r.ok) throw new Error(r.status);
  const j = await r.json();
  return j.days || [];
}

function envFor(i){
  const d = S.wx?.daily; if(!d) return {};
  const sun = (d.sunshine_duration?.[i]!=null && d.daylight_duration?.[i])
            ? d.sunshine_duration[i]/d.daylight_duration[i] : null;
  return { rain:d.precipitation_sum?.[i] ?? 0, snow:d.snowfall_sum?.[i] ?? 0,
           tmin:d.temperature_2m_min?.[i], tmax:d.temperature_2m_max?.[i],
           wind:d.wind_speed_10m_max?.[i], sun, vis:null };
}

function render(){
  const k = T();
  renderToday(k); renderForecast(k); renderHistory(k); renderMvr();
}

function scoreBlock(r, k){
  const gap = r.carScore - r.harmScore;
  const note = gap>=3 ? k.gapCar : gap<=-3 ? k.gapHarm : '';
  return `<div class="scales">
      <div><div class="slab">${k.car}</div>
        <div class="sval" style="color:${scoreColor(r.carScore)}">${r.carScore}/10</div></div>
      <div><div class="slab">${k.harm}</div>
        <div class="sval" style="color:${scoreColor(r.harmScore)}">${r.harmScore}/10</div></div>
    </div>
    ${note?`<div class="gapnote">${note}</div>`:''}`;
}

function relOne(mult, k){
  const p = Math.round((mult-1)*100);
  return Math.abs(p)<5 ? k.normal : p>0 ? k.above(p) : k.below(Math.abs(p));
}
/* Двете скали могат да сочат в различни посоки — затова се описват и двете.
   Едно число за "деня изобщо" би скрило точно разминаването, което търсим. */
function relText(r, k){
  return k.both(relOne(r.carMult,k), relOne(r.harmMult,k));
}

function renderToday(k){
  const now = new Date(), env = envFor(0);
  const r = calcRisk(env, now);
  const lv = lvOf(Math.max(r.carScore, r.harmScore));
  $('today-day').textContent = k.days[now.getDay()] + ' — ' + k.lv[lv];
  $('today-sub').textContent = relText(r, k) + (r.hs===2 ? ' · '+k.holiday : '');
  $('today-scores').innerHTML = scoreBlock(r, k);
  $('today-box').className = 'signal lv'+lv;
  renderFactors(env);
}

/* Показват се САМО факторите, които участват в оценката. Kp, лунна фаза и
   налягане бяха проверени и отпаднаха; държането им на екрана — дори
   приглушени — само задръстваше, без да казва нещо полезно. Какво е
   тествано и отхвърлено е описано в раздел „История“. */
function renderFactors(env){
  const k = T();
  const now = new Date();
  const cards = [
    ['🌧️', BG()?'ДЪЖД / СНЯГ':'RAIN / SNOW',
      (env.snow>0? env.snow.toFixed(1)+' cm' : (env.rain||0).toFixed(1)+' mm'),
      rainEffect(env.rain||0, env.snow||0)],
    ['☁️', BG()?'ОБЛАЧНОСТ':'CLOUD',
      env.sun!=null ? Math.round((1-env.sun)*100)+'%' : '—', cloudEffect(env.sun)],
    ['🌡️', BG()?'ТЕМП. И ЛЕД':'TEMP & ICE',
      env.tmin!=null ? env.tmin.toFixed(0)+'° / '+env.tmax.toFixed(0)+'°' : '—',
      iceEffect(env.tmin,(env.rain||0)+(env.snow||0))],
    ['💨', BG()?'ВЯТЪР':'WIND',
      env.wind!=null ? env.wind.toFixed(0)+' km/h' : '—', windEffect(env.wind)],
    ['📅', BG()?'ДЕН ОТ СЕДМИЦАТА':'WEEKDAY',
      k.days[now.getDay()].slice(0,3), WD_FACTOR[now.getDay()]],
    ['🗓️', BG()?'МЕСЕЦ':'MONTH',
      (BG()?['яну','фев','мар','апр','май','юни','юли','авг','сеп','окт','ное','дек']
           :['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])[now.getMonth()],
      MO_FACTOR[now.getMonth()]],
  ];
  $('factors').innerHTML = cards.map(([ic,t,v,f])=>{
    const pct = Math.max(4, Math.min(100, (f-0.75)/0.7*100));
    const col = f>=1.15?'#ef4444' : f>=1.05?'#fb923c' : f>=0.98?'#fbbf24' : '#22c55e';
    return `<div class="fc">
      <div class="fc-h"><span>${t}</span><span>${ic}</span></div>
      <div class="fc-v">${v}</div>
      <div class="fc-e">×${f.toFixed(2)}</div>
      <div class="fc-bw"><div class="fc-b" style="width:${pct}%;background:${col}"></div></div>
    </div>`;
  }).join('');
}

function renderForecast(k){
  const rows=[];
  for(let i=1;i<=3;i++){
    const d = new Date(); d.setDate(d.getDate()+i);
    const env = envFor(i), r = calcRisk(env, d);
    const lv = lvOf(Math.max(r.carScore,r.harmScore));
    rows.push(`<div class="fday">
      <div class="fd-h">
        <div><div class="fd-date">${d.toISOString().slice(0,10)}</div>
        <div class="fd-name">${k.days[d.getDay()]}</div></div>
        <span class="badge b${lv}">${k.lv[lv]}</span>
      </div>
      ${scoreBlock(r,k)}
      <div class="fd-sub">${relText(r,k)}</div>
      <div class="chips">
        <span>${env.snow>0?'❄️ '+env.snow.toFixed(1)+' cm':'🌧️ '+(env.rain||0).toFixed(1)+' mm'}</span>
        <span>🌡️ ${env.tmin?.toFixed(0)}–${env.tmax?.toFixed(0)}°</span>
        <span>💨 ${env.wind?.toFixed(0)} km/h</span>
        <span>☁️ ${env.sun!=null?Math.round((1-env.sun)*100)+'%':'—'}</span>
      </div></div>`);
  }
  $('forecast').innerHTML = rows.join('');
}

function renderMvr(){
  const el = $('mvr'); if(!el) return;
  const days = (S.mvrDays||[]).filter(d=>d?.date).sort((a,b)=>b.date.localeCompare(a.date));
  if(!days.length){ el.innerHTML=''; return; }
  const last = days[0];
  const age = Math.round((Date.now()-new Date(last.date+'T12:00'))/86400000);
  const reg = calcRisk(envFor(0), new Date()).regime;
  el.innerHTML = `<div class="mvr ${age<=2?'fresh':'stale'}">
    <span>📰 ${BG()?'Последни данни от МВР':'Latest MVR data'}: ${last.date} · ${age} ${BG()?'дни':'d'}</span>
    <span class="mvr-n">${last.injured!=null?last.injured+' '+(BG()?'ранени':'injured'):''}
      ${last.dead!=null?' · '+last.dead+' '+(BG()?'загинали':'dead'):''}</span>
    <span class="mvr-reg">${reg.active
      ? (BG()?'режим активен ×':'regime on ×')+reg.mult.toFixed(2)
      : (BG()?'режимът спи':'regime idle')}</span>
  </div>`;
}
