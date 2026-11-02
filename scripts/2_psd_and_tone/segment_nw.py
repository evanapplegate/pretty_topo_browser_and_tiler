# NW Florida masks: three water depth tints, forest and swamp split by hue per tile, and pale clearings.
import glob, os, sys, pickle, numpy as np, rasterio, cv2
from PIL import Image
CLIP, TAG, S = sys.argv[1], sys.argv[2], sys.argv[3]
kern = np.ones((5, 5), np.uint8)
def tidy(m):
    return cv2.erode(m.astype(np.uint8), kern).astype(bool)
COL = dict(water_pale=(205, 230, 245), water_mid=(110, 190, 235), water_deep=(30, 90, 200), clear=(240, 225, 120),
           forest_dark=(20, 90, 30), forest_light=(90, 170, 60), swamp_dark=(0, 110, 110), swamp_light=(90, 200, 180))
out = {}
for f in sorted(glob.glob(CLIP+'/*.tif')):
    with rasterio.open(f) as d:
        a = np.moveaxis(d.read(), 0, -1)
    small = cv2.resize(cv2.GaussianBlur(a, (0, 0), 3), (a.shape[1]//4, a.shape[0]//4), interpolation=cv2.INTER_AREA)
    Lab = cv2.cvtColor(small.astype(np.float32)/255, cv2.COLOR_RGB2LAB); L, A, B = Lab[..., 0], Lab[..., 1], Lab[..., 2]
    C = np.hypot(A, B); H = np.degrees(np.arctan2(B, A)) % 360
    usable = (L > 18) & (A < 8)
    water = usable & (((L > 85) & (C < 12)) | ((C >= 12) & (B < -3)))
    D = L-.5*C
    land = usable & ~water & (B >= 3) & (C >= 12) & (H >= 95) & (H < 190)
    clear = land & (L >= 78)
    wood = land & (L < 78)
    h8 = np.clip((H[wood]-95)/95*255, 0, 255).astype(np.uint8).reshape(-1, 1)
    th, _ = cv2.threshold(h8, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    T = 95+th/255*95
    fo, sw = wood & (H < T), wood & (H >= T)
    gap = H[sw].mean()-H[fo].mean() if sw.any() and fo.any() else 0
    if gap < 8:
        fo, sw = wood, np.zeros_like(wood)
    m = dict(water_pale=water & (D >= 85), water_mid=water & (D >= 71) & (D < 85), water_deep=water & (D < 71), clear=clear)
    for name, r in (('forest', fo), ('swamp', sw)):
        med = np.median(L[r]) if r.any() else 0
        m[name+'_dark'] = r & (L <= med); m[name+'_light'] = r & (L > med)
    m = {k: tidy(v) for k, v in m.items()}
    n = os.path.basename(f).split('_')[1]
    out[n] = dict(f=f, masks=m)
    print(f'{n:18s} hueT {T:5.1f} gap {gap:4.1f} | '+' '.join(f'{k.replace("water_","w").replace("forest_","f").replace("swamp_","s")} {100*v.mean():4.1f}%' for k, v in m.items()), flush=True)
pickle.dump(dict(th=None, tiles=out), open(f'{S}/seg_{TAG}.pkl', 'wb'))
names = sorted(out); cols = 7
h, w = next(iter(out.values()))['masks']['clear'].shape
sc = 0.19; cw = int(w*sc)+6; ch = int(h*sc)+6
Q = Image.new('RGB', (cols*cw, int(np.ceil(len(names)/cols))*ch), 'white')
for i, n in enumerate(names):
    v = np.full((h, w, 3), 255, np.uint8)
    for k, c in COL.items():
        v[out[n]['masks'][k]] = c
    Q.paste(Image.fromarray(v).resize((int(w*sc), int(h*sc)), Image.NEAREST), ((i % cols)*cw, (i//cols)*ch))
Q.save(f'{S}/qa/seg_{TAG}.png')
