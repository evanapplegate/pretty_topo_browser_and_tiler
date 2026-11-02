# Check the delivered BigTIFFs directly: format, grid, seam visibility, detail, and native-pixel crops at seam junctions.
import numpy as np, cv2, rasterio, cfg
from cfg import t
from rasterio.windows import Window
from rasterio.enums import Resampling
from PIL import Image
A = cfg.DATA+'/FL_CapeCanaveral_1976_24000_mosaic_lossless.tif'; B = cfg.DATA+'/FL_CapeCanaveral_1976_24000_mosaic_tonemapped.tif'
print('magic', open(B, 'rb').read(4), '(II+ is BigTIFF)')
a = rasterio.open(A); b = rasterio.open(B)
print(b.crs.to_string(), b.width, b.height, b.count, b.dtypes[0], b.compression.name, b.tags(ns='IMAGE_STRUCTURE').get('LAYOUT'), 'overviews', b.overviews(1))
print('same grid as raw', a.transform.almost_equals(b.transform, 1e-12) and a.shape == b.shape, '| bounds', [round(x, 4) for x in b.bounds])
CW, CH = 6036, 6816; F = 4
qa = np.moveaxis(a.read(out_shape=(3, a.height//F, a.width//F), resampling=Resampling.average), 0, -1).astype(np.float32)/255
qb = np.moveaxis(b.read(out_shape=(3, b.height//F, b.width//F), resampling=Resampling.average), 0, -1).astype(np.float32)/255
T, grid, rows, cols = t.load(); h, w = T[0]['lab'].shape[:2]
la = t.cut(T, t.rgb2oklab(qa).astype(np.float32), rows, cols, h, w); lb = t.cut(T, t.rgb2oklab(qb).astype(np.float32), rows, cols, h, w)
print('raw    ', {k: round(v, 2) for k, v in t.visibility(T, grid, la).items()})
print('matched', {k: round(v, 2) for k, v in t.visibility(T, grid, lb).items()})
m = t.metrics(T, grid, lb, la); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items() if k != 'worst'})
print('raw spread', {k: round(v, 3) for k, v in t.metrics(T, grid, la, la).items() if 'spread' in k})
R = []
for r in range(rows):
    for c in range(cols):
        win = Window(c*CW+CW//2-1024, r*CH+CH//2-1024, 2048, 2048)
        x = cv2.cvtColor(np.moveaxis(a.read(window=win), 0, -1), cv2.COLOR_RGB2GRAY).astype(np.float32); y = cv2.cvtColor(np.moveaxis(b.read(window=win), 0, -1), cv2.COLOR_RGB2GRAY).astype(np.float32)
        hp = lambda i: (i-cv2.GaussianBlur(i, (0, 0), 3)).std()
        R.append(hp(y)/hp(x))
print('native detail kept min %.3f median %.3f max %.3f' % (min(R), float(np.median(R)), max(R)))
pts = [(CW, CH), (CW, 2*CH), (CW, CH//2), (CW, int(1.35*CH)), (int(.5*CW), CH), (int(1.5*CW), CH), (int(1.2*CW), 2*CH)]
S = 330; O = Image.new('RGB', (len(pts)*(S+4), 2*S+4), 'white')
for i, (x, y) in enumerate(pts):
    for k, d in enumerate((a, b)):
        c = np.moveaxis(d.read(window=Window(x-S//2, y-S//2, S, S)), 0, -1)
        O.paste(Image.fromarray(c), (i*(S+4), k*(S+4)))
O.save('qa/final_native.png')
ra = np.moveaxis(a.read(out_shape=(3, 1704, 1006), resampling=Resampling.average), 0, -1); rb = np.moveaxis(b.read(out_shape=(3, 1704, 1006), resampling=Resampling.average), 0, -1)
S2 = np.full((1704, 2032, 3), 255, np.uint8); S2[:, :1006] = ra; S2[:, -1006:] = rb
Image.fromarray(S2).save(cfg.DATA+'/before_after.png')
