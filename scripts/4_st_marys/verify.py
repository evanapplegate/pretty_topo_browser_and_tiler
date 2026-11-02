# Verify the finished file itself: format, grid, seams and detail, reading only from the delivered BigTIFFs.
import numpy as np, cv2, rasterio, tone as t
from rasterio.windows import Window
from rasterio.enums import Resampling
from PIL import Image, ImageDraw
D = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos/'
A = D+'GA_Woodbine_Fernandina_1979-81_24000_mosaic.tif'; B = D+'GA_Woodbine_Fernandina_1979-81_24000_mosaic_matched.tif'
print('magic', open(B, 'rb').read(4), '(II+ is BigTIFF)')
a = rasterio.open(A); b = rasterio.open(B)
print(b.crs.to_string(), b.width, b.height, b.count, b.dtypes[0], b.compression.name, b.tags(ns='IMAGE_STRUCTURE').get('LAYOUT'), 'overviews', b.overviews(1))
print('same grid as raw', a.transform.almost_equals(b.transform, 1e-12) and a.shape == b.shape, '| bounds', [round(x, 4) for x in b.bounds], '| mask all valid', bool(b.read_masks(1, out_shape=(500, 430)).min() == 255))
CW, CH = 5886, 6820; FAC = 4
qa = np.moveaxis(a.read(out_shape=(3, a.height//FAC, a.width//FAC), resampling=Resampling.average), 0, -1).astype(np.float32)/255
qb = np.moveaxis(b.read(out_shape=(3, b.height//FAC, b.width//FAC), resampling=Resampling.average), 0, -1).astype(np.float32)/255
T, grid, rows, cols = t.load(); h, w = T[0]['lab'].shape[:2]
la = t.cut(T, t.rgb2oklab(qa).astype(np.float32), rows, cols, h, w); lb = t.cut(T, t.rgb2oklab(qb).astype(np.float32), rows, cols, h, w)
print('from file, seam visibility raw', {k: round(v, 2) for k, v in t.visibility(T, grid, la).items()})
print('from file, seam visibility matched', {k: round(v, 2) for k, v in t.visibility(T, grid, lb).items()})
m = t.metrics(T, grid, lb, la); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items() if k != 'worst'})
# Native-resolution detail, sheet centres.
R = []
for r in range(rows):
    for c in range(cols):
        win = Window(c*CW+CW//2-1024, r*CH+CH//2-1024, 2048, 2048)
        x = cv2.cvtColor(np.moveaxis(a.read(window=win), 0, -1), cv2.COLOR_RGB2GRAY).astype(np.float32); y = cv2.cvtColor(np.moveaxis(b.read(window=win), 0, -1), cv2.COLOR_RGB2GRAY).astype(np.float32)
        hp = lambda i: (i-cv2.GaussianBlur(i, (0, 0), 3)).std()
        R.append(hp(y)/hp(x))
print('native detail kept min %.3f median %.3f max %.3f' % (min(R), float(np.median(R)), max(R)))
Image.MAX_IMAGE_PIXELS = None
# Native-pixel crops at seam crossings and hard spots, raw above, matched below.
pts = [(CW, CH), (2*CW, CH), (CW, 2*CH), (2*CW, 2*CH), (2*CW, int(1.55*CH)), (int(1.4*CW), CH), (CW, int(2.45*CH))]
S = 330; O = Image.new('RGB', (len(pts)*(S+4), 2*S+4), 'white')
for i, (x, y) in enumerate(pts):
    for k, d in enumerate((a, b)):
        c = np.moveaxis(d.read(window=Window(x-S//2, y-S//2, S, S)), 0, -1)
        O.paste(Image.fromarray(c), (i*(S+4), k*(S+4)))
O.save('qa/final_native.png'); print(O.size)
