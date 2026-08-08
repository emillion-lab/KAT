/* ═══ История, проверка и методология ═══ */
function renderHistory(k){
  const bg = BG();
  const wdN = bg?['Нд','Пн','Вт','Ср','Чт','Пт','Сб']:['Su','Mo','Tu','We','Th','Fr','Sa'];
  const moN = bg?['Яну','Фев','Мар','Апр','Май','Юни','Юли','Авг','Сеп','Окт','Ное','Дек']
               :['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const bar=(v,mx,col)=>`<div class="hb"><div style="width:${v/mx*100}%;background:${col}"></div></div>`;
  const wdMax=Math.max(...WD_FACTOR,...H_WD), moMax=Math.max(...MO_FACTOR,...H_MO);

  const wdRows = [1,2,3,4,5,6,0].map(d=>`<tr>
    <td>${wdN[d]}</td>
    <td>${bar(WD_FACTOR[d],wdMax,'#5fb3ff')}</td><td class="n">${WD_FACTOR[d].toFixed(2)}</td>
    <td>${bar(H_WD[d],wdMax,'#f97316')}</td><td class="n">${H_WD[d].toFixed(2)}</td></tr>`).join('');
  const moRows = MO_FACTOR.map((v,i)=>`<tr>
    <td>${moN[i]}</td>
    <td>${bar(v,moMax,'#5fb3ff')}</td><td class="n">${v.toFixed(2)}</td>
    <td>${bar(H_MO[i],moMax,'#f97316')}</td><td class="n">${H_MO[i].toFixed(2)}</td></tr>`).join('');

  $('history').innerHTML = `
  <div class="card">
    <div class="ct">📊 ${bg?'КОЕФИЦИЕНТИ НА МОДЕЛА':'MODEL COEFFICIENTS'}</div>
    <div class="legend"><span style="color:#5fb3ff">■</span> ${k.car}
      &nbsp;&nbsp;<span style="color:#f97316">■</span> ${k.harm}
      &nbsp;&nbsp;<span class="dim">(1.00 = ${bg?'средно':'average'})</span></div>
    <table class="ht"><tbody>${wdRows}</tbody></table>
    <div class="sub">${bg?'ПО МЕСЕЦ':'BY MONTH'}</div>
    <table class="ht"><tbody>${moRows}</tbody></table>
    <div class="note">${bg
      ? 'Август има само +10% повече ПТП, но <b>+32% повече пострадали</b>. Февруари е обратното. Оттам двете отделни скали.'
      : 'August has only +10% more crashes but <b>+32% more casualties</b>. February is the reverse. Hence the two scales.'}</div>
  </div>
  ${validation(bg)}
  ${methodology(bg)}`;
}

/* Проверка върху цели месеци от чистата справка на МВР, които моделът не е
   виждал при калибрирането.

   Живият поток НЕ се ползва за проверка. Ежедневната справка се извлича от
   новинарски заглавия и понякога хваща областни числа вместо национални
   ("в Разградско три катастрофи"). За 30 дни това дава четири дни със
   стойности 2, 2, 3 — възможни са, но при базова честота около 1%, а не 14%.
   Не могат да се отличат ден по ден, а включени в сметката вдигат грешката
   до 33% и правят модела да изглежда счупен, когато проблемът е в данните. */
function validation(bg){
  if(!bg) return `<div class="card"><div class="ct">✅ OUT-OF-SAMPLE VALIDATION</div>
    <div class="mrow">November 2025 — mean error <b>11.1%</b>, correlation <b>0.84</b></div>
    <div class="mrow">December 2025 — mean error <b>10.5%</b>, systematic bias <b>−0.3%</b>, 25 of 31 days within ±15%</div>
    <div class="note">Bias near zero is the number that matters: the model does not err in one direction.</div></div>`;
  return `<div class="card">
    <div class="ct">✅ ПРОВЕРКА ВЪРХУ НЕВИЖДАНИ МЕСЕЦИ</div>
    <div class="mrow"><b>Ноември 2025</b> — средна грешка <b>11.1%</b>, корелация модел↔реалност <b>0.84</b>, 22 от 30 дни в рамките на ±15%</div>
    <div class="mrow"><b>Декември 2025</b> — средна грешка <b>10.5%</b>, систематично отклонение <b>−0.3%</b>, 25 от 31 дни в рамките на ±15%</div>
    <div class="mrow">Предколедната седмица, изведена от десетте години, се потвърди на живо:
      19 дек <b>+4%</b>, 22 дек <b>+2%</b>, 23 дек <b>+1%</b> разлика от предсказаното.</div>
    <div class="mrow">Новогодишната яма също: 31 декември е ×0.56 от обичайното — <b>в 10 от 10 години</b>.</div>
    <div class="note">Отклонението близо до нула е важното число: моделът не греши систематично в една посока.
      Средна грешка от ~11% е нормална — една тежка катастрофа мести дневния брой повече от всички фактори заедно.
      <br><br><span class="dim">Проверката ползва официалната справка на МВР. Ежедневният поток от новинарски заглавия
      не се използва за оценка на точността: той понякога съобщава числа за една област вместо за страната,
      което не може да се отличи ден по ден.</span></div>
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
    ${h('LIMITS')}
    ${row('Explains <b>44%</b> of daily variation out of sample. Shows a relative score, not a crash count.')}
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
    ${row('▸ <b>Геомагнитни бури</b> — без ефект при закъснение от 0 до 7 дни (r = −0.02)')}
    ${row('▸ <b>Лунни фази</b> — проверени в три държави; България и САЩ излизат почти в противофаза. Отхвърлено.')}
    ${row('▸ <b>Налягане</b>, <b>обезводняване в жега</b>, <b>витамин D</b>, <b>заслепяване при залез</b>, <b>планетарни цикли</b> — нито едно не оцелява след контрол за календара и времето')}
    ${h('КАКВО ЗНАЕМ, НО НЕ МОЖЕМ ДА ОБЯСНИМ')}
    ${row('Аварийността има <b>памет от около седмица</b>. Ако последните дни са били тежки, следващите също. Затихва наполовина за 5 дни.')}
    ${row('Потвърдена в трите държави, включително върху американските смъртни катастрофи, които не зависят от полицейско отчитане. През зимата е пет пъти по-силна, отколкото през лятото.')}
    ${row('<b>Причината е неизвестна.</b> Не е цикъл — няма период, който се повтаря. Отхвърлени обяснения: партидно вкарване на данни, остатъчно време, работен цикъл, медийно отразяване.')}
    ${h('ГРАНИЦИ НА ТОЧНОСТТА')}
    ${row('Моделът обяснява <b>44%</b> от дневната промяна, проверено върху години, които не е виждал.')}
    ${row('Затова показва <b>относителна</b> оценка, а не брой катастрофи. Скалата е стръмна: 10 се пада няколко пъти годишно, за да означава нещо.')}
    ${row('Коефициентите са от <b>национални</b> данни, приложени към София. Изчаква се справка по области.')}
  </div>`;
}
