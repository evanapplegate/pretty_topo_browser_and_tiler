# Louisiana masks: water is light, marsh is dark, farmland is yellow; lightness split is per tile because ink density varies.
import glob, os, sys, pickle, numpy as np, rasterio, cv2
from PIL import Image
CLIP, TAG, S = sys.argv[1], sys.argv[2], sys.argv[3]
MARGIN, FARM_B = 6, 14
def lab(rgb):
    return cv2.cvtColor((rgb.astype(np.float32)/255), cv2.COLOR_RGB2LAB)
kern = np.ones((5, 5), np.uint8)
def tidy(m):
    return cv2.erode(m.astype(np.uint8), kern).astype(bool)
out = {}
for f in sorted(glob.glob(CLIP+'/*.tif')):
    with rasterio.open(f) as d:
        a = np.moveaxis(d.read(), 0, -1)
    small = cv2.resize(cv2.GaussianBlur(a, (0, 0), 3), (a.shape[1]//4, a.shape[0]//4), interpolation=cv2.INTER_AREA)
    Lab = lab(small); L, A, B = Lab[..., 0], Lab[..., 1], Lab[..., 2]
    cool = B < FARM_B
    th, _ = cv2.threshold(np.clip(L[cool]*2.55, 0, 255).astype(np.uint8).reshape(-1, 1), 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    T = th/2.55
    usable = (L > 18) & (A < 8)
    water = tidy(usable & cool & (L > T+MARGIN))
    veg = tidy(usable & cool & (L < T-MARGIN))
    farm = tidy(usable & (B >= FARM_B))
    n = os.path.basename(f).split('_')[1]
    out[n] = (f, water, veg, farm)
    s = lambda m: (f'{100*m.mean():5.1f}% ' + ' '.join(f'{v:6.1f}' for v in Lab[m].mean(0))) if m.sum() else '  none'
    print(f'{n:20s} T {T:4.1f}  water {s(water)}  marsh {s(veg)}  farm {s(farm)}', flush=True)
pickle.dump(dict(th=None, tiles=out), open(f'{S}/seg_{TAG}.pkl', 'wb'))
names = sorted(out); cols = 5
h, w = next(iter(out.values()))[1].shape
sc = 0.26; cw = int(w*sc)+6; ch = int(h*sc)+6
Q = Image.new('RGB', (cols*cw, int(np.ceil(len(names)/cols))*ch), 'white')
for i, n in enumerate(names):
    m = np.full((h, w, 3), 255, np.uint8); m[out[n][1]] = (60, 140, 230); m[out[n][2]] = (50, 120, 90); m[out[n][3]] = (230, 200, 40)
    Q.paste(Image.fromarray(m).resize((int(w*sc), int(h*sc)), Image.NEAREST), ((i % cols)*cw, (i//cols)*ch))
Q.save(f'{S}/qa/seg_{TAG}.png')
