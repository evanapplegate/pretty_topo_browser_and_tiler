# Per-tile slider fit toward group medians; tiles run in parallel, and a tile only fits the groups it contains.
import json, os, sys
os.environ['OMP_NUM_THREADS'] = os.environ['OPENBLAS_NUM_THREADS'] = '1'
import numpy as np, cv2
import multiprocessing as mp
from scipy.optimize import minimize
cv2.setNumThreads(0)
TAG, OUT, S = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, S)
import sc
USE = sys.argv[4].split(',')
LAM, BOUND = float(sys.argv[5]), float(sys.argv[6])
BIAS = json.load(open(sys.argv[7])) if len(sys.argv) > 7 else {}
G = sc.groups(TAG, S, n=20000)
names = sorted(G)
base = {n: {k: sc.lab(G[n][k][2]).mean(0) for k in G[n]} for n in names}
allk = sorted({k for n in names for k in G[n]})
target = {k: np.median([base[n][k] for n in names if k in G[n]], 0) for k in allk}
print('targets', {k: np.round(v, 1).tolist() for k, v in target.items()}, flush=True)
def unpack(x):
    return {r: tuple(x[i*4:i*4+4]) for i, r in enumerate(USE)}
def one(n):
    keys = sorted(G[n])
    tgt = {k: target[k]+np.array(BIAS.get(n, {}).get(k, [0, 0, 0])) for k in keys}
    def loss(x):
        adj = unpack(x); e = 0
        for k in keys:
            m = sc.lab(sc.simulate(G[n][k][2], adj)).mean(0)
            e += ((m-tgt[k])**2).sum()
        return e+LAM*(x**2).sum()
    r = minimize(loss, np.zeros(len(USE)*4), method='L-BFGS-B', bounds=[(-BOUND, BOUND)]*(len(USE)*4), options=dict(eps=.012, maxiter=60, maxfun=2500))
    xi = np.round(r.x*100)/100; adj = unpack(xi)
    res = {k: [int(round(v*100)) for v in adj[k]] for k in adj}
    b = {k: np.linalg.norm(base[n][k]-target[k]) for k in keys}; a = {k: np.linalg.norm(sc.lab(sc.simulate(G[n][k][2], adj)).mean(0)-target[k]) for k in keys}
    print(f'{n:18s} dE before {np.mean(list(b.values())):5.1f} after {np.mean(list(a.values())):4.1f} worst {max(a.values()):4.1f} {max(a, key=a.get):10s} at-bound {int((np.abs(xi) >= BOUND-.005).sum())}', flush=True)
    return n, res, b, a
with mp.get_context("fork").Pool(16) as p:
    R = p.map(one, names, chunksize=1)
json.dump({n: r for n, r, _, _ in R}, open(OUT, 'w'), indent=1)
json.dump({k: v.tolist() for k, v in target.items()}, open(OUT+'.target', 'w'))
bb = [np.mean(list(b.values())) for _, _, b, _ in R]; aa = [np.mean(list(a.values())) for _, _, _, a in R]
print('mean dE before %.1f after %.1f' % (np.mean(bb), np.mean(aa)))
