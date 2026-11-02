# Track the pale flats patch through every stage of the pipeline.
import numpy as np, cv2, tone as t
T, grid, rows, cols = t.load(); base = [x['lab'] for x in T]
CW, CH = 5886//4, 6820//4; y0, x0 = int(1.55*CH), 2*CW
R = t.canvas(T, base, rows, cols)[y0-30:y0+30, x0-40:x0-5]; k = R[..., 0] > .86
P = lambda X: np.round(t.canvas(T, X, rows, cols)[y0-30:y0+30, x0-40:x0-5][k].mean(0), 3)
print('raw', P(base), 'class share', [round(float((t.classify(t.canvas(T, base, rows, cols))[y0-30:y0+30, x0-40:x0-5][k] == i).mean()), 2) for i in (-1, 0, 1, 2, 3)])
M = t.fit_global(T, grid, order=3, lam=.005); L = [t.apply_global(x, m, 3) for x, m in zip(base, M)]; print('global', P(L))
al = (.8, .6, .7, .4)
for sg in (260, 180, 120):
    L, _, tau = t.dodge(T, base, L, rows, cols, sigma=sg, alpha=al); print('dodge', sg, P(L), {k_: np.round(v, 3).tolist() for k_, v in tau.items()}, flush=True)
for r in range(3):
    F = t.fit_bilateral(T, grid, L, along=30, node=24); L = [t.apply_bilateral(a, f) for a, f in zip(L, F)]; print('seam', r, P(L), flush=True)
L, _, _ = t.dodge(T, base, L, rows, cols, sigma=90, alpha=tuple(a*.5 for a in al)); print('dodge 90', P(L), flush=True)
for r in range(4):
    F = t.fit_bilateral(T, grid, L, along=30, node=24); L = [t.apply_bilateral(a, f) for a, f in zip(L, F)]; print('seam', r, P(L), flush=True)
