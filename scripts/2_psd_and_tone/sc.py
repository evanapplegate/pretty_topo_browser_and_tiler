# Selective Color model plus sampling and fitting helpers shared by fit and verify steps.
import pickle, numpy as np, cv2, rasterio
FARM_MIN = .005
GROUP_MIN = .0005
RANGES = ['reds', 'yellows', 'greens', 'cyans', 'blues', 'magentas', 'whites', 'neutrals', 'blacks']
def simulate(rgb, adj):
    # rgb Nx3 in 0..1, adj dict range -> (c, m, y, k) in -1..1, Relative method
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    mx = rgb.max(1); mn = rgb.min(1); mid = rgb.sum(1)-mx-mn
    prim = mx-mid; sec = mid-mn
    scales = dict(reds=(r == mx)*prim, cyans=(r == mn)*sec, greens=(g == mx)*prim, magentas=(g == mn)*sec,
                  blues=(b == mx)*prim, yellows=(b == mn)*sec,
                  whites=(mn > .5)*(2*mn-1), blacks=(mx < .5)*(1-2*mx),
                  neutrals=1-(np.abs(mx-.5)+np.abs(mn-.5)))
    d = np.zeros_like(rgb)
    for name, v in adj.items():
        c, m, y, k = v
        if not (c or m or y or k): continue
        s = scales[name]
        for i, a in enumerate((c, m, y)):
            val = rgb[:, i]
            res = ((-1-a)*k-a)*(1-val)
            d[:, i] += s*np.clip(res, -val, 1-val)
    return np.clip(rgb+d, 0, 1)
def lab(rgb):
    return cv2.cvtColor(rgb.astype(np.float32).reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3)
def groups(TAG, S, n=40000, seed=7):
    # For each tile: raw-pixel samples of water and vegetation, split into darker and lighter halves
    seg = pickle.load(open(f'{S}/seg_{TAG}.pkl', 'rb'))['tiles']; rng = np.random.default_rng(seed); out = {}
    if isinstance(next(iter(seg.values())), dict):
        for name, rec in seg.items():
            with rasterio.open(rec['f']) as d:
                a = np.moveaxis(d.read(), 0, -1)
            g = {}
            for k, m in rec['masks'].items():
                if m.mean() < GROUP_MIN: continue
                ys, xs = np.nonzero(m)
                i = rng.integers(0, len(ys), n)
                yy = np.minimum(ys[i]*4+rng.integers(0, 4, n), a.shape[0]-1); xx = np.minimum(xs[i]*4+rng.integers(0, 4, n), a.shape[1]-1)
                g[k] = (yy, xx, a[yy, xx].astype(np.float32)/255)
            out[name] = g
        return out
    for name, rec in seg.items():
        f, water, veg = rec[:3]; farm = rec[3] if len(rec) > 3 else None
        with rasterio.open(f) as d:
            a = np.moveaxis(d.read(), 0, -1)
        small = cv2.resize(cv2.GaussianBlur(a, (0, 0), 3), (a.shape[1]//4, a.shape[0]//4), interpolation=cv2.INTER_AREA)
        L = lab(small.reshape(-1, 3)/255.).reshape(small.shape)[..., 0]
        g = {}
        for cname, m in (('water', water), ('veg', veg)):
            med = np.median(L[m])
            for part, mm in (('dark', m & (L <= med)), ('light', m & (L > med))):
                ys, xs = np.nonzero(mm)
                i = rng.integers(0, len(ys), n)
                yy = np.minimum(ys[i]*4+rng.integers(0, 4, n), a.shape[0]-1); xx = np.minimum(xs[i]*4+rng.integers(0, 4, n), a.shape[1]-1)
                g[f'{cname}_{part}'] = (yy, xx, a[yy, xx].astype(np.float32)/255)
        if farm is not None and farm.mean() >= FARM_MIN:
            med = np.median(L[farm])
            for part, mm in (('dark', farm & (L <= med)), ('light', farm & (L > med))):
                ys, xs = np.nonzero(mm)
                i = rng.integers(0, len(ys), n)
                yy = np.minimum(ys[i]*4+rng.integers(0, 4, n), a.shape[0]-1); xx = np.minimum(xs[i]*4+rng.integers(0, 4, n), a.shape[1]-1)
                g[f'farm_{part}'] = (yy, xx, a[yy, xx].astype(np.float32)/255)
        out[name] = g
    return out
