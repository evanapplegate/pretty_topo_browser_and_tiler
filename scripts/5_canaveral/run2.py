# Add the water-only seam pass to the run1 result, then preview it.
import numpy as np, cfg
from cfg import t
from PIL import Image
T, grid, rows, cols = t.load(); base = [x['lab'] for x in T]
Z = np.load('work/final_q.npz'); L = [Z[str(x['s']['scan'])].astype(np.float32) for x in T]
L = t.water_pass(T, grid, L)
print({k: round(v, 2) for k, v in t.visibility(T, grid, L).items()}, {a: round(b, 3) for a, b in t.metrics(T, grid, L, base).items() if a in ('seam_med', 'seam_p90', 'land_spread', 'water_spread', 'chroma', 'detail')}, flush=True)
for q in t.last_seams[:7]: print('  %-22s med %.1f p90 %.1f' % (q[2], q[0], q[1]))
np.savez('work/final2_q.npz', **{str(x['s']['scan']): l.astype(np.float32) for x, l in zip(T, L)})
G = [t.gamut_map(t.ink_guard(b, l, 3)) for b, l in zip(base, L)]
b = t.mosaic(T, G, rows, cols, 2); Image.fromarray(b).resize((880, int(880*b.shape[0]/b.shape[1])), Image.LANCZOS).save('qa/run2.png')
t.seam_crops(T, grid, G, rows, cols, 'qa/run2_seams.png')
