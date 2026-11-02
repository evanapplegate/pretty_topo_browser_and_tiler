# Score a cluster after every stage, to find where a bad result enters.
import sys, time, numpy as np, blocks as b
from blocks import t
g_all, C, Q, rep = b.clusters()
i = int(sys.argv[1]); node = int(sys.argv[2])
T, grid, rows, cols = b.load_block(g_all[i], C, Q, rep); base = [x['lab'] for x in T]
def show(tag, X):
    v = t.visibility(T, grid, X, off=12); m = t.metrics(T, grid, X, base)
    print(f"{tag:14s} vis {v['ratio']:.2f} worst {v['ratio_worst']:.2f} land {m['land_spread']:.2f} water {m['water_spread']:.2f} chroma {m['chroma']:.3f} detail {m['detail']:.3f} Lrange {min(float(x[...,0].min()) for x in X):.2f}..{max(float(x[...,0].max()) for x in X):.2f}", flush=True)
show('raw', base)
M = t.fit_global(T, grid, order=3, lam=.005, sigma=2, depths=(2, 5, 9, 15), step=2)
L = [t.apply_global(x, m, 3) for x, m in zip(base, M)]; show('global', L)
al = (.8, .6, .7, .4)
for sg in (130, 90, 60):
    L, _, _ = t.dodge(T, base, L, rows, cols, sigma=sg, alpha=al); show(f'dodge {sg}', L)
t0 = time.time(); F = t.fit_bilateral(T, grid, L, along=15, node=node); print('solve', round(time.time()-t0), 's max', round(float(np.abs(F).max()), 3), 'shape', F.shape, flush=True)
L2 = [t.apply_bilateral(a, f) for a, f in zip(L, F)]; show('seam 1', L2)
