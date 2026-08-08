"""KAT v7 — clear the legacy panels out of History.

The tab still carried three things from the pre-recalibration model, sitting
directly under text that says those factors were dropped:

  1. "КРИВИ НА МОДЕЛА — Kp (обърната U)" — a chart of the inverted-U
     hypothesis, with a caption explaining that above Kp 7.5 people stay home.
     Tested at every lag from 0 to 7 days: r = -0.023. The chart draws a claim
     the model no longer makes.
  2. The correlation strip showing r=0.30 for Kp vs crashes. That is the raw
     correlation with nothing held constant; weekday, month and rain all move
     together with it. Controlled, it goes to -0.023. Two contradictory numbers
     on one screen is worse than either alone.
  3. The 30-day table's Kp and ΔhPa columns, for the same reason.

What replaces them is the comparison that actually matters: model score
against what happened, day by day, for the last 30 days.
"""
import io

src = io.open('index.html', encoding='utf-8').read()
count = 0

def rep(old, new):
    global src, count
    c = src.count(old)
    assert c == 1, 'MARKER x%d: %r' % (c, old[:90])
    src = src.replace(old, new); count += 1


# ---------- 1. drop the Kp inverted-U curve block entirely -----------------
rep("""  <div class="fc-chart-wrap">
    <div class="fc-chart-title" id="curve-title">КРИВИ НА МОДЕЛА — Kp (обърната U) срещу реалните данни</div>
    <canvas id="curve-canvas" height="190"></canvas>
    <div style="font-size:.7rem;color:var(--dim);margin-top:6px;line-height:1.5" id="curve-note">
      <span style="color:var(--yellow)">━</span> kpEffect — коефициентът на модела ·
      <span style="color:var(--orange)">●</span> реален ден: ПТП спрямо базата за този ден/месец, при измереното Kp.
      Ако точките лягат на кривата — коефициентите са верни. Хипотезата: над Kp≈7.5 хората си стоят вкъщи и ПТП падат.
    </div>
  </div>""",
"""  <!-- Kp кривата е премахната: обърнатата U хипотеза е проверена и отхвърлена
       (r=-0.023 при всички закъснения 0–7 дни). Виж методологията по-горе. -->""")

# ---------- 2. drop the correlation strip ----------------------------------
rep("""  <!-- Correlation stats -->
  <div class="corr-box" id="corr-box" style="display:none;">
    <div class="corr-title" id="corr-title">🔬 КОРЕЛАЦИЯ: МВР ДАННИ ↔ РИСК ФАКТОРИ</div>
    <div class="corr-stat-row" id="corr-stats"></div>
  </div>""",
"""  <!-- Корелационната лента е премахната: показваше СУРОВИ корелации без
       контрол за ден, месец и време. Kp излизаше r=0.30, а контролирано
       е -0.023 — числото подвеждаше точно там, където обяснявахме обратното. -->""")

# ---------- 3. 30-day table: drop Kp / ΔhPa, add score comparison ----------
rep("""      <thead id="hist-thead"><tr>
        <th>ДАТА</th><th>ДЕН</th><th>Kp</th><th>ΔhPa</th><th>ДЪЖД</th><th>РИСК</th>
        <th>МВР ПТП</th><th>МОДЕЛ</th>
      </tr></thead>""",
"""      <thead id="hist-thead"><tr>
        <th>ДАТА</th><th>ДЕН</th><th>ДЪЖД</th><th>🚗</th><th>🧍</th>
        <th>МВР ПТП</th><th>ОЧАКВАНО</th><th>РАЗЛИКА</th>
      </tr></thead>""")

rep("""    <div class="fc-chart-title" id="hist-chart-title">ПОСЛЕДНИТЕ 30 ДНИ — РЕАЛНИ ДАННИ</div>""",
"""    <div class="fc-chart-title" id="hist-chart-title">ПОСЛЕДНИТЕ 30 ДНИ — МОДЕЛ СРЕЩУ ДЕЙСТВИТЕЛНОСТ</div>""")

rep("""      <span style="color:var(--cyan)">━</span> дневен риск индекс (реални Kp от NOAA · реално налягане и валежи от Open-Meteo) ·
      <span style="color:var(--orange)">●</span> реален брой ПТП, когато е наличен от МВР/новини.""",
"""      <span style="color:var(--cyan)">━</span> оценка на модела ·
      <span style="color:var(--orange)">●</span> реален брой ПТП от МВР, когато е наличен.
      Съвпадението няма да е точно: моделът обяснява 44% от дневната промяна.
      Полезното е дали греши <b>систематично</b> в една посока, не дали познава всеки ден.""")

io.open('index.html','w',encoding='utf-8').write(src)
print('PATCHED %d blocks OK' % count)
