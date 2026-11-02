# Compare every 1/8 image with its clipped thumbnail, then flag only the ones that pass so the site can use them.
import json, os
from concurrent.futures import ThreadPoolExecutor as TP
import numpy as np
from PIL import Image
D = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/topo_finder/site/'
R = json.load(open('site_rows.json'))
def one(r):
    p = f"{D}clip8/{r['scan']}.jpg"
    if not os.path.exists(p): return r['scan'], 'missing', 0, 0
    try:
        b = Image.open(p); b.load()
    except Exception as e:
        return r['scan'], 'corrupt', 0, 0
    if b.size != (740, 850): return r['scan'], f'size {b.size}', 0, 0
    a = np.asarray(Image.open(f"{D}clip/{r['scan']}.jpg").convert('L').resize((85, 97), Image.BILINEAR), float)
    c = np.asarray(b.convert('L').resize((85, 97), Image.BILINEAR), float)
    # Blocks of 2 px keep this about overall layout, not fine texture.
    ax, cx = a-a.mean(), c-c.mean()
    ncc = float((ax*cx).sum()/np.sqrt((ax**2).sum()*(cx**2).sum()+1e-9))
    return r['scan'], 'ok', ncc, float(c.std())
with TP(10) as e: Q = list(e.map(one, R))
st = {}
for _, s, _, _ in Q: st[s] = st.get(s, 0)+1
ncc = np.array([q[2] for q in Q if q[1] == 'ok']); print('status', st, '| match to thumb: min %.3f p1 %.3f median %.3f' % (ncc.min(), np.percentile(ncc, 1), np.median(ncc)))
by = {r['scan']: r for r in R}
low = sorted((q for q in Q if q[1] == 'ok'), key=lambda q: q[2])[:12]
for q in low: print(f"  {q[2]:.3f} std {q[3]:5.1f} {by[q[0]]['name']}, {by[q[0]]['st']} {by[q[0]]['yr']}")
good = {q[0] for q in Q if q[1] == 'ok' and q[2] >= .6 and q[3] >= 1}
for r in R: r['hi'] = r['scan'] in good
json.dump(R, open('site_rows.json', 'w'))
open(D+'sheets.js', 'w').write('const SHEETS='+json.dumps(R, separators=(',', ':'))+';\n')
print('flagged', len(good), 'of', len(R), '| not flagged', [by[q[0]]['name'] for q in Q if q[0] not in good][:12])
