# Measure Photoshop's flattened render per tile, compare to target and to the model, write bias for a refit.
import glob, json, os, sys, numpy as np, rasterio, tifffile
sys.path.insert(0, sys.argv[1])
import sc
S, TAG, TIF, SL, CLIP, BIASOUT = sys.argv[1:7]
target = {k: np.array(v) for k, v in json.load(open(SL+'.target')).items()}
sl = json.load(open(SL))
G = sc.groups(TAG, S); keys = sorted(target)
A = np.memmap(TIF, 'uint8', 'r', shape=tuple(int(v) for v in os.environ['RAW'].split(','))) if TIF.endswith('.raw') else tifffile.imread(TIF)
off = {}
fs = glob.glob(CLIP+'/*.tif')
bs = {os.path.basename(f).split('_')[1]: rasterio.open(f) for f in fs}
L0 = min(b.bounds.left for b in bs.values()); T0 = max(b.bounds.top for b in bs.values())
print(A.shape, 'alpha band' if A.shape[2] > 3 else '')
bias = {}; ws = []
for n in sorted(G):
    b = bs[n]; x = int(round((b.bounds.left-L0)/b.res[0])); y = int(round((T0-b.bounds.top)/b.res[1]))
    adj = {k: tuple(v/100 for v in vv) for k, vv in sl[n].items()}
    before = []; after = []; model = []; bias[n] = {}
    for k in [k for k in keys if k in G[n]]:
        yy, xx, px = G[n][k]
        real = sc.lab(A[yy+y, xx+x, :3].astype(np.float32)/255).mean(0)
        sim = sc.lab(sc.simulate(px, adj)).mean(0)
        base = sc.lab(px).mean(0)
        before.append(np.linalg.norm(base-target[k])); after.append(np.linalg.norm(real-target[k])); model.append(np.linalg.norm(real-sim))
        bias[n][k] = (sim-real).tolist()
    ws.append((before, after))
    print(f'{n:15s} dE to target before {np.mean(before):5.1f}  in Photoshop {np.mean(after):4.1f}  worst {max(after):4.1f}  model error {np.mean(model):4.1f}')
b = [x for w in ws for x in w[0]]; a = [x for w in ws for x in w[1]]
print('mean dE before %.1f after %.1f | worst group before %.1f after %.1f' % (np.mean(b), np.mean(a), max(b), max(a)))
json.dump(bias, open(BIASOUT, 'w'))
