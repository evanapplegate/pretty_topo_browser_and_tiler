# Add reviewed GeoTIFF URLs to the site: IDs, small clip, colour and size; the 1/8 pass runs afterwards.
import json, os, pickle, re, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor as TP
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', GDAL_HTTP_MAX_RETRY='3', GDAL_HTTP_RETRY_DELAY='1')
import cv2, numpy as np, rasterio, hue
from pyproj import Transformer
from PIL import Image
OUT = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/topo_finder/site/clip/'
cand, feat = pickle.load(open('scan.pkl', 'rb')); R = json.load(open('site_rows.json')); have = {r['tif'] for r in R}
urls = [u for u in json.load(open(sys.argv[1])) if u not in have]
scan = lambda u: int(re.search(r'_(\d+)_\d{4}_\d+_geo\.tif', u).group(1))
p = urllib.parse.urlencode(dict(where='scan_id IN (%s)' % ','.join(str(scan(u)) for u in urls), outFields='scan_id,md5', returnGeometry='false', f='json'))
md5 = {f['attributes']['scan_id']: f['attributes']['md5'] for f in json.load(urllib.request.urlopen(urllib.request.Request('https://energy.usgs.gov/arcgis/rest/services/topoview/ustOverlay/MapServer/0/query?'+p, headers={'User-Agent': 'curl/8.7.1'}), timeout=60))['features']}
GREEN = np.array([52.6, -28.7, 30.4]); BLUE = np.array([65.1, -19., -5.1]); OW, OH = 170, 195
def one(u):
    i = cand[u]['item']; m = re.search(r'1:(\d+)-scale Quadrangle for (.+), ([A-Z]{2}) (\d{4})', i['title']); bb = i['boundingBox']
    a = hue.fetch(i['previewGraphicURL']); f = feat.get(u) or hue.features(a)
    w_ = [(np.linalg.norm(np.array(l, float)-c), x) for l, c, x in ((f['lab_green'], GREEN, f['rich_green']), (f['lab_blue'], BLUE, f['rich_blue'])) if l[0] is not None]
    dist = sum(d*x for d, x in w_)/sum(x for _, x in w_) if w_ and sum(x for _, x in w_) else 30.
    r = dict(id=md5[scan(u)], scan=scan(u), name=m[2], st=m[3], yr=int(m[4]), scale=int(m[1]), tier=1 if dist <= 15 else 2, dist=round(float(dist), 1), cover=round(f['rich'], 2), have=False,
             bbox=[bb['minX'], bb['minY'], bb['maxX'], bb['maxY']], thumb=i['previewGraphicURL'], file=urllib.parse.unquote(u.rsplit('/', 1)[1]).replace('.tif', '.pdf'), tif=u)
    with rasterio.open(u) as d:
        W, H = d.width, d.height; inv = ~d.transform; crs = d.crs.to_wkt()
    t = Transformer.from_crs('EPSG:4267', crs, always_xy=True); w, s, e, n = r['bbox']
    uv = np.array([[x/W, y/H] for x, y in (inv*t.transform(*q) for q in ((w, n), (e, n), (e, s), (w, s)))], np.float32)
    h, wd = a.shape[:2]; src = uv*np.array([wd, h], np.float32); c = src.mean(0); src = c+(src-c)*.985
    M = cv2.getPerspectiveTransform(src, np.array([[0, 0], [OW, 0], [OW, OH], [0, OH]], np.float32))
    Image.fromarray(cv2.warpPerspective(a, M, (OW, OH), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)).save(f"{OUT}{r['scan']}.jpg", quality=88)
    b = a[int(h*.1):int(h*.82), int(wd*.12):int(wd*.86)].reshape(-1, 3); r['color'] = '#%02x%02x%02x' % tuple(int(v) for v in b.mean(0))
    x = urllib.request.urlopen(urllib.request.Request(u, method='HEAD'), timeout=30); r['mb'] = round(int(x.headers['Content-Length'])/1e6, 1)
    return r
with TP(6) as e: new = list(e.map(one, urls))
R += new; R.sort(key=lambda r: r['dist']); json.dump(R, open('site_rows.json', 'w'))
print('added', [(r['name'], r['st'], r['yr']) for r in new], '| sheets', len(R))
