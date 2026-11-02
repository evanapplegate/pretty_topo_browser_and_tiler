# Read each GeoTIFF's 1/8 overview over HTTP, warp the quad to a north-up rectangle, and save atomically so reruns resume.
import json, os, sys, time
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', GDAL_HTTP_MAX_RETRY='4', GDAL_HTTP_RETRY_DELAY='2',
                  GDAL_HTTP_TIMEOUT='60', GDAL_HTTP_MERGE_CONSECUTIVE_RANGES='YES', VSI_CACHE='FALSE', GDAL_CACHEMAX='64')
from concurrent.futures import ThreadPoolExecutor as TP
import cv2, numpy as np, rasterio
from rasterio.enums import Resampling
from pyproj import Transformer
from PIL import Image
OUT = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/topo_finder/site/clip8/'
R = json.load(open('site_rows.json')); OW, OH, TH = 740, 850, int(sys.argv[1])
if len(sys.argv) > 2: R = R[:int(sys.argv[2])]
cv2.setNumThreads(1)
def one(r):
    p = f"{OUT}{r['scan']}.jpg"
    if os.path.exists(p): return r['scan'], 'skip', 0
    t0 = time.time()
    try:
        with rasterio.open(r['tif']) as d:
            W, H = d.width, d.height; inv = ~d.transform; crs = d.crs.to_wkt(); ov = d.overviews(1)
            a = np.moveaxis(d.read([1, 2, 3], out_shape=(3, round(H/8), round(W/8)), resampling=Resampling.nearest), 0, -1)
        t = Transformer.from_crs('EPSG:4267', crs, always_xy=True); w, s, e, n = r['bbox']
        src = np.array([inv*t.transform(*q) for q in ((w, n), (e, n), (e, s), (w, s))], np.float32)*np.array([a.shape[1]/W, a.shape[0]/H], np.float32)
        c = src.mean(0); src = c+(src-c)*.997
        M = cv2.getPerspectiveTransform(src, np.array([[0, 0], [OW, 0], [OW, OH], [0, OH]], np.float32))
        b = cv2.warpPerspective(a, M, (OW, OH), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        Image.fromarray(b).save(p+'.tmp', 'JPEG', quality=84, optimize=True)
        os.replace(p+'.tmp', p)
        return r['scan'], '8' in map(str, ov) and 'ok' or f'no 8 in {ov}', time.time()-t0
    except Exception as ex:
        return r['scan'], 'ERR '+str(ex)[:100], time.time()-t0
t0 = time.time(); fails = []; n = 0; kept = 0
with TP(TH) as e:
    for scan, st, dt in e.map(one, R):
        n += 1
        if st.startswith('ERR') or st.startswith('no 8'): fails.append((scan, st))
        if n % 50 == 0 or n == len(R): print(n, 'of', len(R), round(time.time()-t0), 's', 'issues', len(fails), flush=True)
json.dump(fails, open('hires_issues.json', 'w'))
print('done', n, 'issues', len(fails), fails[:3], round(time.time()-t0), 's')
