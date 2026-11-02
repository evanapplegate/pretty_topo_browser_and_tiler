# Fourth pass: tone-and-position seam correction, two rounds, measured after each.
import time, numpy as np, tone as t
from PIL import Image
T, grid, rows, cols = t.load()
base = [x['lab'] for x in T]
M = t.fit_global(T, grid, order=3, lam=.005)
L = [t.apply_global(x, m, 3) for x, m in zip(base, M)]
for sg in (260, 180, 120):
    L, _, _ = t.dodge(T, base, L, rows, cols, sigma=sg)
show = lambda tag, X: print(tag, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in t.metrics(T, grid, X, base).items() if a != 'worst'}, flush=True)
show('before', L)
for r in range(3):
    t0 = time.time(); F = t.fit_bilateral(T, grid, L)
    L = [t.apply_bilateral(a, f) for a, f in zip(L, F)]
    print('round', r, round(time.time()-t0, 1), 's  max', round(float(np.abs(F).max()), 3), flush=True); show(f'round{r}', L)
print('fake-seam baseline med %.2f p90 %.2f' % t.baseline(T, L))
for q in t.last_seams[:6]: print('  %-22s med %.1f p90 %.1f' % (q[2], q[0], q[1]))
G = [t.gamut_map(l) for l in L]
Image.fromarray(t.mosaic(T, G, rows, cols, 2)).resize((1103, 1278), Image.LANCZOS).save('qa/run4.png')
t.seam_crops(T, grid, G, rows, cols, 'qa/run4_seams.png')
