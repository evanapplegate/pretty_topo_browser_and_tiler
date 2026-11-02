# Match one cluster and report the same scores and previews used on the full-resolution blocks.
import sys, time, numpy as np, blocks as b
from blocks import t
from PIL import Image
g_all, C, Q, rep = b.clusters()
print('clusters', len(g_all), 'sizes', [len(g) for g in g_all][:12], flush=True)
i = int(sys.argv[1]); node = int(sys.argv[2]) if len(sys.argv) > 2 else 12
T, grid, rows, cols = b.load_block(g_all[i], C, Q, rep); base = [x['lab'] for x in T]
print('cluster', i, 'sheets', len(T), 'grid', rows, 'x', cols, 'unknowns est', len(T)*(850//node+2)*(740//node+2)*7, flush=True)
print('raw', {k: round(v, 2) for k, v in t.visibility(T, grid, base, off=12).items()}, flush=True)
t0 = time.time(); L = b.match(T, grid, rows, cols, node=node); print('match', round(time.time()-t0), 's', flush=True)
G = b.finish(base, L)
print('run', {k: round(v, 2) for k, v in t.visibility(T, grid, G, off=12).items()})
print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in t.metrics(T, grid, G, base).items() if k != 'worst'})
for q in t.last_seams[:5]: print('  %-22s med %.1f p90 %.1f' % (q[2], q[0], q[1]))
A = t.mosaic(T, base, rows, cols, 1); B = t.mosaic(T, G, rows, cols, 1)
S = np.full((A.shape[0], 2*A.shape[1]+40, 3), 255, np.uint8); S[:, :A.shape[1]] = A; S[:, -A.shape[1]:] = B
w = 1900; Image.fromarray(S).resize((w, int(w*S.shape[0]/S.shape[1])), Image.LANCZOS).save(f'qa/test{i}_ba.png')
t.seam_crops(T, grid, G, rows, cols, f'qa/test{i}_seams.png', size=280)
print(S.shape)
