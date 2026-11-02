# Add sheets topoView flags ORTHOPHOTO=Map to the site, skip orange ones, and report blanks that stay empty.
import csv, glob, json, os, pickle, re, urllib.parse
from concurrent.futures import ThreadPoolExecutor as TP
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', GDAL_HTTP_MAX_RETRY='3', GDAL_HTTP_RETRY_DELAY='1')
import cv2, numpy as np, rasterio, urllib.request, hue
from pyproj import Transformer
from PIL import Image, ImageDraw
T = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/'; OUT = T+'topo_finder/site/clip/'
cand, feat = pickle.load(open('scan.pkl', 'rb')); H = pickle.load(open('holes.pkl', 'rb'))
md5 = {int(k): v for k, v in json.load(open('md5s.json')).items()}; flag = set(open('flags.txt').read().split())
R = json.load(open('site_rows.json')); have_tif = {r['tif'] for r in R}
mine = {os.path.basename(f).replace('_geo.tif', '') for g in ('FL_*_tif/*.tif', 'louisiana_topos/LA_*_tif/*.tif', 'nw_fl_topos/FL_*_tif/*.tif') for f in glob.glob(T+g)}
scan = lambda u: int(re.search(r'_(\d+)_\d{4}_\d+_geo\.tif', u).group(1))
GREEN = np.array([52.6, -28.7, 30.4]); BLUE = np.array([65.1, -19., -5.1])
def strong(u):
    # Enclosed blanks also take unflagged sheets with clear image tone, because USGS's flag has gaps.
    f = feat.get(u)
    if not f or f['rich'] < .5: return False
    lg, lb = f['lab_green'], f['lab_blue']
    cg = float(np.hypot(*lg[1:])) if lg[0] is not None else 0; cb = float(np.hypot(*lb[1:])) if lb[0] is not None else 0
    yr = int(re.search(r'(\d{4})$', cand[u]['item']['title']).group(1))
    return yr >= 1960 and (cb >= 8 if f['rich_blue'] >= .02 else cg >= 26)
K0 = {(round(r['bbox'][0]/.125), round(r['bbox'][1]/.125)) for r in R}
pool = sorted({u for h in H['holes'] if h['cell'] not in K0 for u in h['cands'] if u not in have_tif and (md5.get(scan(u), '')[:10] in flag or strong(u))})
new = []; skipped = 0
for u in pool:
    f = feat.get(u)
    if not f: skipped += 1; continue
    i = cand[u]['item']; m = re.search(r'1:(\d+)-scale Quadrangle for (.+), ([A-Z]{2}) (\d{4})', i['title']); bb = i['boundingBox']
    lg, lb = f['lab_green'], f['lab_blue']; wg, wb = f['rich_green'], f['rich_blue']
    w = [(np.linalg.norm(np.array(l, float)-c), x) for l, c, x in ((lg, GREEN, wg), (lb, BLUE, wb)) if l[0] is not None]
    dist = sum(d*x for d, x in w)/sum(x for _, x in w) if w and sum(x for _, x in w) else 30.
    base = urllib.parse.unquote(u.rsplit('/', 1)[1]).replace('_geo.tif', '')
    new.append(dict(id=md5[scan(u)], scan=scan(u), name=m[2], st=m[3], yr=int(m[4]), scale=int(m[1]), tier=1 if dist <= 15 else 2, dist=round(float(dist), 1), cover=round(f['rich'], 2),
                    have=base in mine, bbox=[bb['minX'], bb['minY'], bb['maxX'], bb['maxY']], thumb=i['previewGraphicURL'], color='#5a8f7b', file=base+'_geo.pdf', tif=u, mb=0))
print('adding', len(new), 'orange skipped', skipped, '| of your 57 restored', sum(r['have'] for r in new), [r['name'] for r in new if r['have']], flush=True)
OW, OH = 170, 195
def one(r):
    with rasterio.open(r['tif']) as d:
        W, H_ = d.width, d.height; inv = ~d.transform; crs = d.crs.to_wkt()
    t = Transformer.from_crs('EPSG:4267', crs, always_xy=True); w, s, e, n = r['bbox']
    uv = np.array([[x/W, y/H_] for x, y in (inv*t.transform(*p) for p in ((w, n), (e, n), (e, s), (w, s)))], np.float32)
    a = hue.fetch(r['thumb']); h, wd = a.shape[:2]
    src = uv*np.array([wd, h], np.float32); c = src.mean(0); src = c+(src-c)*.985
    M = cv2.getPerspectiveTransform(src, np.array([[0, 0], [OW, 0], [OW, OH], [0, OH]], np.float32))
    Image.fromarray(cv2.warpPerspective(a, M, (OW, OH), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)).save(f"{OUT}{r['scan']}.jpg", quality=88)
    b = a[int(h*.1):int(h*.82), int(wd*.12):int(wd*.86)].reshape(-1, 3); r['color'] = '#%02x%02x%02x' % tuple(int(v) for v in b.mean(0))
    x = urllib.request.urlopen(urllib.request.Request(r['tif'], method='HEAD'), timeout=30); r['mb'] = round(int(x.headers['Content-Length'])/1e6, 1)
    return r
with TP(12) as e: new = list(e.map(one, new))
R += new; R.sort(key=lambda r: r['dist'])
json.dump(R, open('site_rows.json', 'w'))
open(T+'topo_finder/site/sheets.js', 'w').write('const SHEETS='+json.dumps(R, separators=(',', ':'))+';\n')
K = {(round(r['bbox'][0]/.125), round(r['bbox'][1]/.125)) for r in R}
left = [h for h in H['holes'] if h['cell'] not in K]
print('total sheets', len(R), '| enclosed blanks filled', len(H['holes'])-len(left), 'still blank', len(left))
for h in left: print(f"   {h['s']:7.3f} {h['w']:9.3f} editions {len(h['cands'])}")
rows = [dict(tier=r['tier'], state=r['st'], name=r['name'], year=r['yr'], scale=r['scale'], match_dist=r['dist'], image_cover=r['cover'], already_have=r['have'], west=r['bbox'][0], south=r['bbox'][1], east=r['bbox'][2], north=r['bbox'][3], topoview_id=r['id'], geotiff_url=r['tif'], thumb_url=r['thumb']) for r in R]
with open(T+'topo_finder/blue_green_image_topos.csv', 'w', newline='') as o:
    w = csv.DictWriter(o, list(rows[0])); w.writeheader(); w.writerows(rows)
open(T+'topo_finder/tier1_geotiff_urls.txt', 'w').write('\n'.join(r['tif'] for r in R if r['tier'] == 1 and not r['have'])+'\n')
order = sorted(R, key=lambda r: (r['st'], r['dist']))
with TP(12) as e: A = list(e.map(lambda r: hue.fetch(r['thumb']), order))
cols = 24; W, Hh = 84, 112
C = Image.new('RGB', (cols*W, (len(order)//cols+1)*Hh), 'white'); d = ImageDraw.Draw(C)
for i, (r, a) in enumerate(zip(order, A)):
    x, y = (i % cols)*W, (i//cols)*Hh
    if a is not None: C.paste(Image.fromarray(a).resize((W-3, Hh-14), Image.LANCZOS), (x, y))
    d.text((x+1, y+Hh-13), f"{r['st']} {r['yr']} {r['dist']:.0f}", fill='black')
C.save(T+'topo_finder/blue_green_image_topos_contact.png')
# Trial view of just the additions so false positives are easy to see.
cols = 16; W, Hh = 120, 158
order = sorted(new, key=lambda r: (r['st'], r['name']))
with TP(12) as e: A = list(e.map(lambda r: hue.fetch(r['thumb']), order))
C = Image.new('RGB', (cols*W, (len(order)//cols+1)*Hh), 'white'); d = ImageDraw.Draw(C)
for i, (r, a) in enumerate(zip(order, A)):
    x, y = (i % cols)*W, (i//cols)*Hh
    if a is not None: C.paste(Image.fromarray(a).resize((W-4, Hh-18), Image.LANCZOS), (x, y))
    d.text((x+2, y+Hh-17), f"{r['st']} {r['yr']} {r['name'][:14]}", fill='black')
C.save('qa/added.png'); print('done')
