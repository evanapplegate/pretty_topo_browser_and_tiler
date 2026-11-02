# Match one cluster plus its stacked editions and write the images. Each runs in its own process and finished clusters are skipped on a rerun.
import json, os, sys, time, numpy as np, blocks as b
from blocks import t
from PIL import Image
for d in ('clip_tm', 'clip8_tm'): os.makedirs(f'{b.SITE}/{d}', exist_ok=True)
G, C, Q, rep = b.clusters()
arg = sys.argv[1]
done = f'work/c{arg}.json'
wide = len(sys.argv) > 2 and sys.argv[2] == 'wide'
if os.path.exists(done) and not wide: print(arg, 'skip'); sys.exit()
t0 = time.time()
def stack_out(bbox, top):
    top_s = rep(bbox); n = 0
    for s in Q[bbox]:
        if s['scan'] == top_s['scan']: continue
        e = b.load_lab(s); b.save(s, t.gamut_map(t.ink_guard(e, b.match_edition(e, top), 6))); n += 1
    return n
if arg == 'rest':
    # Sheets with no neighbours have no seams, so they keep their colour; their other editions still follow them.
    inmulti = {tuple(C[c]) for g in G if len(g) > 1 for c in g}
    k = 0; n = 0
    for bbox in Q:
        if bbox in inmulti: continue
        top = b.load_lab(rep(bbox)); b.save(rep(bbox), top); n += stack_out(bbox, top); k += 1
    json.dump(dict(quads=k, editions=n, sec=round(time.time()-t0)), open(done, 'w')); print('rest', k, 'quads', n, 'editions', flush=True); sys.exit()
g = G[int(arg)]
T, grid, rows, cols = b.load_block(g, C, Q, rep); base = [x['lab'] for x in T]
raw = t.visibility(T, grid, base, off=12); rm = t.metrics(T, grid, base, base)
L = b.match_wide(T, grid, rows, cols) if wide else b.match(T, grid, rows, cols)
F = b.finish(base, L, 20 if wide else None)
v = t.visibility(T, grid, F, off=12); m = t.metrics(T, grid, F, base)
n = 0
for x, f in zip(T, F):
    b.save(x['s'], f); n += stack_out(tuple(x['s']['bbox']), f)
A = t.mosaic(T, base, rows, cols, 2); B = t.mosaic(T, F, rows, cols, 2)
S = np.full((A.shape[0], 2*A.shape[1]+24, 3), 255, np.uint8); S[:, :A.shape[1]] = A; S[:, -A.shape[1]:] = B
w = 1900 if len(g) > 8 else 1000
Image.fromarray(S).resize((w, max(1, int(w*S.shape[0]/S.shape[1]))), Image.LANCZOS).save(f'qa/c{arg}.png')
if len(t.edges(grid)) and len(g) >= 8: t.seam_crops(T, grid, F, rows, cols, f'qa/c{arg}_seams.png', size=280)
st = sorted({x['s']['st'] for x in T})
r = dict(i=int(arg), wide=wide, sheets=len(g), editions=n, states=st, raw=round(raw['ratio'], 2), raw_worst=round(raw['ratio_worst'], 2), vis=round(v['ratio'], 2), worst=round(v['ratio_worst'], 2), land=[round(rm['land_spread'], 2), round(m['land_spread'], 2)], water=[round(rm['water_spread'], 2), round(m['water_spread'], 2)], chroma=round(m['chroma'], 3), detail=round(m['detail'], 3), sec=round(time.time()-t0))
json.dump(r, open(done, 'w')); print(r, flush=True)
