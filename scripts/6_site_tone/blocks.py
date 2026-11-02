# Tone match the site's map images one connected cluster at a time, so each region keeps its own look.
import collections, json, os, sys
import cv2, numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE+'/../4_st_marys')
import tone as t
SITE = os.path.abspath(HERE+'/../../topo_finder/site')
R = json.load(open(HERE+'/../3_finder_and_site/site_rows.json'))
OW, OH = 740, 850

def clusters():
    # Quads sharing an edge form a cluster. The shown sheet in each quad is the site's default: earliest year, then closest match.
    Q = collections.defaultdict(list)
    for r in R: Q[tuple(r['bbox'])].append(r)
    std = lambda b: abs(b[2]-b[0]-.125) < .01 and abs(b[3]-b[1]-.125) < .01
    cell = lambda b: (-round(b[3]/.125), round(b[0]/.125))
    C = {cell(b): b for b in Q if std(b)}
    seen = set(); out = []
    for c in C:
        if c in seen: continue
        st = [c]; seen.add(c); g = []
        while st:
            x = st.pop(); g.append(x)
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x[0]+d[0], x[1]+d[1])
                if n in C and n not in seen: seen.add(n); st.append(n)
        out.append(g)
    out.sort(key=len, reverse=True)
    rep = lambda b: min(Q[b], key=lambda s: (s['yr'], s['dist']))
    return out, C, Q, rep

def load_block(g, C, Q, rep):
    r0 = min(c[0] for c in g); c0 = min(c[1] for c in g)
    rows = max(c[0] for c in g)-r0+1; cols = max(c[1] for c in g)-c0+1
    T = []; grid = {}
    for c in g:
        s = rep(C[c]); f = f"{SITE}/clip8/{s['scan']}.jpg"
        a = np.asarray(Image.open(f).convert('RGB'), np.float32)/255
        x = dict(s=s, f=f, lab=t.rgb2oklab(a).astype(np.float32), rc=(c[0]-r0, c[1]-c0))
        T.append(x); grid[x['rc']] = x
    return T, grid, rows, cols

def match(T, grid, rows, cols, node=12, along=15, water=True, chroma=.965):
    # The St Marys and Canaveral chain with every distance halved, because these images are half the scale that pipeline was tuned on.
    base = [x['lab'] for x in T]; al = (.8, .6, .7, .4)
    M = t.fit_global(T, grid, order=3, lam=.005, sigma=2, depths=(2, 5, 9, 15), step=2)
    L = [t.apply_global(x, m, 3) for x, m in zip(base, M)]
    for sg, a, rounds in ((130, al, 0), (90, al, 0), (60, al, 3), (45, tuple(v*.5 for v in al), 4)):
        L, _, _ = t.dodge(T, base, L, rows, cols, sigma=sg, alpha=a)
        for _ in range(rounds):
            F = t.fit_bilateral(T, grid, L, along=along, node=node)
            L = [t.apply_bilateral(a_, f) for a_, f in zip(L, F)]
    L = t.trim(L, chroma)
    if water: L = t.water_pass(T, grid, L, along=along, node=node)
    return L

def finish(base, L, warm_area=None):
    return [t.gamut_map(t.ink_guard(b, l, 6, warm_area)) for b, l in zip(base, L)]

def to_rgb(l):
    return (np.clip(t.oklab2rgb(l), 0, 1)*255+.5).astype(np.uint8)

def match_edition(e, target, order=3, rounds=6, sigma=60, cap=.08):
    # Another edition of the same quad: fit its tones to the sheet shown on top, then remove slow drift. The cap stops changed land and labels printing through.
    s = cv2.GaussianBlur(e, (0, 0), 2)[::3, ::3].reshape(-1, 3); d = cv2.GaussianBlur(target, (0, 0), 2)[::3, ::3].reshape(-1, 3)
    F = t.phi(s, order); w = np.ones(len(F))
    for _ in range(rounds):
        M = np.linalg.lstsq(F*w[:, None], d*w[:, None], rcond=None)[0]
        w = np.sqrt(1/np.maximum(np.linalg.norm(F@M-d, axis=1), .012))
    o = t.apply_global(e, M, order)
    return o+t.gblur(np.clip(target-o, -cap, cap), sigma)

def save(s, lab):
    # Write the map image and its small copy; the rename means a stopped run never leaves half a file.
    rgb = to_rgb(lab)
    for d, im, q in (('clip8_tm', rgb, 88), ('clip_tm', cv2.resize(rgb, (170, 195), interpolation=cv2.INTER_AREA), 88)):
        p = f"{SITE}/{d}/{s['scan']}.jpg"
        Image.fromarray(im).save(p+'.tmp', 'JPEG', quality=q, optimize=True); os.replace(p+'.tmp', p)

def load_lab(s):
    return t.rgb2oklab(np.asarray(Image.open(f"{SITE}/clip8/{s['scan']}.jpg").convert('RGB'), np.float32)/255).astype(np.float32)

_classify = t.classify
def classify_wide(lab):
    # The St Marys classes, plus dark blue water, which they leave out because they were tuned on pale water.
    k = _classify(lab)
    s = cv2.GaussianBlur(lab, (0, 0), 3)
    k[(s[..., 2] < -.02) & (s[..., 1] < .012) & (s[..., 0] >= .25)] = 3
    return k

def open_water(L, cover=.4):
    # The colour of sheets that really are mostly water, so marsh tints inland can't drag the water target toward teal.
    K = [t.classify(l) for l in L]
    m = [np.median(l[k == 3], axis=0) for l, k in zip(L, K) if (k == 3).mean() >= cover]
    return np.median(np.array(m), axis=0) if len(m) >= 3 else None

def level_sheets(T, L, strength=.85, cover=.03, soft=3, water=None):
    # Shift each sheet's classes toward the cluster's typical values. This acts on whole sheets, so it stays sharp at seams, where evening's wide blur can't reach.
    K = [t.classify(l) for l in L]; meds = {}
    for i in range(len(t.CLASSES)):
        meds[i] = {j: np.median(L[j][K[j] == i], axis=0) for j in range(len(L)) if (K[j] == i).mean() >= cover}
    out = []
    for j, l in enumerate(L):
        o = l.copy()
        for i, m in meds.items():
            if j not in m or len(m) < 3: continue
            tau = np.median(np.array(list(m.values())), axis=0)
            if i == 3 and water is not None: tau = water
            w = cv2.GaussianBlur((K[j] == i).astype(np.float32), (0, 0), soft)
            o += (tau-m[j])[None, None]*strength*w[..., None]
        out.append(o)
    return out

def match_wide(T, grid, rows, cols, node=12, along=15, level=True, wide=((.30, .16), (.30, .16), (.16, .09))):
    # For clusters with big sheet-to-sheet jumps: level whole sheets first, then let early seam rounds accept pairs that disagree a lot.
    base = [x['lab'] for x in T]; al = (.8, .6, .7, .4)
    t.classify = classify_wide
    M = t.fit_global(T, grid, order=3, lam=.005, sigma=2, depths=(2, 5, 9, 15), step=2)
    L = [t.apply_global(x, m, 3) for x, m in zip(base, M)]
    w = open_water(L)
    over = {'water': w} if w is not None else None
    if level: L = level_sheets(T, L, water=w)
    for sg in (130, 90, 60):
        L, _, _ = t.dodge(T, base, L, rows, cols, sigma=sg, alpha=al, over=over)
    for lim in wide:
        F = t.fit_bilateral(T, grid, L, along=along, node=node, limits=lim)
        L = [t.apply_bilateral(a, f) for a, f in zip(L, F)]
    for _ in range(2):
        F = t.fit_bilateral(T, grid, L, along=along, node=node)
        L = [t.apply_bilateral(a, f) for a, f in zip(L, F)]
    L, _, _ = t.dodge(T, base, L, rows, cols, sigma=45, alpha=tuple(v*.5 for v in al), over=over)
    for _ in range(4):
        F = t.fit_bilateral(T, grid, L, along=along, node=node)
        L = [t.apply_bilateral(a, f) for a, f in zip(L, F)]
    L = t.water_pass(T, grid, L, along=along, node=node)
    t.classify = _classify
    mean_c = lambda X: float(np.mean([np.hypot(x[..., 1], x[..., 2]).mean() for x in X]))
    s = float(np.clip(mean_c(base)/mean_c(L), .94, 1.12))                      # return to the cluster's own saturation, rather than a fixed trim
    for x in L: x[..., 1:] *= s
    return L
