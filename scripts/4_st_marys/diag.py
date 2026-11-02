# Sample the pink flats and the blue contours: raw, global-only and final colour.
import numpy as np, cv2, rasterio, tone as t
from rasterio.windows import Window
T, grid, rows, cols = t.load(); base = [x['lab'] for x in T]
Z = np.load('work/final_q.npz'); L = [Z[str(x['s']['scan'])].astype(np.float32) for x in T]
M = t.fit_global(T, grid, order=3, lam=.005); G = [t.apply_global(x, m, 3) for x, m in zip(base, M)]
names = [x['s']['name'] for x in T]
C = lambda X: t.canvas(T, X, rows, cols)
b, g, l = C(base), C(G), C(L)
CW, CH = 5886//4, 6820//4
y0, x0 = int(1.55*CH), 2*CW
r = b[y0-30:y0+30, x0-40:x0-5]; m = r[..., 0] > .86
f = lambda a: np.round(a[y0-30:y0+30, x0-40:x0-5][m].mean(0), 3)
print('pale flats pixels', int(m.sum()), 'raw', f(b), 'global', f(g), 'final', f(l))
n = 'Cumberland Island South'
for nm in ('Harrietts Bluff', 'Cumberland Island North', 'Gross', 'Woodbine'):
    x = T[names.index(nm)]; p = np.array([[.60, -.02, -.06], [.75, -.03, -.05], [.92, -.03, -.01], [.95, -.015, .0], [.97, -.01, .005], [.80, .01, .06]], np.float32)
    o = t.apply_global(p, M[names.index(nm)], 3)
    print(f'{nm:24s} global maps', ' '.join(f'{q[0]:.2f},{q[1]:+.3f},{q[2]:+.3f}>{v[0]:.2f},{v[1]:+.3f},{v[2]:+.3f}' for q, v in zip(p, o)))
A = rasterio.open('/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos/GA_Woodbine_Fernandina_1979-81_24000_mosaic.tif')
B = rasterio.open('/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos/GA_Woodbine_Fernandina_1979-81_24000_mosaic_matched.tif')
win = Window(2*5886-300, 6820-40, 330, 300)
a = t.rgb2oklab(np.moveaxis(A.read(window=win), 0, -1).astype(np.float32)/255); c = t.rgb2oklab(np.moveaxis(B.read(window=win), 0, -1).astype(np.float32)/255)
ink = (a[..., 2] < -.03)
print('blue ink px', int(ink.sum()), 'raw', np.round(a[ink].mean(0), 3), 'final', np.round(c[ink].mean(0), 3), '| raw b pct', np.round(np.percentile(a[..., 2], [1, 5, 25, 50, 75]), 3))
