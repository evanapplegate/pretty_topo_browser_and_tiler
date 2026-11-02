# Build the candidate, then expose any sheet-shaped patches by exaggerating low-frequency colour within each land and water class.
import sys, json, numpy as np, cv2, tone as t
from PIL import Image
KW = dict(along=30, node=24, rounds=5); TAG = 'run6'
T, grid, rows, cols = t.load()
base = [x['lab'] for x in T]
L = t.stack(T, grid, base, rows, cols, **KW)
np.savez('work/final_q.npz', **{str(x['s']['scan']): l.astype(np.float16) for x, l in zip(T, L)})
v = t.visibility(T, grid, L); m = t.metrics(T, grid, L, base)
print({k: round(a, 2) for k, a in v.items()}); print({a: (round(b, 3) if isinstance(b, float) else b) for a, b in m.items() if a != 'worst'})
def table(X):
    K = [t.classify(a) for a in X]; R = {}
    for i, n in enumerate(t.CLASSES):
        R[n] = [X[j][K[j] == i].mean(0) if (K[j] == i).mean() > .03 else None for j in range(len(X))]
    return R
K0 = [t.classify(a) for a in L]
for lab, X in (('raw', base), ('final', L)):
    for i, n in enumerate(t.CLASSES):
        v_ = np.array([X[j][K0[j] == i].mean(0) for j in range(len(X)) if (K0[j] == i).mean() > .03])
        print(f'{lab:6s}{n:9s} sheets {len(v_)} mean L {v_[:,0].mean():.3f} a {v_[:,1].mean():+.3f} b {v_[:,2].mean():+.3f} | spread L {v_[:,0].std()*100:.2f} a {v_[:,1].std()*100:.2f} b {v_[:,2].std()*100:.2f}')
def exag(X, K):
    C = t.canvas(T, X, rows, cols); Kc = t.canvas(T, K, rows, cols)[..., 0]; out = np.full(C.shape, .92, np.float32); 
    for i, gain in ((0, 3.5), (1, 3.5), (3, 3.5)):
        m = (Kc == i).astype(np.float32); den = t.gblur(m, 20)
        mu = np.stack([t.gblur(C[..., c]*m, 20) for c in range(3)], -1)/np.maximum(den, 1e-3)[..., None]
        tau = np.array([np.median(C[..., c][Kc == i]) for c in range(3)])
        e = tau+(mu-tau)*gain
        s = (Kc == i)&(den > .08); out[s] = e[s]
    return (np.clip(t.oklab2rgb(out), 0, 1)*255).astype(np.uint8)
a = exag(base, K0); b = exag(L, K0)
h = a.shape[0]//5; w = a.shape[1]//5
S = np.full((h, 2*w+16, 3), 255, np.uint8)
S[:, :w] = cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA); S[:, w+16:] = cv2.resize(b, (w, h), interpolation=cv2.INTER_AREA)
Image.fromarray(S).save(f'qa/{TAG}_exag.png')
G = [t.gamut_map(l) for l in L]
Image.fromarray(t.mosaic(T, G, rows, cols, 2)).resize((1103, 1278), Image.LANCZOS).save(f'qa/{TAG}.png')
t.seam_crops(T, grid, G, rows, cols, f'qa/{TAG}_seams.png')
