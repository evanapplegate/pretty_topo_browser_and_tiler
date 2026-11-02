# Seam-driven colour harmonisation in OKLab: a jointly solved global tone map per sheet, then seam levelling with a smooth field.
import glob, json, os, re, sys, time
import numpy as np, cv2, rasterio
from rasterio.enums import Resampling
from scipy import sparse
from scipy.interpolate import RectBivariateSpline
from scipy.ndimage import median_filter
from scipy.sparse.linalg import splu

HERE = os.path.dirname(os.path.abspath(__file__))
LOSSLESS = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos/lossless'
SHEETS = {s['scan']: s for s in json.load(open(HERE+'/sheets.json'))}
FAC = 4

def srgb2lin(c):
    return np.where(c <= .04045, c/12.92, ((c+.055)/1.055)**2.4)
def lin2srgb(c):
    c = np.clip(c, 0, None)
    return np.where(c <= .0031308, 12.92*c, 1.055*c**(1/2.4)-.055)
M1 = np.array([[.4122214708, .5363325363, .0514459929], [.2119034982, .6806995451, .1073969566], [.0883024619, .2817188376, .6299787005]], np.float32)
M2 = np.array([[.2104542553, .7936177850, -.0040720468], [1.9779984951, -2.4285922050, .4505937099], [.0259040371, .7827717662, -.8086757660]], np.float32)
M1i = np.linalg.inv(M1); M2i = np.linalg.inv(M2)
def rgb2oklab(rgb):
    return np.cbrt(srgb2lin(rgb)@M1.T)@M2.T
def oklab2rgb(lab):
    return lin2srgb((lab@M2i.T)**3@M1i.T)

def load(fac=FAC):
    T = []
    for f in sorted(glob.glob(LOSSLESS+'/*.tif')):
        scan = int(re.search(r'_(\d+)_\d{4}_', os.path.basename(f)).group(1)); s = SHEETS[scan]
        with rasterio.open(f) as d:
            a = np.moveaxis(d.read(out_shape=(3, d.height//fac, d.width//fac), resampling=Resampling.average), 0, -1).astype(np.float32)/255
        T.append(dict(s=s, f=f, lab=rgb2oklab(a).astype(np.float32)))
    ws = sorted({t['s']['bbox'][0] for t in T}); ns = sorted({t['s']['bbox'][3] for t in T}, reverse=True)
    grid = {}
    for t in T:
        t['rc'] = (ns.index(t['s']['bbox'][3]), ws.index(t['s']['bbox'][0])); grid[t['rc']] = t
    return T, grid, len(ns), len(ws)

def edges(grid):
    # Each seam as (first sheet, second sheet, direction); h means the second sheet lies east.
    E = []
    for (r, c), t in grid.items():
        if (r, c+1) in grid: E.append((t, grid[(r, c+1)], 'h'))
        if (r+1, c) in grid: E.append((t, grid[(r+1, c)], 'v'))
    return E

def strip(lab, side, d):
    return {'E': lab[:, -1-d], 'W': lab[:, d], 'S': lab[-1-d, :], 'N': lab[d, :]}[side]

def phi(c, order):
    L, a, b = c[..., 0], c[..., 1], c[..., 2]
    t = [np.ones_like(L), L, a, b]
    if order >= 2: t += [L*L, a*a, b*b, L*a, L*b, a*b]
    if order >= 3: t += [L**3, L*L*a, L*L*b]
    return np.stack(t, -1).astype(np.float64)

def seam_pairs(grid, sigma, depths, step):
    # Mirrored pixel pairs either side of each seam: they show nearly the same ground.
    P = []
    blur = {id(t): cv2.GaussianBlur(t['lab'], (0, 0), sigma) for t in grid.values()}
    for a, b, k in edges(grid):
        sa, sb = ('E', 'W') if k == 'h' else ('S', 'N')
        A = []; B = []
        for d in depths:
            A.append(strip(blur[id(a)], sa, d)[::step]); B.append(strip(blur[id(b)], sb, d)[::step])
        P.append((a, b, np.concatenate(A), np.concatenate(B)))
    return P

def fit_global(T, grid, order=2, lam=.02, sigma=4, depths=(4, 10, 18, 30), step=3, rounds=8, pin=.2, anchor=None):
    idx = {id(t): i for i, t in enumerate(T)}
    n = len(T); K = phi(np.zeros((1, 3)), order).shape[1]
    I = np.zeros((K, 3)); I[1, 0] = 1; I[2, 1] = 1; I[3, 2] = 1
    M = np.tile(I, (n, 1, 1))
    P = seam_pairs(grid, sigma, depths, step)
    pin_c = np.array([[0, 0, 0], [1, 0, 0], [.05, 0, 0], [.97, 0, 0]], float)
    F = [(idx[id(a)], idx[id(b)], phi(A, order), phi(B, order)) for a, b, A, B in P]
    for _ in range(rounds):
        H = np.zeros((n*K, n*K)); g = np.zeros((n*K, 3))
        for i, j, Fa, Fb in F:
            r = (Fa@M[i])-(Fb@M[j])
            w = 1/np.maximum(np.linalg.norm(r, axis=1), .012)              # Huber-style weights shrug off labels and line work
            w = w/w.mean()/len(w)
            Faw = Fa*w[:, None]; Fbw = Fb*w[:, None]
            ii = slice(i*K, (i+1)*K); jj = slice(j*K, (j+1)*K)
            H[ii, ii] += Fa.T@Faw; H[jj, jj] += Fb.T@Fbw
            cross = Fa.T@Fbw
            H[ii, jj] -= cross; H[jj, ii] -= cross.T
        H /= len(F)
        fp = phi(pin_c, order)
        for i in range(n):
            ii = slice(i*K, (i+1)*K)
            wt = lam*(anchor.get(T[i]['s']['name'], 1) if anchor else 1)
            H[ii, ii] += wt*np.eye(K)+pin*fp.T@fp/len(pin_c)
            g[ii] += wt*I+pin*fp.T@(fp@I)/len(pin_c)
        M = np.linalg.solve(H, g).reshape(n, K, 3)
    return M

def apply_global(lab, m, order):
    return (phi(lab, order)@m).astype(np.float32)

def seam_delta(a, b, sa, sb, depths=(3, 8, 14), along=12):
    # Robust colour offset along a seam, measured from what sits either side of it.
    A = np.mean([strip(a, sa, d) for d in depths], 0); B = np.mean([strip(b, sb, d) for d in depths], 0)
    d = (A-B).astype(np.float32)
    k = along*2+1
    d = median_filter(d, size=(k, 1), mode='nearest').astype(np.float32)
    return cv2.GaussianBlur(d, (1, 0), along, borderType=cv2.BORDER_REPLICATE)

def fit_field(T, grid, labs, node=20, along=40, seam_w=60., eps=.002):
    # One membrane per sheet, coupled across seams so each jump is cancelled, shared half and half.
    H, W = labs[0].shape[:2]
    ny, nx = H//node+2, W//node+2
    n = len(T); N = nx*ny*n
    id_ = lambda s, y, x: s*nx*ny+y*nx+x
    r = []; c = []; v = []
    def add(i, j, w):
        r.extend([i, j, i, j]); c.extend([i, j, j, i]); v.extend([w, w, -w, -w])
    for s in range(n):
        for y in range(ny):
            for x in range(nx):
                if x+1 < nx: add(id_(s, y, x), id_(s, y, x+1), 1.)
                if y+1 < ny: add(id_(s, y, x), id_(s, y+1, x), 1.)
    rhs = np.zeros((N, 3)); pos = {id(t): i for i, t in enumerate(T)}
    for a, b, k in edges(grid):
        ia, ib = pos[id(a)], pos[id(b)]
        sa, sb = ('E', 'W') if k == 'h' else ('S', 'N')
        d = seam_delta(labs[ia], labs[ib], sa, sb, along=along)
        m = ny if k == 'h' else nx
        at = np.linspace(0, len(d)-1, m).round().astype(int)
        for q, dd in zip(range(m), d[at]):
            p1 = id_(ia, q, nx-1) if k == 'h' else id_(ia, ny-1, q)
            p2 = id_(ib, q, 0) if k == 'h' else id_(ib, 0, q)
            add(p1, p2, seam_w)
            rhs[p1] -= seam_w*dd; rhs[p2] += seam_w*dd
    A = sparse.coo_matrix((v, (r, c)), shape=(N, N)).tocsc()+eps*sparse.identity(N, format='csc')
    lu = splu(A)
    X = np.stack([lu.solve(rhs[:, i]) for i in range(3)], -1)
    return X.reshape(n, ny, nx, 3), (ny, nx)

def field_up(fld, shape):
    h, w = shape; ny, nx = fld.shape[:2]
    gy = np.linspace(0, 1, ny); gx = np.linspace(0, 1, nx)
    yi = (np.arange(h)+.5)/h; xi = (np.arange(w)+.5)/w
    return np.stack([RectBivariateSpline(gy, gx, fld[..., c], kx=3, ky=3)(yi, xi) for c in range(3)], -1).astype(np.float32)

def de(a, b):
    return np.linalg.norm(a-b, axis=-1)*100

last_seams = []
def seam_crops(T, grid, labs, rows, cols, path, size=340, n=8):
    # Paired crops centred on the worst stretches of the worst seams, at quarter resolution scaled up.
    from PIL import Image, ImageDraw
    h, w = labs[0].shape[:2]; C = canvas(T, labs, rows, cols); pos = {id(t): i for i, t in enumerate(T)}
    spots = []
    for a, b, k in edges(grid):
        ia, ib = pos[id(a)], pos[id(b)]; sa, sb = ('E', 'W') if k == 'h' else ('S', 'N')
        A = np.mean([strip(labs[ia], sa, d) for d in (2, 5, 8)], 0); B = np.mean([strip(labs[ib], sb, d) for d in (2, 5, 8)], 0)
        q = cv2.GaussianBlur(de(A, B).astype(np.float32).reshape(-1, 1), (1, 0), 30).ravel(); i = int(q.argmax())
        r, c = a['rc']; x = (c+1)*w if k == 'h' else c*w+i; y = r*h+i if k == 'h' else (r+1)*h
        spots.append((float(q[i]), x, y, f"{a['s']['name'][:10]}|{b['s']['name'][:10]} {q[i]:.1f}"))
    spots.sort(reverse=True); out = Image.new('RGB', (4*size+12, 2*size+4), 'white'); dr = ImageDraw.Draw(out)
    for i, (q, x, y, tag) in enumerate(spots[:n]):
        x0 = min(max(x-size//4, 0), C.shape[1]-size//2); y0 = min(max(y-size//4, 0), C.shape[0]-size//2)
        c = (np.clip(oklab2rgb(C[y0:y0+size//2, x0:x0+size//2]), 0, 1)*255).astype(np.uint8)
        px, py = (i % 4)*(size+4), (i//4)*(size+4)
        out.paste(Image.fromarray(c).resize((size, size), Image.BICUBIC), (px, py)); dr.text((px+4, py+4), tag, fill='red')
    out.save(path)

def metrics(T, grid, labs, base):
    pos = {id(t): i for i, t in enumerate(T)}
    J = []
    for a, b, k in edges(grid):
        ia, ib = pos[id(a)], pos[id(b)]
        sa, sb = ('E', 'W') if k == 'h' else ('S', 'N')
        A = np.mean([strip(cv2.GaussianBlur(labs[ia], (0, 0), 3), sa, d) for d in (2, 5, 8)], 0)
        B = np.mean([strip(cv2.GaussianBlur(labs[ib], (0, 0), 3), sb, d) for d in (2, 5, 8)], 0)
        q = cv2.GaussianBlur(de(A, B).astype(np.float32).reshape(-1, 1), (1, 0), 10).ravel()
        J.append((np.median(q), np.percentile(q, 90), f"{a['s']['name'][:9]}|{b['s']['name'][:9]}"))
    def cls(lab):
        L, A, B = lab[..., 0], lab[..., 1], lab[..., 2]; C = np.hypot(A, B)
        return (L > .3) & (A < -.02) & (B > .02), (B < -.004) & (L > .55), C
    sp = {'land': [], 'water': []}; chroma = []; hp = []
    for lab, b0 in zip(labs, base):
        s = cv2.GaussianBlur(lab, (0, 0), 3); land, water, C = cls(cv2.GaussianBlur(b0, (0, 0), 3))
        if land.mean() > .03: sp['land'].append(s[land].mean(0))
        if water.mean() > .03: sp['water'].append(s[water].mean(0))
        chroma.append(np.hypot(lab[..., 1], lab[..., 2]).mean()/np.hypot(b0[..., 1], b0[..., 2]).mean())
        h = lab[..., 0]-cv2.GaussianBlur(lab[..., 0], (0, 0), 6); h0 = b0[..., 0]-cv2.GaussianBlur(b0[..., 0], (0, 0), 6)
        hp.append(h.std()/h0.std())
    spread = {k: float(np.mean(np.linalg.norm(np.array(v)-np.mean(v, 0), axis=1))*100) for k, v in sp.items()}
    rgb = [oklab2rgb(l) for l in labs]
    clipped = float(np.mean([((r < 0) | (r > 1)).any(-1).mean() for r in rgb])*100)
    global last_seams; last_seams = sorted(J, key=lambda j: -j[1])
    return dict(seam_med=float(np.mean([j[0] for j in J])), seam_p90=float(np.mean([j[1] for j in J])), seam_worst=float(max(j[1] for j in J)), worst=max(J, key=lambda j: j[1])[2],
                land_spread=spread['land'], water_spread=spread['water'], chroma=float(np.mean(chroma)), detail=float(np.mean(hp)), detail_min=float(min(hp)), clipped_pct=clipped)

def mosaic(T, labs, rows, cols, fac=2):
    h, w = labs[0].shape[:2]
    C = np.zeros((rows*h//fac, cols*w//fac, 3), np.uint8)
    for t, l in zip(T, labs):
        r, c = t['rc']
        s = cv2.resize(l, (w//fac, h//fac), interpolation=cv2.INTER_AREA)
        C[r*(h//fac):(r+1)*(h//fac), c*(w//fac):(c+1)*(w//fac)] = (np.clip(oklab2rgb(s), 0, 1)*255+.5).astype(np.uint8)
    return C

CLASSES = ('forest', 'clearing', 'marsh', 'water')
def classify(lab):
    # Soft-free class map from a lightly blurred colour image: 0 forest, 1 clearing, 2 marsh, 3 water, -1 other (sand, roads, labels).
    s = cv2.GaussianBlur(lab, (0, 0), 3)
    L, A, B = s[..., 0], s[..., 1], s[..., 2]
    k = np.full(L.shape, -1, np.int8)
    green = A < -.012
    k[green & (B >= .045) & (L < .62)] = 0
    k[green & (B >= .045) & (L >= .62)] = 1
    k[green & (B < .045) & (B >= -.002) & (L < .74)] = 2
    k[(L >= .72) & (B < .03) & (A < .012)] = 3
    return k

def canvas(T, labs, rows, cols):
    h, w = labs[0].shape[:2]
    C = np.zeros((rows*h, cols*w, labs[0].shape[-1] if labs[0].ndim == 3 else 1), labs[0].dtype)
    for t, l in zip(T, labs):
        r, c = t['rc']
        C[r*h:(r+1)*h, c*w:(c+1)*w] = l if l.ndim == 3 else l[..., None]
    return C

def cut(T, C, rows, cols, h, w):
    return [C[t['rc'][0]*h:(t['rc'][0]+1)*h, t['rc'][1]*w:(t['rc'][1]+1)*w] for t in T]

def gblur(a, s):
    # Large Gaussian on a reduced grid; the result is smooth, so nothing is lost and it stays fast.
    f = max(1, int(s/4))
    sm = cv2.resize(a, (a.shape[1]//f, a.shape[0]//f), interpolation=cv2.INTER_AREA) if f > 1 else a
    b = cv2.GaussianBlur(sm, (0, 0), s/f, borderType=cv2.BORDER_REFLECT)
    return cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_CUBIC) if f > 1 else b

def dodge(T, base, labs, rows, cols, sigma=180, alpha=(.8, .6, .7, .4), target=None):
    # Local tone mapping per class: even out each class's slow drift across the mosaic, leaving real detail alone.
    h, w = labs[0].shape[:2]
    K = canvas(T, [classify(b) for b in labs], rows, cols)[..., 0]             # classify the current estimate, because raw colours differ by sheet
    R = canvas(T, base, rows, cols); Rs = cv2.GaussianBlur(R, (0, 0), 3)
    K[(Rs[..., 0] >= .78) & (Rs[..., 2] < .03) & (Rs[..., 1] < .012)] = 3      # pale flats stay water: a drifting estimate must not recruit them into land
    C = canvas(T, labs, rows, cols).astype(np.float32)
    corr = np.zeros_like(C); conf = np.zeros(C.shape[:2], np.float32); total = np.zeros_like(C); targets = {}
    for i, name in enumerate(CLASSES):
        m = (K == i).astype(np.float32)
        den = gblur(m, sigma)
        num = np.stack([gblur(C[..., c]*m, sigma) for c in range(3)], -1)
        mu = num/np.maximum(den, 1e-4)[..., None]
        tau = target[name] if target else np.array([np.median(C[..., c][K == i]) for c in range(3)], np.float32)
        targets[name] = tau
        ok = np.clip(den/.02, 0, 1)[..., None]                          # fade out where a class is barely present
        d = (tau-mu)*alpha[i]*ok
        corr += d*m[..., None]
        total += d*den[..., None]; conf += den
    other = (K < 0)
    fill = total/np.maximum(conf, 1e-4)[..., None]
    corr[other] = (fill*(1-smooth(C[..., 0], .78, .86))[..., None])[other]
    corr = np.stack([cv2.GaussianBlur(corr[..., c], (0, 0), 2) for c in range(3)], -1)
    return cut(T, C+corr, rows, cols, h, w), cut(T, corr, rows, cols, h, w), targets

def baseline(T, labs):
    # What the seam metric reads on real, unbroken map: fake seams through the sheet centres.
    q = []
    for l in labs:
        s = cv2.GaussianBlur(l, (0, 0), 3); w = s.shape[1]//2; h = s.shape[0]//2
        for A, B in ((np.mean([s[:, w-1-d] for d in (2, 5, 8)], 0), np.mean([s[:, w+d] for d in (2, 5, 8)], 0)), (np.mean([s[h-1-d] for d in (2, 5, 8)], 0), np.mean([s[h+d] for d in (2, 5, 8)], 0))):
            p = cv2.GaussianBlur(de(A, B).astype(np.float32).reshape(-1, 1), (1, 0), 10).ravel()
            q.append((np.median(p), np.percentile(p, 90)))
    return float(np.mean([a for a, _ in q])), float(np.mean([b for _, b in q]))

def gamut_map(lab):
    # Pull out-of-gamut colours in along chroma, holding lightness and hue, instead of clipping channels.
    rgb = oklab2rgb(lab)
    bad = ((rgb < -1e-4) | (rgb > 1+1e-4)).any(-1)
    if not bad.any(): return lab
    p = lab[bad].copy(); lo = np.zeros(len(p)); hi = np.ones(len(p))
    for _ in range(12):
        m = (lo+hi)/2; q = p.copy(); q[:, 1:] *= m[:, None]
        r = oklab2rgb(q); out = ((r < 0) | (r > 1)).any(-1)
        hi = np.where(out, m, hi); lo = np.where(out, lo, m)
    p[:, 1:] *= lo[:, None]
    res = lab.copy(); res[bad] = p
    return res

def pipeline(T, grid, base, rows, cols, order=3, lam=.005, sigma=(260, 180, 120), alpha=(.8, .6, .7, .4), passes=3, along=40, seam_w=60., node=20):
    M = fit_global(T, grid, order=order, lam=lam)
    L = [apply_global(x, m, order) for x, m in zip(base, M)]
    corr = [np.zeros_like(x) for x in base]
    sigmas = sigma if isinstance(sigma, (tuple, list)) else [sigma]*passes
    for sg in sigmas:
        L, c, tau = dodge(T, base, L, rows, cols, sigma=sg, alpha=alpha)
        corr = [a+b for a, b in zip(corr, c)]
    F, _ = fit_field(T, grid, L, node=node, along=along, seam_w=seam_w)
    out = [a+field_up(f, a.shape[:2]) for a, f in zip(L, F)]
    return out, dict(M=M, corr=corr, F=F, tau=tau)

TONES = np.array([.22, .38, .52, .66, .80, .92, 1.0], np.float32)
def tone_basis(L, tones=TONES):
    # Piecewise-linear weights across the tone nodes.
    L = np.clip(L, tones[0], tones[-1]-1e-4)
    i = np.searchsorted(tones, L, side='right')-1
    return i, (L-tones[i])/(tones[i+1]-tones[i])

def seam_tone_delta(a, b, sa, sb, nodes, along, tones=TONES, depths=(2, 4, 7, 11, 16), blur=1.5, select=None, limits=None):
    # Across-seam offset per position and per tone, using only pairs that look like the same material.
    ba = cv2.GaussianBlur(a, (0, 0), blur); bb = cv2.GaussianBlur(b, (0, 0), blur)
    A = np.stack([strip(ba, sa, d) for d in depths], 1); B = np.stack([strip(bb, sb, d) for d in depths], 1)
    d = A-B; L = (A[..., 0]+B[..., 0])/2
    hi = smooth(L, .70, .85)                                                   # near white, everything looks alike, so demand a closer match
    ok = (np.abs(d[..., 0]) < .09-.055*hi) & (np.hypot(d[..., 1], d[..., 2]) < .05-.03*hi)
    if limits: ok = (np.abs(d[..., 0]) < limits[0]) & (np.hypot(d[..., 1], d[..., 2]) < limits[1])
    if select: ok &= select(A) & select(B)
    pos = np.repeat(np.arange(A.shape[0])[:, None], len(depths), 1)
    i, f = tone_basis(L)
    D = np.zeros((len(nodes), len(tones), 3), np.float32); C = np.zeros((len(nodes), len(tones)), np.float32)
    for q, p in enumerate(nodes):
        g = np.exp(-.5*((pos-p)/along)**2)*ok
        for k in range(len(tones)):
            w = g*((i == k)*(1-f)+(i+1 == k)*f)
            s = w.sum()
            if s < 1e-3: continue
            m = (w[..., None]*d).sum((0, 1))/s
            for _ in range(2):
                r = np.linalg.norm(d-m, axis=-1); u = w/np.maximum(r, .012)
                m = (u[..., None]*d).sum((0, 1))/u.sum()
            D[q, k] = m; C[q, k] = s
    return D, C

def fit_bilateral(T, grid, labs, node=30, along=45, seam_w=30., tone_w=.6, eps=.003, hi_eps=.06, c0=25., tones=TONES, select=None, limits=None):
    # One colour field per sheet over (y, x, tone), coupled across seams, so bright water and dark forest each get their own correction.
    H, W = labs[0].shape[:2]; ny, nx, nt = H//node+2, W//node+2, len(tones)
    n = len(T); per = ny*nx*nt; N = n*per
    idx = lambda s, y, x, k: s*per+(y*nx+x)*nt+k
    Y, X, K = np.meshgrid(np.arange(ny), np.arange(nx), np.arange(nt), indexing='ij')
    pairs = []
    for s in range(n):
        base = idx(s, Y, X, K)
        pairs.append((base[:, :-1].ravel(), base[:, 1:].ravel(), np.ones(base[:, :-1].size)))
        pairs.append((base[:-1].ravel(), base[1:].ravel(), np.ones(base[:-1].size)))
        pairs.append((base[..., :-1].ravel(), base[..., 1:].ravel(), np.full(base[..., :-1].size, tone_w)))
    rhs = np.zeros((N, 3)); pos = {id(t): i for i, t in enumerate(T)}
    for a, b, k in edges(grid):
        ia, ib = pos[id(a)], pos[id(b)]
        sa, sb = ('E', 'W') if k == 'h' else ('S', 'N')
        m = ny if k == 'h' else nx; L = H if k == 'h' else W
        nodes = np.linspace(0, L-1, m)
        D, C = seam_tone_delta(labs[ia], labs[ib], sa, sb, nodes, along, select=select, limits=limits)
        w = seam_w*np.clip(C/c0, 0, 1)
        q, t = np.meshgrid(np.arange(m), np.arange(nt), indexing='ij')
        p1 = idx(ia, q, nx-1, t) if k == 'h' else idx(ia, ny-1, q, t)
        p2 = idx(ib, q, 0, t) if k == 'h' else idx(ib, 0, q, t)
        keep = w.ravel() > 0
        pairs.append((p1.ravel()[keep], p2.ravel()[keep], w.ravel()[keep]))
        np.add.at(rhs, p1.ravel(), -(w[..., None]*D).reshape(-1, 3)); np.add.at(rhs, p2.ravel(), (w[..., None]*D).reshape(-1, 3))
    i = np.concatenate([p[0] for p in pairs]); j = np.concatenate([p[1] for p in pairs]); w = np.concatenate([p[2] for p in pairs])
    leash = np.full(N, eps); leash[(np.arange(N) % nt) >= nt-3] = hi_eps       # highlights stay near zero unless a seam really asks otherwise
    A = sparse.coo_matrix((np.r_[w, w, -w, -w], (np.r_[i, j, i, j], np.r_[i, j, j, i])), shape=(N, N)).tocsc()+sparse.diags(leash, format='csc')
    lu = splu(A, permc_spec='COLAMD')
    return np.stack([lu.solve(rhs[:, c]) for c in range(3)], -1).reshape(n, ny, nx, nt, 3).astype(np.float32)

def apply_bilateral(lab, fld, tones=TONES, weight=None):
    h, w = lab.shape[:2]; nt = fld.shape[2]
    ys = np.linspace(0, fld.shape[0]-1, h, dtype=np.float32); xs = np.linspace(0, fld.shape[1]-1, w, dtype=np.float32)
    mx, my = np.meshgrid(xs, ys)
    i, f = tone_basis(lab[..., 0]); out = lab.copy()
    for k in range(nt-1):
        m = (i == k)
        if not m.any(): continue
        lo = cv2.remap(fld[:, :, k], mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        hi = cv2.remap(fld[:, :, k+1], mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        d = lo[m]*(1-f[m])[:, None]+hi[m]*f[m][:, None]
        out[m] += d if weight is None else d*weight[m][:, None]
    return out

def visibility(T, grid, labs, off=24):
    # How much stronger the colour step is on the real seam than on parallel control lines inside each sheet: 1.0 means no seam at all.
    pos = {id(t): i for i, t in enumerate(T)}; R = []; S = []; C = []
    for a, b, k in edges(grid):
        ia, ib = pos[id(a)], pos[id(b)]; sa, sb = ('E', 'W') if k == 'h' else ('S', 'N')
        sA = cv2.GaussianBlur(labs[ia], (0, 0), 2); sB = cv2.GaussianBlur(labs[ib], (0, 0), 2)
        ds = (2, 4, 6)
        seam = de(np.mean([strip(sA, sa, d) for d in ds], 0), np.mean([strip(sB, sb, d) for d in ds], 0))
        ctl = []
        for src, sd in ((sA, sa), (sB, sb)):
            ctl.append(de(np.mean([strip(src, sd, off-1-d) for d in ds], 0), np.mean([strip(src, sd, off+d) for d in ds], 0)))
        ctl = np.mean(ctl, 0)
        w = 40; ker = np.ones(w)/w
        x = np.convolve(seam, ker, 'valid'); y = np.convolve(ctl, ker, 'valid')
        S.append(np.median(x)); C.append(np.median(y)); R.append(np.median(x)/max(np.median(y), 1e-3))
    return dict(ratio=float(np.mean(R)), ratio_worst=float(max(R)), seam=float(np.mean(S)), control=float(np.mean(C)))

def stack(T, grid, base, rows, cols, order=3, lam=.005, sigmas=(260, 180, 120), alpha=(.8, .6, .7, .4), rounds=3, **kw):
    M = fit_global(T, grid, order=order, lam=lam)
    L = [apply_global(x, m, order) for x, m in zip(base, M)]
    for sg in sigmas:
        L, _, _ = dodge(T, base, L, rows, cols, sigma=sg, alpha=alpha)
    for _ in range(rounds):
        F = fit_bilateral(T, grid, L, **kw)
        L = [apply_bilateral(a, f) for a, f in zip(L, F)]
    return L

def band_profile(T, labs, tag=''):
    # Forest and clearing lightness against distance from a sheet edge; a flat line means no band along the seams.
    bins = [0, 15, 40, 80, 140, 220, 320]; out = {}
    cells = {x['rc'] for x in T}
    for name, cl in (('forest', 0), ('clearing', 1)):
        vs = []
        for x, l in zip(T, labs):
            r, c = x['rc']; K = classify(l); h, w = l.shape[:2]
            yy, xx = np.mgrid[0:h, 0:w]
            d = np.full((h, w), 1e9, np.float32)
            if (r-1, c) in cells: d = np.minimum(d, yy)
            if (r+1, c) in cells: d = np.minimum(d, h-1-yy)
            if (r, c-1) in cells: d = np.minimum(d, xx)
            if (r, c+1) in cells: d = np.minimum(d, w-1-xx)
            row = []
            for a, b in zip(bins, bins[1:]):
                m = (K == cl) & (d >= a) & (d < b)
                row.append(l[..., 0][m].mean() if m.sum() > 400 else np.nan)
            vs.append(row)
        p = np.nanmean(np.array(vs), 0)*100
        out[name] = p-p[-1]
    return {k: [round(float(x), 2) for x in v] for k, v in out.items()}

def stack2(T, grid, base, rows, cols, order=3, lam=.005, alpha=(.8, .6, .7, .4), along=30, node=24, rounds=(3, 3, 2), sigmas=((260, 180, 120), (90,), (60,)), finish=.6):
    M = fit_global(T, grid, order=order, lam=lam)
    L = [apply_global(x, m, order) for x, m in zip(base, M)]
    for sgs, rn in zip(sigmas, rounds):
        for sg in sgs:
            L, _, _ = dodge(T, base, L, rows, cols, sigma=sg, alpha=alpha if sgs == sigmas[0] else tuple(a*finish for a in alpha))
        for _ in range(rn):
            F = fit_bilateral(T, grid, L, along=along, node=node)
            L = [apply_bilateral(a, f) for a, f in zip(L, F)]
    return L

def smooth(a, lo, hi):
    x = np.clip((a-lo)/(hi-lo), 0, 1); return x*x*(3-2*x)

def finish(T, grid, base, L, order=3, lam=.005, chroma=.965):
    # Warm inks (sand, roads, town tint) were never green: keep their hue from the global step, and trim the saturation the matching added.
    M = fit_global(T, grid, order=order, lam=lam)
    out = []
    for x, m, l in zip(base, M, L):
        g = apply_global(x, m, order)
        s = cv2.GaussianBlur(x, (0, 0), 1.2)
        w = smooth(s[..., 1], -.022, -.004)*smooth(np.hypot(s[..., 1], s[..., 2]), .02, .05)
        o = l.copy()
        o[..., 1:] = l[..., 1:]*chroma*(1-w)[..., None]+g[..., 1:]*w[..., None]
        out.append(o)
    return out


def ink_guard(src, out, sig=12):
    # Printed inks keep their colour. Thin blue lines are found by being bluer than their surroundings, so flat ocean tints stay matched;
    # they take the shift of the water around them. Warm inks (sand, roads, town tint) keep their original hue outright.
    s = cv2.GaussianBlur(src, (0, 0), .7)
    bg = cv2.GaussianBlur(src[..., 2], (0, 0), sig)
    blue = np.maximum(smooth(bg-s[..., 2], .008, .022), smooth(-s[..., 2], .028, .05))
    warm = smooth(s[..., 1], -.012, .004)*smooth(np.hypot(s[..., 1], s[..., 2]), .03, .06)
    d = out[..., 1:]-src[..., 1:]
    shift = np.stack([cv2.GaussianBlur(d[..., c], (0, 0), sig) for c in range(2)], -1)
    o = out.copy()
    o[..., 1:] += (src[..., 1:]+shift-out[..., 1:])*blue[..., None]
    o[..., 1:] += (src[..., 1:]-o[..., 1:])*warm[..., None]
    return o

def trim(L, chroma=.965):
    o = [l.copy() for l in L]
    for x in o: x[..., 1:] *= chroma
    return o

def water_mask(lab):
    return smooth(-cv2.GaussianBlur(lab, (0, 0), 1)[..., 2], .0, .018)

def water_pass(T, grid, L, rounds=3, limits=(.16, .09), along=30, node=24):
    # For blocks with saturated water: seam solve on cool pixels only, with looser limits, applied through a soft water mask so land keeps its own correction.
    cool = lambda c: c[..., 2] < -.004
    for _ in range(rounds):
        F = fit_bilateral(T, grid, L, along=along, node=node, hi_eps=.003, select=cool, limits=limits)
        L = [apply_bilateral(a, f, weight=water_mask(a)) for a, f in zip(L, F)]
    return L
