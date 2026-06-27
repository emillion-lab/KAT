# KAT — Пътен Монитор

**Психо-Среда Монитор** за прогнозиране на пътни катастрофи в София.

Свързва данни от:
- 🌐 NOAA SWPC — геомагнитна активност (Kp индекс)
- 🌡️ Open-Meteo — атмосферно налягане (промяна 24ч)
- 📡 USGS — земетресения
- 🌕 Луна — фаза
- 🚔 МВР — реални ПТП данни (автоматично скрейпвани)

## Структура
```
index.html                    ← главен сайт (GitHub Pages)
scripts/scrape_mvr.py         ← MVR scraper
.github/workflows/            ← автоматично обновяване
data/mvr_accidents.json       ← реални данни от МВР
```

## GitHub Pages
Активирай от: Settings → Pages → Branch: main / root

🔗 https://emillion-lab.github.io/KAT/
