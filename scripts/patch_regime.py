"""Пуска режима: филтър срещу областни заглавия + поправка на базата.

Два проблема пречеха режимът да работи с живия поток:

1. mvTotal приемаше всяка стойност на `injured`. Ежедневната справка се чете
   от новинарски заглавия и понякога съобщава числа за една област вместо за
   страната ("в Разградско три катастрофи" → 3). Национално под 10 ранени за
   денонощие се случва в около 1% от дните; в потока такива стойности са 14%.
   Един такъв ден срива режима с ~90% и произвежда фалшив "спокоен период".

2. baseDaily() връщаше 27 — брой ПТП на денонощие в София. Но mvTotal връща
   РАНЕНИ национално (медиана 24). Различни величини: режимът щеше да отчита
   постоянен спад от порядъка на 75% и да стои залепен на долната граница.

След поправката: 12 от последните 14 дни минават филтъра, режимът се
задейства с трите изисквани дни.
"""
import io

src = io.open('engine.js', encoding='utf-8').read()
count = 0

def rep(old, new):
    global src, count
    c = src.count(old)
    assert c == 1, 'MARKER x%d: %r' % (c, old[:80])
    src = src.replace(old, new); count += 1

rep("""function mvTotal(m){
  if(!m) return null;
  if(m.sofia_light != null) return m.sofia_light;
  if(m.injured != null) return m.injured;
  if(m.light != null || m.serious != null) return (m.light||0)+(m.serious||0);
  return null;
}""",
"""function mvTotal(m){
  if(!m) return null;
  if(m.sofia_light != null) return m.sofia_light;
  /* Филтър срещу областни заглавия. Ежедневната справка се чете от новини и
     понякога съобщава числа за една област вместо за страната ("в Разградско
     три катастрофи"). Национално под 10 ранени за денонощие се случва в
     около 1% от дните; в потока такива стойности са 14% — почти сигурно са
     регионални. По-добре пропуснат ден, отколкото фалшив спад в режима. */
  if(m.injured != null) return m.injured >= 10 ? m.injured : null;
  if(m.light != null || m.serious != null){
    const t = (m.light||0)+(m.serious||0);
    return t >= 10 ? t : null;
  }
  return null;
}""")

rep("""function baseDaily(){ return (S.historical && S.historical.base_daily) || 27; }""",
"""/* Базата се сравнява със същата величина, която mvTotal връща — ранени на
   денонощие национално. Медианата за 2015–2025 е 24. Ако се ползваше базата
   за брой ПТП (~100), режимът щеше да отчита постоянен спад от 75%. */
function baseDaily(){ return (S.historical && S.historical.injured_base) || 24; }""")

io.open('engine.js', 'w', encoding='utf-8').write(src)
print('PATCHED %d blocks OK' % count)
