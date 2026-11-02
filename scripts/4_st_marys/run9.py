# Rebuild with pale flats pinned and inks guarded, then recheck the two defects.
import numpy as np, cv2, tone as t
from PIL import Image
T, grid, rows, cols = t.load()
base = [x['lab'] for x in T]
L0 = t.stack2(T, grid, base, rows, cols, rounds=(3, 4), sigmas=((260, 180, 120), (90,)), finish=.5)
L = t.trim(L0)
np.savez('work/final_q.npz', **{str(x['s']['scan']): l.astype(np.float32) for x, l in zip(T, L)})
V = [t.ink_guard(b, l, 3) for b, l in zip(base, L)]
print('band', t.band_profile(T, V), flush=True)
print({k: round(a, 2) for k, a in t.visibility(T, grid, V).items()}); m = t.metrics(T, grid, V, base)
print({a: (round(b, 3) if isinstance(b, float) else b) for a, b in m.items() if a != 'worst'})
C = lambda X: t.canvas(T, X, rows, cols)
b, l = C(base), C(V); CW, CH = 5886//4, 6820//4; y0, x0 = int(1.55*CH), 2*CW
r = b[y0-30:y0+30, x0-40:x0-5]; k = r[..., 0] > .86
print('pale flats raw', np.round(r[k].mean(0), 3), 'final', np.round(l[y0-30:y0+30, x0-40:x0-5][k].mean(0), 3))
G = [t.gamut_map(v) for v in V]
Image.fromarray(t.mosaic(T, G, rows, cols, 2)).resize((1103, 1278), Image.LANCZOS).save('qa/run9.png')
t.seam_crops(T, grid, G, rows, cols, 'qa/run9_seams.png')
