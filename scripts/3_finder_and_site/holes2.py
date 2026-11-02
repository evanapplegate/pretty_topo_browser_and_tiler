# List every 7.5-minute edition for each enclosed blank, score new thumbnails, and fetch topoView IDs for all candidates.
import json, pickle, re, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor as TP
import numpy as np, tnm, hue
cand, feat = pickle.load(open('scan.pkl', 'rb'))
H = pickle.load(open('holes.pkl', 'rb'))
def q(h):
    w, s = h['w'], h['s']
    d = tnm.page(bbox=f'{w+.05},{s+.05},{w+.075},{s+.075}', prodExtents='7.5 x 7.5 minute', max=60)
    return h, d.get('items', [])
with TP(6) as e: got = list(e.map(q, H['holes']))
new = {}
for h, items in got:
    h['cands'] = []
    for i in items:
        u = (i.get('urls') or {}).get('GeoTIFF'); b = i['boundingBox']
        if not u or not i.get('previewGraphicURL'): continue
        if abs(b['minX']-h['w']) > .01 or abs(b['minY']-h['s']) > .01: continue
        h['cands'].append(u)
        if u not in cand: new[u] = dict(item=i, q=False)
print('hole editions', sum(len(h['cands']) for h in H['holes']), 'new thumbs to score', len(new), 'blanks with no edition at all', sum(not h['cands'] for h in H['holes']), flush=True)
def run(kv):
    u, r = kv; a = hue.fetch(r['item']['previewGraphicURL']); return u, (None if a is None else hue.features(a))
with TP(12) as e:
    for u, f in e.map(run, new.items()):
        feat[u] = f; cand[u] = new[u]
pickle.dump((cand, feat), open('scan.pkl', 'wb')); pickle.dump(H, open('holes.pkl', 'wb'))
ids = sorted({int(re.search(r'_(\d+)_\d{4}_\d+_geo\.tif', u).group(1)) for u in list(H['Lsheets'])+[c for h in H['holes'] for c in h['cands']]})
B = 'https://energy.usgs.gov/arcgis/rest/services/topoview/ustOverlay/MapServer/0/query?'
md5 = {}
for i in range(0, len(ids), 150):
    p = urllib.parse.urlencode(dict(where='scan_id IN (%s)' % ','.join(map(str, ids[i:i+150])), outFields='scan_id,md5', returnGeometry='false', f='json'))
    for f in json.load(urllib.request.urlopen(urllib.request.Request(B+p, headers={'User-Agent': 'curl/8.7.1'}), timeout=90))['features']:
        md5[f['attributes']['scan_id']] = f['attributes']['md5']
json.dump(md5, open('md5s.json', 'w'))
print('scan ids', len(ids), 'with topoView id', len(md5))
print('JS_IDS=' + json.dumps(sorted(md5.values()), separators=(',', ':')))
