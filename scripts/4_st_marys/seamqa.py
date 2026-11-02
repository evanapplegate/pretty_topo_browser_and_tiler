# Seam QA on the raw lossless mosaic: leftover neatline darkening, and how far map features are offset along each seam.
import glob, numpy as np, cv2, rasterio
M = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos/GA_Woodbine_Fernandina_1979-81_24000_mosaic.tif'
COLS, ROWS = 5886, 6820
d = rasterio.open(M); A = np.moveaxis(d.read(), 0, -1); g = A.mean(2).astype(np.float32)
hp = lambda a: a-cv2.GaussianBlur(a.reshape(-1, 1).astype(np.float32), (1, 41), 10).ravel()
def shift(a, b, L=360, R=14):
    a = hp(a); b = hp(b); out = []
    for i in range(0, len(a)-L, L//2):
        x = a[i:i+L]; y = b[i+R:i+L-R]
        if x.std() < 4 or y.std() < 4: continue
        cc = np.array([np.corrcoef(x[k:k+len(y)], y)[0, 1] for k in range(2*R+1)])
        k = int(cc.argmax())
        if cc[k] > .5 and 0 < k < 2*R: out.append(k-R)
    return out
dips = []; al = {}
for r in range(3):
    for c in range(3):
        if c < 2:
            a = g[r*ROWS:(r+1)*ROWS]; x = (c+1)*COLS; p = a[:, x-16:x+16].mean(0)
            dips.append(float(min(p[:12].mean(), p[-12:].mean())-p[12:20].min()))
            al[f'r{r}c{c} EW-neighbours'] = shift(a[:, x-4:x-1].mean(1), a[:, x+1:x+4].mean(1))
        if r < 2:
            a = g[:, c*COLS:(c+1)*COLS]; y = (r+1)*ROWS; p = a[y-16:y+16].mean(1)
            dips.append(float(min(p[:12].mean(), p[-12:].mean())-p[12:20].min()))
            al[f'r{r}c{c} NS-neighbours'] = shift(a[y-4:y-1].mean(0), a[y+1:y+4].mean(0))
v = np.array([s for x in al.values() for s in x])
print('seams', len(dips), 'worst darkening', round(max(dips), 1), '| offset blocks', len(v), 'median %+.1f p50|s| %.1f p90|s| %.1f max|s| %d px' % (np.median(v), np.median(abs(v)), np.percentile(abs(v), 90), abs(v).max()))
