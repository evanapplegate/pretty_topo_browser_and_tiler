# Warp each thumbnail's quad corners to a north-up rectangle so the map body fills its bbox with no collar.
import json
from concurrent.futures import ThreadPoolExecutor as TP
import numpy as np, cv2, hue
from PIL import Image
OUT = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/topo_finder/site/clip/'
R = json.load(open('site_rows.json')); G = json.load(open('georef.json'))
OW, OH = 170, 195
def one(r):
    a = hue.fetch(r['thumb'])
    if a is None: return r['id'], 'no thumb'
    h, w = a.shape[:2]
    uv = np.array(G[r['id']]['uv'], np.float32)
    src = uv*np.array([w, h], np.float32)
    # Pull each corner in slightly so the neatline and white collar cannot bleed into the seam.
    c = src.mean(0); src = c+(src-c)*.985
    dst = np.array([[0, 0], [OW, 0], [OW, OH], [0, OH]], np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    b = cv2.warpPerspective(a, M, (OW, OH), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    Image.fromarray(b).save(f"{OUT}{r['scan']}.jpg", quality=88)
    return r['id'], None
with TP(12) as e: res = list(e.map(one, R))
print('clipped', sum(v is None for _, v in res), 'of', len(res), [v for _, v in res if v][:3])
