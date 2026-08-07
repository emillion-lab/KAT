"""Discover the data endpoint behind the MVR interactive crash map.

Goal: replace headline scraping (36% coverage, mixes national totals with
single-region headlines) with the official per-incident feed, which carries
date, severity and region -> gives Sofia separately without waiting for FOI.

Strategy: fetch the map page, harvest every candidate URL from HTML/JS,
probe each, and record what came back. Written to run unattended.
"""
import urllib.request, urllib.error, re, json, sys, gzip, io

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept': 'text/html,application/json,*/*',
      'Accept-Language': 'bg-BG,bg;q=0.9,en;q=0.8'}

def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    r = urllib.request.urlopen(req, timeout=timeout)
    raw = r.read()
    if r.headers.get('Content-Encoding') == 'gzip':
        raw = gzip.decompress(raw)
    enc = 'utf-8'
    ct = r.headers.get('Content-Type', '')
    if 'windows-1251' in ct.lower() or 'cp1251' in ct.lower():
        enc = 'windows-1251'
    return r.getcode(), ct, raw.decode(enc, 'replace')

SEEDS = [
  "https://www.mvr.bg/ptp",
  "https://www.mvr.bg/opp",
  "https://ptp.mvr.bg/",
  "https://katastrofi.bg/",
]

print("=" * 70)
print("STEP 1 — seed pages")
print("=" * 70)
pages = {}
for u in SEEDS:
    try:
        code, ct, body = fetch(u)
        print("%s  %s  %s  %d chars" % (code, ct.split(';')[0], u, len(body)))
        pages[u] = body
    except Exception as ex:
        print("FAIL %s -> %s" % (u, ex))

print()
print("=" * 70)
print("STEP 2 — candidate endpoints harvested from those pages")
print("=" * 70)
PAT = re.compile(r'''["'(]([^"'()\s]{6,200}?(?:api|json|geojson|arcgis|feature|service|
                      rest|data|ptp|accident|incident)[^"'()\s]{0,200}?)["')]''',
                 re.I | re.X)
cands = set()
for base, body in pages.items():
    for m in PAT.finditer(body):
        u = m.group(1)
        if u.startswith('//'):
            u = 'https:' + u
        elif u.startswith('/'):
            root = '/'.join(base.split('/')[:3])
            u = root + u
        elif not u.startswith('http'):
            continue
        if any(u.lower().endswith(x) for x in ('.css', '.png', '.jpg', '.svg', '.woff', '.woff2', '.ico')):
            continue
        cands.add(u)

for u in sorted(cands):
    print(" ", u)
print("total candidates:", len(cands))

print()
print("=" * 70)
print("STEP 3 — probing candidates")
print("=" * 70)
hits = []
for u in sorted(cands)[:60]:
    try:
        code, ct, body = fetch(u, timeout=40)
    except Exception as ex:
        print("  ERR  %-70s %s" % (u[:70], str(ex)[:40]))
        continue
    looks_json = 'json' in ct.lower() or body.lstrip()[:1] in '[{'
    flag = ''
    if looks_json:
        try:
            j = json.loads(body)
            n = len(j) if isinstance(j, list) else len(j.keys())
            flag = '  <== JSON, %d top-level items' % n
            hits.append((u, ct, body[:1500]))
        except Exception:
            flag = '  (json-ish, unparsed)'
    print("  %s  %-58s %8d %s%s" % (code, u[:58], len(body), ct.split(';')[0][:24], flag))

print()
print("=" * 70)
print("STEP 4 — sample payloads from JSON hits")
print("=" * 70)
for u, ct, sample in hits[:6]:
    print("-" * 70)
    print(u)
    print(sample[:1200])

print()
print("SUMMARY: seeds_ok=%d candidates=%d json_hits=%d" % (len(pages), len(cands), len(hits)))
