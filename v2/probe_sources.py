#!/usr/bin/env python3
"""Диагностика: откъде katastrofi.bg тегли точките и дали sensor.community отговаря за София."""
import json, re, urllib.request
from urllib.parse import urljoin

UA = {"User-Agent": "Mozilla/5.0 (KAT research; github.com/emillion-lab/KAT)"}


def get(url, n=None):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        b = r.read() if n is None else r.read(n)
        return r.status, r.headers.get("content-type", ""), b.decode("utf-8", "replace")


print("=== katastrofi.bg ===")
st, ct, html = get("https://katastrofi.bg/")
print(st, ct, len(html))
scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
print("scripts:", scripts)
cands = set(re.findall(r'["\'`](/?(?:api|data|export|static/data)[^"\'`\s]{0,120})["\'`]', html))
for s in scripts:
    try:
        _, _, js = get(urljoin("https://katastrofi.bg/", s))
        print(f"  {s}: {len(js)} chars")
        cands |= set(re.findall(r'["\'`](/?(?:api|data|export)[A-Za-z0-9_/\-\.\?=&{}$]{1,120})["\'`]', js))
        cands |= set(re.findall(r'["\'`](https?://[^"\'`\s]{5,160})["\'`]', js))
        cands |= set(re.findall(r'fetch\(\s*["\'`]([^"\'`]{3,160})', js))
    except Exception as e:
        print("  ERR", s, e)
print("кандидати:")
for c in sorted(cands):
    print("  ", c)

print("\n=== опит на кандидати ===")
for c in sorted(cands):
    if c.startswith("http") and "katastrofi" not in c:
        continue
    url = urljoin("https://katastrofi.bg/", c.replace("${", "").replace("}", ""))
    try:
        st, ct, body = get(url, 600)
        print(f"{st} {ct[:30]:30} {url}\n    {body[:300]!r}")
    except Exception as e:
        print(f"ERR {url} {e}")

print("\n=== sensor.community, София (текущи) ===")
try:
    st, ct, body = get("https://data.sensor.community/airrohr/v1/filter/area=42.69,23.32,12")
    d = json.loads(body)
    ids = {(x['sensor']['id'], x['sensor']['sensor_type']['name']) for x in d}
    pm = [x for x in d if any(v['value_type'] == 'P2' for v in x['sensordatavalues'])]
    print(f"{st} записи={len(d)} сензори={len(ids)} с PM2.5={len({x['sensor']['id'] for x in pm})}")
    print("типове:", sorted({t for _, t in ids}))
except Exception as e:
    print("ERR", e)

print("\n=== архив sensor.community ===")
try:
    st, ct, body = get("https://archive.sensor.community/2026-10-06/", 400)
    print(st, ct, body[:300])
except Exception as e:
    print("ERR", e)
