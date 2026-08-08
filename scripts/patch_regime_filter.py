"""Активира режимния член: филтър срещу регионалните заглавия в живия поток.

МВР публикува ту национална справка ("5 загинали и 24 ранени"), ту заглавие
за една област ("в Разградско три катастрофи"). Второто влиза в потока като
национално число и изкривява режима: 28 юли идва с 2 ранени при медиана 27.

Реален национален ден с под 8 ранени се случва в 1.4% от дните (2022–2025).
В потока такива стойности са 14%. Тоест почти всичките са грешни, а прагът
жертва много малко истински спокойни дни.

Прозорецът се разширява от 5 на 8 дни, защото филтърът маха около една пета
от дните, а режимът иска поне 3 точки. Осем дни са още в обхвата, докъдето
сигналът стига (полуживот 5 дни, изчезва към десетия).

Проверено срещу живия поток: 6 чисти дни от последните 8, режимът се
активира с ×0.981 при августовско тегло 0.12.
"""
import io

src = io.open('engine.js', encoding='utf-8').read()
n = 0

def rep(old, new):
    global src, n
    c = src.count(old)
    assert c == 1, 'MARKER x%d: %r' % (c, old[:80])
    src = src.replace(old, new); n += 1

rep("""function mvTotal(m){
  if(!m) return null;
  if(m.sofia_light != null) return m.sofia_light;
  if(m.injured != null) return m.injured;
  if(m.light != null || m.serious != null) return (m.light||0)+(m.serious||0);
  return null;
}""",
"""/* Прагът от 8 отсява регионалните заглавия — виж scripts/patch_regime_filter.py */
const MIN_PLAUSIBLE_INJURED = 8;

function mvTotal(m){
  if(!m) return null;
  if(m.sofia_light != null) return m.sofia_light;
  if(m.injured != null)
    return m.injured >= MIN_PLAUSIBLE_INJURED ? m.injured : null;
  if(m.light != null || m.serious != null){
    const s = (m.light||0)+(m.serious||0);
    return s >= MIN_PLAUSIBLE_INJURED ? s : null;
  }
  return null;
}""")

rep("""  const days = (S.mvrDays||[]).filter(d=>d && d.date && mvTotal(d)!=null)
    .sort((a,b)=>b.date.localeCompare(a.date)).slice(0,5);
  if(days.length < 3) return off;""",
"""  /* Прозорец 8 дни: филтърът маха около една пета от дните, а режимът иска
     поне 3 точки. Осемте дни са още в обхвата на сигнала. */
  const days = (S.mvrDays||[]).filter(d=>d && d.date && mvTotal(d)!=null)
    .sort((a,b)=>b.date.localeCompare(a.date)).slice(0,8);
  if(days.length < 3) return off;""")

rep("    if((Date.now()-dt)/86400000 > 7) continue;",
    "    if((Date.now()-dt)/86400000 > 9) continue;")

io.open('engine.js', 'w', encoding='utf-8').write(src)
print('PATCHED %d blocks OK' % n)
