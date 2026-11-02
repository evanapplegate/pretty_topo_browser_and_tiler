# Try the wide match on the part of the Florida cluster with the worst seams.
import sys, time, numpy as np, blocks as b
from blocks import t
from PIL import Image
G, C, Q, rep = b.clusters()
g = [c for c in G[1] if C[c][1] < float(sys.argv[1])]
T, grid, rows, cols = b.load_block(g, C, Q, rep); base = [x['lab'] for x in T]
print('sheets', len(T), 'grid', rows, 'x', cols, 'seams', len(t.edges(grid)), flush=True)
print('raw', {k: round(v, 2) for k, v in t.visibility(T, grid, base, off=12).items()}, flush=True)
t0 = time.time(); L = b.match_wide(T, grid, rows, cols); print('match', round(time.time()-t0), 's', flush=True)
F = b.finish(base, L)
print('run', {k: round(v, 2) for k, v in t.visibility(T, grid, F, off=12).items()})
print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in t.metrics(T, grid, F, base).items() if k != 'worst'})
for q in t.last_seams[:6]: print('  %-22s med %.1f p90 %.1f' % (q[2], q[0], q[1]))
A = t.mosaic(T, base, rows, cols, 1); B = t.mosaic(T, F, rows, cols, 1)
S = np.full((A.shape[0], 2*A.shape[1]+40, 3), 255, np.uint8); S[:, :A.shape[1]] = A; S[:, -A.shape[1]:] = B
Image.fromarray(S).resize((1900, int(1900*S.shape[0]/S.shape[1])), Image.LANCZOS).save('qa/fl_south_ba.png')
t.seam_crops(T, grid, F, rows, cols, 'qa/fl_south_seams.png', size=280)
