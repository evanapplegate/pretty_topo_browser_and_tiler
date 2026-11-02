# Find blank 7.5-minute cells enclosed by kept sheets, and list what the scan already has for each.
import collections, json, math, pickle, re
import numpy as np
cand, feat = pickle.load(open('scan.pkl', 'rb'))
R = json.load(open('site_rows.json'))
cell = lambda b: (round(b[0]/.125), round(b[1]/.125))
is75 = lambda b: abs(b[2]-b[0]-.125) < .01 and abs(b[3]-b[1]-.125) < .01
kept = {r['tif'] for r in R}
K = {cell(r['bbox']) for r in R if is75(r['bbox'])}
print('kept cells', len(K))
def loose(f):
    if not f or f['rich'] < .2 or f['warm_img'] >= .12: return False
    lg, lb = f['lab_green'], f['lab_blue']
    cg = float(np.hypot(*lg[1:])) if lg[0] is not None else 0; cb = float(np.hypot(*lb[1:])) if lb[0] is not None else 0
    hg = float(np.degrees(np.arctan2(lg[2], lg[1])) % 360) if lg[0] is not None else None
    if f['rich_blue'] >= .02: return cb >= 8
    return cg >= 26 and (hg is None or hg >= 115)
Lsheets = {u for u, f in feat.items() if u not in kept and loose(f)}
print('newly passing looser filter', len(Lsheets))
def box(i):
    b = i['boundingBox']; return [b['minX'], b['minY'], b['maxX'], b['maxY']]
by = collections.defaultdict(list)
for u, c in cand.items():
    b = box(c['item'])
    if is75(b): by[cell(b)].append(u)
K2 = K | {cell(box(cand[u]['item'])) for u in Lsheets if is75(box(cand[u]['item']))}
print('cells after looser filter', len(K2))
N4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]; N8 = N4+[(1, 1), (1, -1), (-1, 1), (-1, -1)]
def holes(S):
    out = {}
    seen = {(x+dx, y+dy) for x, y in S for dx in range(-1, 2) for dy in range(-1, 2)}-S
    for c in seen:
        n4 = sum((c[0]+d[0], c[1]+d[1]) in S for d in N4); n8 = sum((c[0]+d[0], c[1]+d[1]) in S for d in N8)
        if n4 >= 3 or n8 >= 5: out[c] = (n4, n8)
    return out
H = holes(K2)
print('enclosed blanks after looser filter', len(H))
rows = []
for c, (n4, n8) in sorted(H.items(), key=lambda kv: (-kv[0][1], kv[0][0])):
    w, s = c[0]*.125, c[1]*.125
    us = by.get(c, [])
    names = sorted({re.search(r'for (.+), ([A-Z]{2}) (\d{4})', cand[u]['item']['title']).group(0)[4:] for u in us})
    rows.append(dict(cell=c, w=w, s=s, n4=n4, n8=n8, cands=us))
    print(f'  {s:7.3f} {w:9.3f} sides {n4} around {n8} in scan {len(us):2d} {names[:4]}')
pickle.dump(dict(Lsheets=sorted(Lsheets), holes=rows), open('holes.pkl', 'wb'))
