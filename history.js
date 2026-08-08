/* ═══ История и методология ═══ */
function renderHistory(k){
  const bg = BG();
  const wdN = bg?['Нд','Пн','Вт','Ср','Чт','Пт','Сб']:['Su','Mo','Tu','We','Th','Fr','Sa'];
  const moN = bg?['Яну','Фев','Мар','Апр','Май','Юни','Юли','Авг','Сеп','Окт','Ное','Дек']
               :['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  /* Реални средни от 4018 дни (2015–2025, без 2020). Показваме какво е БИЛО,
     не колко греши моделът: точност не се обещава, затова и не се отчита. */
  const WD_REAL = [ [83,23.8,1.80],[112,26.4,1.71],[109,24.2,1.49],[106,23.8,1.27],
                    [110,25.4,1.50],[117,27.9,1.72],[95,25.5,1.78] ];   // getDay: 0=Нд
  const MO_REAL = [ [99,18.7,1.13],[95,18.7,1.12],[95,20.1,1.19],[100,21.8,1.28],
                    [102,25.3,1.55],[110,29.2,1.80],[113,31.9,2.06],[115,33.3,2.03],
                    [110,29.0,1.81],[110,26.1,1.76],[107,25.5,2.07],[102,23.4,1.51] ];

  const bar=(v,mx,col)=>`<div class="hb"><div style="width:${v/mx*100}%;background:${col}"></div></div>`;
  const cMax=Math.max(...WD_REAL.map(r=>r[0]),...MO_REAL.map(r=>r[0]));
  const hMax=Math.max(...WD_REAL.map(r=>r[1]),...MO_REAL.map(r=>r[1]));

  const row=(name,r)=>`<tr><td>${name}</td>
    <td>${bar(r[0],cMax,'#5fb3ff')}</td><td class="n">${r[0]}</td>
    <td>${bar(r[1],hMax,'#f97316')}</td><td class="n">${r[1].toFixed(0)}</td>
    <td class="n" style="color:#ef4444">${r[2].toFixed(2)}</td></tr>`;

  const wdRows=[1,2,3,4,5,6,0].map(d=>row(wdN[d],WD_REAL[d])).join('');
  const moRows=MO_REAL.map((r,i)=>row(moN[i],r)).join('');

  $('history').innerHTML = `
  <div class="card">
    <div class="ct">📊 ${bg?'КАКВО Е БИЛО — СРЕДНО НА ДЕН':'WHAT ACTUALLY HAPPENED — DAILY AVERAGE'}</div>
    <div class="legend">
      <span style="color:#5fb3ff">■</span> ${bg?'ПТП':'crashes'}
      &nbsp;&nbsp;<span style="color:#f97316">■</span> ${bg?'пострадали':'casualties'}
      &nbsp;&nbsp;<span style="color:#ef4444">■</span> ${bg?'загинали':'deaths'}
      <br><span class="dim">${bg?'национално, 4018 дни (2015–2025)':'national, 4018 days'}</span>
    </div>
    <table class="ht"><tbody>${wdRows}</tbody></table>
    <div class="note">${bg
      ? '<b>Неделя има най-малко катастрофи, но най-много загинали</b> — 83 ПТП и 1.80 смъртни случая на ден. Петък е обратното: 117 ПТП, но 1.72 загинали. Най-безопасен е сряда с 1.27.'
      : '<b>Sunday has the fewest crashes but the most deaths</b> — 83 crashes, 1.80 deaths a day. Friday is the reverse.'}</div>
    <div class="sub">${bg?'ПО МЕСЕЦ':'BY MONTH'}</div>
    <table class="ht"><tbody>${moRows}</tbody></table>
    <div class="note">${bg
      ? 'Август има 115 ПТП на ден срещу 95 през февруари — с 20% повече. Но пострадалите скачат от 18.7 на <b>33.3</b>, тоест почти двойно. Затова двете скали се разминават най-силно през лятото.'
      : 'August averages 115 crashes vs 95 in February, but casualties jump from 18.7 to 33.3 — nearly double.'}</div>
  </div>
  ${extremes(bg)}
  ${methodology(bg)}`;
}

function extremes(bg){
  if(!bg) return '';
  return `<div class="card">
    <div class="ct">📌 КРАЙНИ СТОЙНОСТИ ЗА 10 ГОДИНИ</div>
    <div class="mrow">Най-натоварен ден: <b>11 октомври 2016</b> — 257 ПТП за денонощие</div>
    <div class="mrow">Най-тежък ден: <b>23 ноември 2021</b> — 47 загинали (автобусната катастрофа на АМ „Струма“)</div>
    <div class="mrow">Най-спокоен ден: <b>7 март 2021</b> — 27 ПТП</div>
    <div class="mrow">Най-рисковата дата в годината: <b>23 декември</b> — с ~35% над обичайното за деня</div>
    <div class="mrow">Най-спокойната: <b>31 декември и 1 януари</b> — наполовина под обичайното, в 10 от 10 години</div>
  </div>`;
}

function methodology(bg){
  const row = t => `<div class="mrow">${t}</div>`;
  const h   = t => `<div class="mh">${t}</div>`;
  if(!bg) return `<div class="card"><div class="ct">🔬 HOW THE MODEL WAS BUILT</div>
    ${h('DATA')}
    ${row('▸ <b>Bulgaria</b> — 4018 days of crashes, deaths and injuries (MVR 2015–2025)')}
    ${row('▸ <b>United Kingdom</b> — 1826 days, full STATS19 register')}
    ${row('▸ <b>United States</b> — 186,398 fatal crashes with exact dates (NHTSA FARS)')}
    ${row('▸ <b>Germany</b> — 269,048 crashes with hourly detail (Unfallatlas)')}
    ${h('TESTED AND DROPPED')}
    ${row('Geomagnetic storms · lunar phase · pressure · heat dehydration · vitamin D · sunset glare · planetary cycles. None survive controlling for calendar and weather.')}
    ${h('KNOWN BUT UNEXPLAINED')}
    ${row('Crash rates carry about a week of memory, confirmed in all three countries. <b>The cause is unknown</b>, and it is not a cycle.')}
    ${h('WHAT THIS IS NOT')}
    ${row('Not a crash-count forecast. It shows how a day compares with the usual, based on what happened on similar days over ten years.')}
  </div>`;
  return `<div class="card">
    <div class="ct">🔬 КАК Е ПОСТРОЕН МОДЕЛЪТ</div>
    ${h('ОБРАБОТЕНИ ДАННИ')}
    ${row('▸ <b>България</b> — 4018 дни ежедневни ПТП, загинали и ранени (МВР, 2015–2025)')}
    ${row('▸ <b>Великобритания</b> — 1826 дни, пълен регистър STATS19')}
    ${row('▸ <b>САЩ</b> — 186 398 смъртни катастрофи с точна дата (NHTSA FARS)')}
    ${row('▸ <b>Германия</b> — 269 048 катастрофи с часова разбивка (Unfallatlas)')}
    ${row('▸ Метео от Open-Meteo · геомагнитен индекс от GFZ Потсдам')}
    ${h('КАКВО ВЛИЗА В ОЦЕНКАТА')}
    ${row('Валеж и сняг · облачност · ден от седмицата · месец · лед · вятър · празници · предколеден трафик · новогодишна яма · денонощна температурна амплитуда')}
    ${h('КАКВО ПРОВЕРИХМЕ И ОТПАДНА')}
    ${row('▸ <b>Геомагнитни бури</b> — без ефект при закъснение от 0 до 7 дни')}
    ${row('▸ <b>Лунни фази</b> — проверени в три държави; България и САЩ излизат почти в противофаза. Отхвърлено.')}
    ${row('▸ <b>Налягане</b>, <b>обезводняване в жега</b>, <b>витамин D</b>, <b>заслепяване при залез</b>, <b>планетарни цикли</b> — нито едно не оцелява след контрол за календара и времето')}
    ${h('КАКВО ЗНАЕМ, НО НЕ МОЖЕМ ДА ОБЯСНИМ')}
    ${row('Аварийността има <b>памет от около седмица</b>. Ако последните дни са били тежки, следващите също. Затихва наполовина за 5 дни.')}
    ${row('Потвърдена в трите държави, включително върху американските смъртни катастрофи, които не зависят от полицейско отчитане. През зимата е пет пъти по-силна, отколкото през лятото.')}
    ${row('<b>Причината е неизвестна.</b> Не е цикъл — няма период, който се повтаря. Отхвърлени обяснения: партидно вкарване на данни, остатъчно време, работен цикъл, медийно отразяване.')}
    ${h('КАКВО НЕ Е ТОВА')}
    ${row('<b>Не е прогноза за брой катастрофи.</b> Показва как днешният ден се сравнява с обичайното — на базата на това какво се е случвало в подобни дни през последните десет години.')}
    ${row('Един обърнат тир мести дневния брой повече от всички фактори заедно. Затова не се дават числа, а сравнение.')}
    ${row('Коефициентите са от <b>национални</b> данни, приложени към София. Изчаква се справка по области.')}
  </div>`;
}
