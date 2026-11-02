# Score a topo thumbnail by how much of its map body is image-toned blue or green, not white paper with line work.
import io, urllib.parse, urllib.request, time
import numpy as np, cv2
from PIL import Image
def fetch(url):
    for t in range(3):
        try:
            return np.asarray(Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=40).read())).convert('RGB'))
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(1+t)
        except Exception:
            time.sleep(1+t)
    return None
def features(a):
    h, w = a.shape[:2]
    b = a[int(h*.1):int(h*.82), int(w*.12):int(w*.86)]
    Lab = cv2.cvtColor(b.astype(np.float32)/255, cv2.COLOR_RGB2LAB); L, A, B = Lab[..., 0], Lab[..., 1], Lab[..., 2]
    C = np.hypot(A, B); H = np.degrees(np.arctan2(B, A)) % 360
    green = (H >= 100) & (H < 170) & (C >= 22)
    blue = (H >= 170) & (H < 270) & (C >= 10)
    darkgreen = green & (L < 62)
    pale = (L > 90) & (C < 10)
    warm = (H < 100) & (C >= 12)
    tex = cv2.Laplacian(L, cv2.CV_32F)
    # Image-toned land is dark; image-toned water is saturated. Line-map tints are neither.
    cool = (H >= 100) & (H < 270)
    rich = (cool & (L < 72) & (C >= 10)) | ((H >= 170) & (H < 270) & (L < 86) & (C >= 26))
    rg, rb = rich & (H < 170), rich & (H >= 170)
    mean = lambda m: [round(float(x[m].mean()), 1) for x in (L, A, B)] if m.sum() >= 20 else [None]*3
    return dict(w=w, h=h, green=float(green.mean()), blue=float(blue.mean()), darkgreen=float(darkgreen.mean()), pale=float(pale.mean()), warm=float(warm.mean()),
                score=float((green | blue).mean()), L=float(np.median(L)), tex=float(tex.std()), rich=float(rich.mean()),
                rich_green=float(rg.mean()), rich_blue=float(rb.mean()), warm_img=float((warm & (L < 72)).mean()), lab_green=mean(rg), lab_blue=mean(rb))
