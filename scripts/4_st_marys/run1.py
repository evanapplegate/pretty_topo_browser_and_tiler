# First pass: score the raw mosaic, then the global tone map, then tone map plus seam levelling.
import json, time, sys
import numpy as np, tone as t
from PIL import Image
T, grid, rows, cols = t.load()
base = [x['lab'] for x in T]
out = {}
out['raw'] = t.metrics(T, grid, base, base)
t0 = time.time()
M = t.fit_global(T, grid, order=2)
G = [t.apply_global(x['lab'], m, 2) for x, m in zip(T, M)]
print('global fit', round(time.time()-t0, 1), 's', 'finite', bool(np.isfinite(M).all()), 'max coef change', round(float(np.abs(M-M.mean(0)).max()), 3), flush=True)
out['global'] = t.metrics(T, grid, G, base)
t0 = time.time()
F, g = t.fit_field(T, grid, G)
print('field', round(time.time()-t0, 1), 's', F.shape, 'max field', round(float(np.abs(F).max()), 3), flush=True)
L = [a+t.field_up(f, a.shape[:2]) for a, f in zip(G, F)]
out['leveled'] = t.metrics(T, grid, L, base)
for k, v in out.items(): print(k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items()})
Image.fromarray(t.mosaic(T, G, rows, cols, 2)).resize((1103, 1278), Image.LANCZOS).save('qa/run1_global.png')
Image.fromarray(t.mosaic(T, L, rows, cols, 2)).resize((1103, 1278), Image.LANCZOS).save('qa/run1_leveled.png')
