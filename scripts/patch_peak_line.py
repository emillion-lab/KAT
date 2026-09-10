# -*- coding: utf-8 -*-
# KAT · FT-PEAKLINE-V1
#
# Добавя един ред под оценката на деня: кога иде следващият пиков прозорец
# и каква ще е оценката тогава. Числата идват от mvr-proxy /risk — същия
# източник, който ползват BAK и шофьорското приложение, за да няма втора
# сметка в браузъра. Прозорците (07–09, 16–19, 22–04) са фиксирани и НЕ са
# калибрирани върху данните на МВР — те са дневни. Затова ред, не графика.
#
# Идемпотентен: втори пуск не прави нищо.
import io, sys

p = 'index.html'
s = io.open(p, encoding='utf-8').read()
n0 = len(s)

if 'FT-PEAKLINE-V1' in s:
    print('SKIP: FT-PEAKLINE-V1 вече е приложен'); sys.exit(0)

OLD1 = '      <div id="today-scores"></div>'
NEW1 = '''      <div id="today-scores"></div>
      <!-- FT-PEAKLINE-V1 -->
      <div class="ssub" id="today-peak" style="margin:12px 0 0;font-family:'Space Mono',monospace"></div>'''

OLD2 = 'boot();'
NEW2 = '''boot();

/* FT-PEAKLINE-V1 — следващият пиков прозорец.
   Идва наготово от mvr-proxy /risk (полето next_peak), за да не се смята
   часовата логика на второ място. Ако worker-ът мълчи, редът просто липсва. */
(function(){
  var el = document.getElementById('today-peak');
  if(!el) return;
  fetch('https://mvr-proxy.mihov-emil.workers.dev/risk')
    .then(function(r){ return r.json(); })
    .then(function(d){
      if(!d || !d.ok || !d.next_peak) return;
      var p = d.next_peak;
      var hh = function(h){ return (h < 10 ? '0' : '') + h + ':00'; };
      var bg = (typeof lang === 'undefined') || lang === 'bg';
      var win = hh(p.from) + '\\u2013' + hh(p.to);
      var sc = '\\uD83D\\uDE97 ' + p.score + '/10 \\u00B7 \\uD83E\\uDDCD ' + p.harm_score + '/10';
      if (p.active) {
        el.textContent = bg
          ? '\\u23F0 Сега сме в ' + p.name + ' (' + win + ') — ' + sc
          : '\\u23F0 Peak window now (' + win + ') — car ' + p.score + '/10 \\u00B7 people ' + p.harm_score + '/10';
      } else {
        el.textContent = bg
          ? '\\u23F0 След ' + p.in_hours + ' ч — ' + p.name + ' ' + win + ' \\u2192 ' + sc
          : '\\u23F0 In ' + p.in_hours + 'h — peak ' + win + ' \\u2192 car ' + p.score + '/10 \\u00B7 people ' + p.harm_score + '/10';
      }
      el.title = bg
        ? 'Часовите прозорци са фиксирани, не са калибрирани върху данните на МВР — те са дневни.'
        : 'Hour windows are fixed, not calibrated on the daily MVR data.';
    })
    .catch(function(){});
})();'''

for i, (o, n) in enumerate([(OLD1, NEW1), (OLD2, NEW2)], 1):
    c = s.count(o)
    if c != 1:
        print('FAIL: котва %d се среща %d пъти, очаква се 1' % (i, c)); sys.exit(1)
    s = s.replace(o, n)

io.open(p, 'w', encoding='utf-8').write(s)
print('OK  FT-PEAKLINE-V1 приложен  %d -> %d chars' % (n0, len(s)))
