# Read each GeoTIFF's size and georeferencing from its header only, then locate the quad corners in thumbnail space.
import json, os, time
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', GDAL_HTTP_MAX_RETRY='3', GDAL_HTTP_RETRY_DELAY='1')
from concurrent.futures import ThreadPoolExecutor as TP
import numpy as np, rasterio
from pyproj import Transformer
R = json.load(open('site_rows.json'))
def one(r):
    try:
        with rasterio.open(r['tif']) as d:
            W, H = d.width, d.height; inv = ~d.transform; crs = d.crs.to_wkt(); ov = d.overviews(1)
        t = Transformer.from_crs('EPSG:4267', crs, always_xy=True)
        w, s, e, n = r['bbox']
        pts = [(w, n), (e, n), (e, s), (w, s)]
        px = [inv*t.transform(*p) for p in pts]
        return r['id'], dict(W=W, H=H, ov=ov, uv=[[round(x/W, 5), round(y/H, 5)] for x, y in px])
    except Exception as ex:
        return r['id'], dict(err=str(ex)[:120])
t0 = time.time()
with TP(12) as e: out = dict(e.map(one, R))
json.dump(out, open('georef.json', 'w'))
bad = [k for k, v in out.items() if 'err' in v]
print('ok', len(out)-len(bad), 'failed', len(bad), round(time.time()-t0), 's', [out[k]['err'] for k in bad[:2]])
good = [v for v in out.values() if 'err' not in v]
print('overviews sample', good[0]['ov'], 'sizes', good[0]['W'], good[0]['H'])
uv = np.array([v['uv'] for v in good])
print('left u', np.round(np.percentile(uv[:, [0, 3], 0], [0, 50, 100]), 3), 'right u', np.round(np.percentile(uv[:, [1, 2], 0], [0, 50, 100]), 3))
print('top v', np.round(np.percentile(uv[:, [0, 1], 1], [0, 50, 100]), 3), 'bottom v', np.round(np.percentile(uv[:, [2, 3], 1], [0, 50, 100]), 3))
