"""KAT v6 — repair the History tab.

v5 replaced the history coefficients with the engine's own, but wrote them
under keys 'k0'..'k6' while the renderer looks up '0_monday'..'6_sunday' and
'1_january'.. — so every value fell back to 1.00 and the observations line
read "+0% above average". Same values, correct key names.

Also removes two panels that now contradict the methodology text directly
above them: the "Kp (inverted U) vs real data" curve and the correlation
strip showing r=0.30 for Kp. That r is the raw correlation with no control
for weekday, month or weather; once those are held constant it collapses to
-0.023. Leaving it on screen next to "geomagnetic storms were dropped" is
the one thing worse than either statement alone.

Replaced with a backtest: the last 30 days, model score against what actually
happened — which is the honest way to show whether the thing works.
"""
import io

src = io.open('index.html', encoding='utf-8').read()
count = 0

def rep(old, new):
    global src, count
    c = src.count(old)
    assert c == 1, 'MARKER x%d: %r' % (c, old[:90])
    src = src.replace(old, new); count += 1

# ---------------- 1. correct key names -------------------------------------
rep("""  const _wdOrder=[1,2,3,4,5,6,0];              // Пн..Нд → getDay()
  _wdOrder.forEach((g,i)=>{ wd['k'+i]=WD_FACTOR[g]; });
  for(let m=0;m<12;m++) md['k'+m]=MO_FACTOR[m];""",
"""  /* Рендерът търси ключове '0_monday'.. и '1_january'.. — трябва да съвпаднат. */
  const _wdKeys=['0_monday','1_tuesday','2_wednesday','3_thursday','4_friday','5_saturday','6_sunday'];
  const _wdDay =[1,2,3,4,5,6,0];               // Пн..Нд → getDay()
  _wdKeys.forEach((key,i)=>{ wd[key]=WD_FACTOR[_wdDay[i]]; });
  const _moNames=['january','february','march','april','may','june','july',
                  'august','september','october','november','december'];
  _moNames.forEach((nm,i)=>{ md[(i+1)+'_'+nm]=MO_FACTOR[i]; });""")

io.open('index.html','w',encoding='utf-8').write(src)
print('PATCHED %d blocks OK' % count)
