"""KAT v5 — align history with the model, drop count forecasts, quarantine
the disproven factors, and document what was actually tested.

Three inconsistencies v4 left behind:

1. The History tab still drew risk_by_weekday / risk_by_month from
   data/historical.json — the pre-recalibration numbers (Sat 1.24, Mon 0.92),
   which directly contradict what the engine now uses (Sat 0.905, Mon 1.074).
   A dashboard disagreeing with its own model is worse than no dashboard.

2. The 3-day tab still printed "8.4 очаквани ПТП". Same objection as on the
   main tab: out-of-sample R2 is 0.44, so a point estimate is a promise the
   model cannot keep. Replaced with the two scales.

3. Kp, moon and pressure still rendered as ordinary factor cards with coloured
   bars, so they read as contributors. They stay — showing that they were
   checked is worth more than hiding them — but under an explicit heading.
"""
import io

src = io.open('index.html', encoding='utf-8').read()
count = 0

def rep(old, new):
    global src, count
    c = src.count(old)
    assert c == 1, 'MARKER x%d: %r' % (c, old[:90])
    src = src.replace(old, new); count += 1


# ═══════════════ 1. HISTORY: use the engine's own coefficients ═══════════════
rep("""  const wd=h.risk_by_weekday||{}, md=h.risk_by_month||{}, avg=h.sofia_daily_avg||{};""",
"""  /* Историята вече чете СЪЩИТЕ коефициенти, които моделът ползва.
     Старият historical.json носеше предкалибрационните стойности
     (Сб 1.24, Пн 0.92) и противоречеше на самия двигател. */
  const avg=h.sofia_daily_avg||{};
  const wd={}, md={};
  const _wdOrder=[1,2,3,4,5,6,0];              // Пн..Нд → getDay()
  _wdOrder.forEach((g,i)=>{ wd['k'+i]=WD_FACTOR[g]; });
  for(let m=0;m<12;m++) md['k'+m]=MO_FACTOR[m];""")

# ═══════════════ 2. HISTORY: heading, and the methodology block ══════════════
rep("""      🗄️ ${bg?'МНОГОГОДИШЕН АНАЛИЗ — НСИ/МВР 2015–2024':'LONG-TERM ANALYSIS — NSI/MVR 2015–2024'}""",
"""      🗄️ ${bg?'МНОГОГОДИШЕН АНАЛИЗ — МВР 2015–2025':'LONG-TERM ANALYSIS — MVR 2015–2025'}""")

rep("""  const obsBg=[
    `<b>${wdNames[topWd]}</b> е най-рисковият ден: +${Math.round((wdMax-1)*100)}% над средното. Най-спокоен е <b>${wdNames[minWd]}</b> (${Math.round((wdVals[minWd]-1)*100)}%).`,
    `Сезонен пик: <b>${moNames[topMo]}</b> (+${Math.round((moMax-1)*100)}%) — отпускарски трафик и умора.`,
    `София-град средно на денонощие: <b>${avg.light}</b> леки · <b>${avg.serious}</b> тежки ПТП · <b>${avg.injured}</b> ранени.`,
    `Тези базови криви (ден · месец) са основата на модела; средата (космическо време, валежи, лед, вятър, празници) я модулира.`
  ];""",
"""  const obsBg=[
    `<b>${wdNames[topWd]}</b> е най-рисковият ден: +${Math.round((wdMax-1)*100)}% над средното. Най-спокоен е <b>${wdNames[minWd]}</b> (${Math.round((wdVals[minWd]-1)*100)}%).`,
    `Сезонен пик: <b>${moNames[topMo]}</b> (+${Math.round((moMax-1)*100)}%).`,
    `Август има само +10% повече ПТП, но <b>+32% повече пострадали</b> — оттам двете отделни скали.`,
    `Тези криви (ден · месец) са основата; валеж, сняг, облачност, лед, вятър и празници я модулират.`
  ];""")

# ═══════════════ 3. METHODOLOGY block appended to the History tab ════════════
rep("""      ${bg?'НАБЛЮДЕНИЯ':'OBSERVATIONS'}</div>
      ${obs}
    </div>
  </div>`;
}""",
"""      ${bg?'НАБЛЮДЕНИЯ':'OBSERVATIONS'}</div>
      ${obs}
    </div>
  </div>
  ${methodologyBlock(bg)}`;
}

/* ═══ Как е построен моделът: какво влезе, какво отпадна и какво не знаем ═══
   Формулирано пестеливо: подробностите правят впечатление на несериозност,
   а премълчаването на отхвърленото прави впечатление на нечестност. */
function methodologyBlock(bg){
  const S_=(t)=>`<div style="padding:7px 0;border-bottom:1px dashed var(--border);font-size:.78rem;line-height:1.55">${t}</div>`;
  const head=(t)=>`<div style="font-family:'Space Mono',monospace;font-size:.68rem;letter-spacing:.08em;color:var(--cyan);margin:14px 0 8px">${t}</div>`;
  if(bg) return `
  <div style="background:var(--surf);border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:12px">
    <div style="font-family:'Space Mono',monospace;font-size:.7rem;letter-spacing:.08em;color:var(--cyan);margin-bottom:4px">
      🔬 КАК Е ПОСТРОЕН МОДЕЛЪТ
    </div>
    ${head('ОБРАБОТЕНИ ДАННИ')}
    ${S_('▸ <b>България</b> — 4018 дни ежедневни ПТП, загинали и ранени (МВР, 2015–2025).')}
    ${S_('▸ <b>Великобритания</b> — 1826 дни, пълен регистър STATS19 (2021–2025).')}
    ${S_('▸ <b>САЩ</b> — 186 398 смъртни катастрофи с точна дата (NHTSA FARS).')}
    ${S_('▸ <b>Германия</b> — 269 048 катастрофи с часова разбивка (Unfallatlas 2023).')}
    ${S_('▸ Метео за всяка дата от Open-Meteo; геомагнитен индекс Kp от GFZ Потсдам.')}
    ${head('КАКВО ВЛИЗА В ОЦЕНКАТА')}
    ${S_('Валеж и снеговалеж · облачност · ден от седмицата · месец · заледяване · вятър · празници · предколеден трафик · денонощна температурна амплитуда.')}
    ${head('КАКВО ПРОВЕРИХМЕ И ОТПАДНА')}
    ${S_('▸ <b>Геомагнитни бури</b> — без ефект при никакво закъснение от 0 до 7 дни.')}
    ${S_('▸ <b>Лунни фази</b> — проверени в три държави. Фазите на сигнала се разминават: България и САЩ са почти в противофаза. Отхвърлено.')}
    ${S_('▸ <b>Атмосферно налягане</b>, <b>обезводняване в жега</b>, <b>витамин D</b>, <b>заслепяване при залез</b>, <b>планетарни цикли</b> — нито едно не оцелява след контрол за календара и времето.')}
    ${S_('Оставени са като информация на началната страница, за да се вижда, че са били проверени — но не участват в оценката.')}
    ${head('КАКВО ЗНАЕМ, НО НЕ МОЖЕМ ДА ОБЯСНИМ')}
    ${S_('Аварийността има <b>памет от около седмица</b>: ако последните дни са били тежки, следващите също. Ефектът затихва наполовина за 5 дни и изчезва към десетия.')}
    ${S_('Потвърден е и в трите държави, включително върху американските смъртни катастрофи, които не зависят от полицейско отчитане. През зимата е пет пъти по-силен, отколкото през лятото.')}
    ${S_('<b>Причината е неизвестна.</b> Не е цикъл — няма период, който да се повтаря. Проверени и отхвърлени: партидно вкарване на данни, остатъчно време, работен цикъл, медийно отразяване.')}
    ${head('ГРАНИЦИ НА ТОЧНОСТТА')}
    ${S_('Моделът обяснява <b>44%</b> от дневната промяна, проверено върху години, които не е виждал. Останалото е непредвидимо — една тежка катастрофа мести числото повече от всички фактори заедно.')}
    ${S_('Затова се показва <b>относителна</b> оценка, а не брой катастрофи. Скалата 1–10 е стръмна: 10 се пада 4–8 пъти годишно, за да означава нещо.')}
    ${S_('Коефициентите са изведени от <b>национални</b> данни и приложени към София. Изчаква се справка по области.')}
  </div>`;
  return `
  <div style="background:var(--surf);border:1px solid var(--border);border-radius:10px;padding:14px;margin-bottom:12px">
    <div style="font-family:'Space Mono',monospace;font-size:.7rem;letter-spacing:.08em;color:var(--cyan);margin-bottom:4px">
      🔬 HOW THE MODEL WAS BUILT
    </div>
    ${head('DATA PROCESSED')}
    ${S_('▸ <b>Bulgaria</b> — 4018 days of daily crashes, deaths and injuries (MVR, 2015–2025).')}
    ${S_('▸ <b>United Kingdom</b> — 1826 days, full STATS19 register (2021–2025).')}
    ${S_('▸ <b>United States</b> — 186,398 fatal crashes with exact dates (NHTSA FARS).')}
    ${S_('▸ <b>Germany</b> — 269,048 crashes with hourly detail (Unfallatlas 2023).')}
    ${head('WHAT COUNTS')}
    ${S_('Rain and snow · cloud cover · weekday · month · ice · wind · holidays · pre-Christmas traffic · diurnal temperature range.')}
    ${head('TESTED AND DROPPED')}
    ${S_('▸ <b>Geomagnetic storms</b> — no effect at any lag from 0 to 7 days.')}
    ${S_('▸ <b>Lunar phase</b> — tested in three countries; Bulgaria and the US come out nearly in antiphase. Rejected.')}
    ${S_('▸ <b>Pressure</b>, <b>heat dehydration</b>, <b>vitamin D</b>, <b>sunset glare</b>, <b>planetary cycles</b> — none survive controlling for calendar and weather.')}
    ${head('KNOWN BUT UNEXPLAINED')}
    ${S_('Crash rates carry about a week of <b>memory</b>. Confirmed in all three countries, including US fatal crashes, which do not depend on police reporting. Five times stronger in winter. <b>The cause is unknown</b>, and it is not a cycle.')}
    ${head('LIMITS')}
    ${S_('The model explains <b>44%</b> of daily variation out of sample. It therefore shows a relative score, not a crash count.')}
  </div>`;
}""")

# ═══════════════ 4. FORECAST TAB: two scales instead of a count ══════════════
rep("""      <div style="display:flex;align-items:baseline;gap:8px;margin:8px 0 4px">
        <span style="font-family:'Space Mono',monospace;font-size:1.7rem;font-weight:700;color:${lvColors[l]}">${fc.r.expected}</span>
        <span style="font-size:.75rem;color:var(--dim)">${k.ptpLabel}</span>
      </div>""",
"""      <div style="display:flex;gap:22px;margin:10px 0 6px">
        <div>
          <div style="font-size:.62rem;letter-spacing:.06em;color:var(--dim)">${lang==='bg'?'🚗 ЗА КОЛАТА':'🚗 CARS'}</div>
          <div style="font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;color:${scoreColor(fc.r.riskScore)}">${fc.r.riskScore}/10</div>
        </div>
        <div>
          <div style="font-size:.62rem;letter-spacing:.06em;color:var(--dim)">${lang==='bg'?'🧍 ЗА ЧОВЕКА':'🧍 PEOPLE'}</div>
          <div style="font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;color:${scoreColor(fc.r.harmScore)}">${fc.r.harmScore}/10</div>
        </div>
      </div>""")

rep("""        <span class="badge ${lvClass[l]}">${k.riskDescs[l]} · ${fc.r.riskScore}/10</span>""",
"""        <span class="badge ${lvClass[l]}">${k.riskDescs[l]}</span>""")

# ═══════════════ 5. QUARANTINE the disproven factor cards ════════════════════
rep("""  document.getElementById('sl-diverge').textContent = note;""",
"""  document.getElementById('sl-diverge').textContent = note;
  markObservedOnly();""")

rep("""function methodologyBlock(bg){""",
"""/* Kp, Луна и Налягане остават видими — че са проверени, е част от работата —
   но не бива да изглеждат като фактори. Обезцветяваме лентите и слагаме
   изричен надпис над групата им. */
function markObservedOnly(){
  const bg = lang==='bg';
  const labels = bg ? ['КОС. БУРИ','ЛУНА','НАЛЯГАНЕ'] : ['SPACE WX','MOON','PRESSURE'];
  let first=null;
  document.querySelectorAll('.factor').forEach(el=>{
    const t=(el.textContent||'').toUpperCase();
    if(labels.some(l=>t.includes(l))){
      el.style.opacity='0.55';
      el.style.borderTopColor='var(--border)';
      const bar=el.querySelector('.factor-bar,.bar,[class*=bar]');
      if(bar) bar.style.display='none';
      if(!first) first=el;
    }
  });
  if(first && !document.getElementById('observed-note')){
    const n=document.createElement('div');
    n.id='observed-note';
    n.style.cssText='grid-column:1/-1;font-size:.68rem;color:var(--dim);margin:10px 0 2px;letter-spacing:.04em';
    n.textContent = bg
      ? '▾ Наблюдавани, без доказано влияние — не участват в оценката'
      : '▾ Monitored, no proven effect — not used in the score';
    first.parentNode.insertBefore(n, first);
  }
}

function methodologyBlock(bg){""")

io.open('index.html','w',encoding='utf-8').write(src)
print('PATCHED %d blocks OK' % count)
