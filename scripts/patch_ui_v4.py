"""KAT UI v4 — surface the second scale, drop the count forecast.

Two problems with what v3 shipped:

1. harmScore was computed but never drawn. The whole value of the finding is
   in the divergence (a dry August Sunday scores 3 for cars, 10 for people),
   and showing one number hides exactly that.

2. "Очаквани ~9.6 ПТП" promises precision the model does not have. Out-of-sample
   R2 is 0.44 — over half the daily variation is unpredictable, and a single
   jack-knifed lorry moves the count more than every factor combined. A relative
   statement is honest; a point estimate is not.
"""
import io

src = io.open('index.html', encoding='utf-8').read()
count = 0

def rep(old, new):
    global src, count
    c = src.count(old)
    assert c == 1, 'MARKER x%d: %r' % (c, old[:90])
    src = src.replace(old, new); count += 1


# ------------------------------------------------- 1. markup: two score boxes
rep(
"""      <div class="signal-right">
        <div class="signal-score-label">РИСК</div>
        <div class="signal-score" id="sl-score">—</div>
        <div class="signal-road" id="sl-road">—</div>
      </div>""",
"""      <div class="signal-right">
        <div class="signal-scales">
          <div class="scale-cell">
            <div class="signal-score-label" id="sl-lab-car">🚗 ЗА КОЛАТА</div>
            <div class="signal-score" id="sl-score">—</div>
          </div>
          <div class="scale-cell">
            <div class="signal-score-label" id="sl-lab-harm">🧍 ЗА ЧОВЕКА</div>
            <div class="signal-score" id="sl-harm">—</div>
          </div>
        </div>
        <div class="signal-road" id="sl-road">—</div>
        <div class="scale-note" id="sl-diverge"></div>
      </div>""")

# --------------------------------------------------------------- 2. styles
rep(
""".signal-right{text-align:right;}""",
""".signal-right{text-align:right;}
.signal-scales{display:flex;gap:18px;justify-content:flex-end;}
.scale-cell{text-align:right;}
.scale-note{font-size:.68rem;color:var(--dim);margin-top:6px;max-width:230px;
  margin-left:auto;line-height:1.35;}""")

# ------------------------------------------- 3. subtitle: no count forecast
rep(
"""  document.getElementById('sl-sub').textContent =
    (lang==='bg'?'Очаквани ~':'Expected ~')+r.expected+(lang==='bg'?' ПТП в София (средна прогноза)':' crashes in Sofia (mean forecast)')
    + (r.hs===2?(lang==='bg'?' · 🎉 празник':' · 🎉 holiday'):r.hs===1?(lang==='bg'?' · пред-празничен ден':' · pre-holiday'):'');""",
"""  /* Без прогноза за брой: моделът обяснява 44% от дневната промяна, тоест
     точно число би било обещание, което не може да се удържи. Показваме
     относително спрямо обичайното за този ден и месец. */
  const relPct = Math.round((r.totalMult-1)*100);
  const relTxt = Math.abs(relPct)<5
    ? (lang==='bg'?'Около обичайното за този ден':'About normal for this day')
    : (lang==='bg'
        ? (relPct>0?'С ~'+relPct+'% над обичайното за този ден':'С ~'+Math.abs(relPct)+'% под обичайното за този ден')
        : (relPct>0?'~'+relPct+'% above normal for this day':'~'+Math.abs(relPct)+'% below normal for this day'));
  document.getElementById('sl-sub').textContent = relTxt
    + (r.hs===2?(lang==='bg'?' · 🎉 празник':' · 🎉 holiday'):'');""")

# --------------------------------------------- 4. render both scores + note
rep(
"""  document.getElementById('sl-score').textContent = r.riskScore+'/10';
  document.getElementById('sl-score').style.color = scoreColor(r.riskScore);
  document.getElementById('sl-road').textContent = k.roadLevels[lv];
  document.getElementById('sl-road').style.color = scoreColor(r.riskScore);""",
"""  document.getElementById('sl-score').textContent = r.riskScore+'/10';
  document.getElementById('sl-score').style.color = scoreColor(r.riskScore);
  document.getElementById('sl-harm').textContent = r.harmScore+'/10';
  document.getElementById('sl-harm').style.color = scoreColor(r.harmScore);
  document.getElementById('sl-lab-car').textContent  = lang==='bg'?'🚗 ЗА КОЛАТА':'🚗 CARS';
  document.getElementById('sl-lab-harm').textContent = lang==='bg'?'🧍 ЗА ЧОВЕКА':'🧍 PEOPLE';
  document.getElementById('sl-road').textContent = k.roadLevels[lv];
  document.getElementById('sl-road').style.color = scoreColor(Math.max(r.riskScore,r.harmScore));

  /* Разминаването е цялата стойност на двете скали — ако не се обясни,
     човек вижда две числа и трябва сам да си ги превежда. */
  const gap = r.riskScore - r.harmScore;
  let note='';
  if(gap>=3)      note = lang==='bg'?'Много удари, но по-леки — типично за сняг и дъжд. Пази ламарината.':'Many crashes, milder ones — typical of snow and rain.';
  else if(gap<=-3)note = lang==='bg'?'Малко катастрофи, но тежки. Спокойните дни са по-опасни за живота.':'Few crashes, but severe ones. Quiet days are deadlier.';
  document.getElementById('sl-diverge').textContent = note;""")

# ------------------------------------------------------- 5. stale label bits
rep("hsub:'Космическо време · Метео · Празници · История 2015–2024'",
    "hsub:'Метео · Празници · МВР данни 2015–2025'")
rep("hsub:'Space weather · Meteo · Holidays · History 2015–2024'",
    "hsub:'Meteo · Holidays · MVR data 2015–2025'")

io.open('index.html','w',encoding='utf-8').write(src)
print('PATCHED %d blocks OK' % count)
