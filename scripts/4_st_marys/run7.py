# Alternate class evening and seam solving so no band is left along seams; compare with the previous candidate.
import numpy as np, tone as t
from PIL import Image
T, grid, rows, cols = t.load()
base = [x['lab'] for x in T]
print('raw band', t.band_profile(T, base), flush=True)
Z = np.load('work/final_q.npz'); P = [Z[str(x['s']['scan'])].astype(np.float32) for x in T]
print('prev band', t.band_profile(T, P), flush=True)
L = t.stack2(T, grid, base, rows, cols)
print('new band', t.band_profile(T, L), flush=True)
v = t.visibility(T, grid, L); m = t.metrics(T, grid, L, base)
print({k: round(a, 2) for k, a in v.items()}); print({a: (round(b, 3) if isinstance(b, float) else b) for a, b in m.items() if a != 'worst'})
np.savez('work/cand2_q.npz', **{str(x['s']['scan']): l.astype(np.float16) for x, l in zip(T, L)})
G = [t.gamut_map(l) for l in L]
Image.fromarray(t.mosaic(T, G, rows, cols, 2)).resize((1103, 1278), Image.LANCZOS).save('qa/run7.png')
t.seam_crops(T, grid, G, rows, cols, 'qa/run7_seams.png')
