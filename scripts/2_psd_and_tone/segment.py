# Classify each clipped tile into water and vegetation on a blurred Lab image; save masks and QA maps.
import glob, os, sys, pickle, numpy as np, rasterio, cv2
from PIL import Image
CLIP, TAG, S = sys.argv[1], sys.argv[2], sys.argv[3]
def lab(rgb):
    return cv2.cvtColor((rgb.astype(np.float32)/255), cv2.COLOR_RGB2LAB)
tiles = {}
for f in sorted(glob.glob(CLIP+'/*.tif')):
    with rasterio.open(f) as d:
        a = np.moveaxis(d.read(), 0, -1)
    small = cv2.resize(cv2.GaussianBlur(a, (0, 0), 3), (a.shape[1]//4, a.shape[0]//4), interpolation=cv2.INTER_AREA)
    tiles[os.path.basename(f).split('_')[1]] = (f, lab(small))
pool = np.concatenate([t[1].reshape(-1, 3)[::37] for t in tiles.values()])
print('pooled b* percentiles', np.round(np.percentile(pool[:, 2], [1, 10, 25, 50, 75, 90, 99]), 1))
th, _ = cv2.threshold(np.clip((pool[:, 2]+60)/120*255, 0, 255).astype(np.uint8), 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
TH = th/255*120-60
print('Otsu b* threshold', round(TH, 1))
out = {}
for n, (f, L) in tiles.items():
    usable = (L[..., 0] > 18) & (L[..., 1] < 8)
    water = usable & (L[..., 2] < TH)
    veg = usable & (L[..., 2] >= TH) & (L[..., 1] < 0)
    kern = np.ones((5, 5), np.uint8)
    water = cv2.erode(water.astype(np.uint8), kern).astype(bool); veg = cv2.erode(veg.astype(np.uint8), kern).astype(bool)
    out[n] = (f, water, veg)
    w = L[water].mean(0) if water.sum() else [np.nan]*3; v = L[veg].mean(0) if veg.sum() else [np.nan]*3
    print(f'{n:20s} water {100*water.mean():5.1f}% Lab {w[0]:5.1f} {w[1]:6.1f} {w[2]:6.1f}   veg {100*veg.mean():5.1f}% Lab {v[0]:5.1f} {v[1]:6.1f} {v[2]:6.1f}')
pickle.dump(dict(th=TH, tiles=out), open(f'{S}/seg_{TAG}.pkl', 'wb'))
names = sorted(out); cols = 5 if len(names) > 6 else 3
h, w = next(iter(out.values()))[1].shape
sc = 0.14; cw = int(w*sc)+6; ch = int(h*sc)+6
T = Image.new('RGB', (cols*cw, int(np.ceil(len(names)/cols))*ch), 'white')
for i, n in enumerate(names):
    m = np.full((h, w, 3), 255, np.uint8); m[out[n][1]] = (60, 140, 230); m[out[n][2]] = (50, 150, 60)
    T.paste(Image.fromarray(m).resize((int(w*sc), int(h*sc)), Image.NEAREST), ((i % cols)*cw, (i//cols)*ch))
T.save(f'{S}/qa/seg_{TAG}.png')
