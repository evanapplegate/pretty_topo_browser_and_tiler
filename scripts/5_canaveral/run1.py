# The latest St Marys settings, unchanged, on the six Canaveral sheets.
import numpy as np, cv2, cfg
from cfg import t
from PIL import Image
T, grid, rows, cols = t.load(); base = [x['lab'] for x in T]
L = t.trim(t.stack2(T, grid, base, rows, cols, rounds=(3, 4), sigmas=((260, 180, 120), (90,)), finish=.5))
np.savez('work/final_q.npz', **{str(x['s']['scan']): l.astype(np.float32) for x, l in zip(T, L)})
V = [t.ink_guard(b, l, 3) for b, l in zip(base, L)]
print('raw', {k: round(v, 2) for k, v in t.visibility(T, grid, base).items()}); print('run', {k: round(v, 2) for k, v in t.visibility(T, grid, V).items()})
print({a: (round(b, 3) if isinstance(b, float) else b) for a, b in t.metrics(T, grid, V, base).items() if a != 'worst'})
for q in t.last_seams[:7]: print('  %-22s med %.1f p90 %.1f' % (q[2], q[0], q[1]))
print('band raw', t.band_profile(T, base)); print('band run', t.band_profile(T, V), flush=True)
G = [t.gamut_map(v) for v in V]
a = t.mosaic(T, base, rows, cols, 2); b = t.mosaic(T, G, rows, cols, 2)
S = np.full((a.shape[0], 2*a.shape[1]+24, 3), 255, np.uint8); S[:, :a.shape[1]] = a; S[:, -a.shape[1]:] = b
Image.fromarray(S).resize((1760, int(1760*S.shape[0]/S.shape[1])), Image.LANCZOS).save('qa/run1_ba.png')
Image.fromarray(b).save('qa/run1.png')
t.seam_crops(T, grid, G, rows, cols, 'qa/run1_seams.png')
