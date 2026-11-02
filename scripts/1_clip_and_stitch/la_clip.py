# Clip each sheet to its measured neatline and resample onto a shared NAD27 lat/lon grid.
# Target pixels map through the sheet georef, then a displacement that lands the
# inner side of the printed neatline exactly on the nominal 7.5' cell edge.
import glob, re, sys, json, os
import numpy as np, rasterio, rasterio.enums, cv2
from rasterio.transform import Affine
from pyproj import Transformer
from scipy.interpolate import RectBivariateSpline
J, OUTDIR, MARGIN, COMPRESS = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
only = sys.argv[5] if len(sys.argv) > 5 else None
COLS, ROWS = 5980, 6820
meas = json.load(open(J))
os.makedirs(OUTDIR, exist_ok=True)
for f in sorted(glob.glob('LA_*_tif/*.tif')):
    name = f.split('/')[1].split('_')[1]
    if only and name != only: continue
    x = open(f+'.xml', errors='ignore').read()
    b = {k: float(v) for k, v in re.findall(r'<(westbc|eastbc|northbc|southbc)>([^<]+)', x)}
    W, E, N, S = b['westbc'], b['eastbc'], b['northbc'], b['southbc']
    m = meas[name]
    stroke = float(np.median([m[e]['width'] for e in 'WENS']))
    def inset(edge, s):
        return np.polyval(m[edge]['coef'], s) + stroke + MARGIN
    with rasterio.open(f) as d:
        src = np.moveaxis(d.read(), 0, -1)
        t = Transformer.from_crs('EPSG:4267', d.crs, always_xy=True)
        inv = ~d.transform
    g = 128
    uc = np.linspace(0, 1, g+1); vc = np.linspace(0, 1, g+1)
    U, V = np.meshgrid(uc, vc)
    X, Y = t.transform(W+(E-W)*U, N+(S-N)*V)
    px, py = inv*(X, Y)
    px = np.asarray(px)+(1-U)*inset('W', V)-U*inset('E', V)-0.5
    py = np.asarray(py)+(1-V)*inset('N', U)-V*inset('S', U)-0.5
    ui = (np.arange(COLS)+.5)/COLS; vi = (np.arange(ROWS)+.5)/ROWS
    mx = RectBivariateSpline(vc, uc, px)(vi, ui).astype(np.float32)
    my = RectBivariateSpline(vc, uc, py)(vi, ui).astype(np.float32)
    out = cv2.remap(src, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    tr = Affine((E-W)/COLS, 0, W, 0, (S-N)/ROWS, N)
    opts = dict(driver='GTiff', width=COLS, height=ROWS, count=3, dtype='uint8', crs='EPSG:4267', transform=tr,
                tiled=True, blockxsize=512, blockysize=512, photometric='RGB')
    if COMPRESS == 'jpeg':
        opts.update(compress='JPEG', jpeg_quality=92, photometric='YCBCR')
    else:
        opts.update(compress='DEFLATE', predictor=2, zlevel=9)
    base = os.path.basename(f).replace('_geo.tif', '_clip.tif').replace(' ', '')
    p = os.path.join(OUTDIR, base)
    with rasterio.open(p, 'w', **opts) as o:
        o.write(np.moveaxis(out, -1, 0))
        o.colorinterp = [rasterio.enums.ColorInterp.red, rasterio.enums.ColorInterp.green, rasterio.enums.ColorInterp.blue]
    print(name, 'stroke %.2f' % stroke, p, os.path.getsize(p)//1048576, 'MB')
