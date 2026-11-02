import json, sys, numpy as np
from scipy.optimize import minimize
sys.path.insert(0, sys.argv[3])
import sc
TAG, OUT, S = sys.argv[1], sys.argv[2], sys.argv[3]
USE = sys.argv[4].split(',')
LAM = float(sys.argv[5])
BIAS = json.load(open(sys.argv[6])) if len(sys.argv) > 6 else {}
G = sc.groups(TAG, S)
names = sorted(G); keys = sorted(next(iter(G.values())))
base = {n: {k: sc.lab(G[n][k][2]).mean(0) for k in keys} for n in names}
target = {k: np.median([base[n][k] for n in names], 0) for k in keys}
print('targets', {k: np.round(v, 1).tolist() for k, v in target.items()})
def unpack(x):
    return {r: tuple(x[i*4:i*4+4]) for i, r in enumerate(USE)}
res = {}
for n in names:
    tgt = {k: target[k]+np.array(BIAS.get(n, {}).get(k, [0, 0, 0])) for k in keys}
    def loss(x):
        adj = unpack(x); e = 0
        for k in keys:
            m = sc.lab(sc.simulate(G[n][k][2], adj)).mean(0)
            e += ((m-tgt[k])**2).sum()
        return e+LAM*(x**2).sum()
    r = minimize(loss, np.zeros(len(USE)*4), method='L-BFGS-B', bounds=[(-.7, .7)]*(len(USE)*4), options=dict(eps=.012, maxiter=60, maxfun=2500))
    xi = np.round(r.x*100)/100
    adj = unpack(xi)
    res[n] = {k: [int(round(v*100)) for v in adj[k]] for k in adj}
    b = [np.linalg.norm(base[n][k]-target[k]) for k in keys]; a = [np.linalg.norm(sc.lab(sc.simulate(G[n][k][2], adj)).mean(0)-target[k]) for k in keys]
    print(f'{n:15s} dE to target before {np.mean(b):5.1f} after {np.mean(a):4.1f} worst {max(a):4.1f}  ', {k: v for k, v in res[n].items() if any(v)}, flush=True)
json.dump(res, open(OUT, 'w'), indent=1)
json.dump({k: v.tolist() for k, v in target.items()}, open(OUT+'.target', 'w'))
