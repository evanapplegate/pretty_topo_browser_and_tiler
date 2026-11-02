# Full-resolution render: learn a local affine colour map (before to after) per sheet at quarter scale, then apply it to the original pixels.
import glob, json, multiprocessing as mp, os, sys, time
import cv2, numpy as np, rasterio, rasterio.enums
import tone as t

OUT = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos/matched'
FINAL = 'work/final_q.npz'
R, EPS = 6, 2e-4

def local_affine(I, p, r=R, eps=EPS):
    # A guided filter on the colour change, so full-resolution detail comes from the source, not the small image.
    box = lambda x: cv2.blur(x, (2*r+1, 2*r+1), borderType=cv2.BORDER_REFLECT)
    h, w = I.shape[:2]; d = p-I
    mI = box(I); mD = box(d)
    S = np.zeros((h, w, 3, 3), np.float32); C = np.zeros((h, w, 3, 3), np.float32)
    for i in range(3):
        for j in range(i, 3):
            S[..., i, j] = S[..., j, i] = box(I[..., i]*I[..., j])-mI[..., i]*mI[..., j]
        for c in range(3):
            C[..., i, c] = box(I[..., i]*d[..., c])-mI[..., i]*mD[..., c]
    S += eps*np.eye(3, dtype=np.float32)
    a = np.linalg.solve(S, C).astype(np.float32)
    b = mD-(a*mI[..., :, None]).sum(2)
    a = np.stack([box(a[..., i, c]) for i in range(3) for c in range(3)], -1)
    return a, box(b)

def one(args):
    name, f, q0, q1 = args
    t0 = time.time()
    with rasterio.open(f) as d:
        prof = d.profile.copy(); src = np.moveaxis(d.read(), 0, -1)
    H, W = src.shape[:2]
    a, b = local_affine(q0, q1)
    lab = t.rgb2oklab(src.astype(np.float32)/255).astype(np.float32); del src
    up = lambda x: cv2.resize(x, (W, H), interpolation=cv2.INTER_CUBIC)
    out = lab.copy()
    for c in range(3):
        out[..., c] += sum(up(a[..., i*3+c])*lab[..., i] for i in range(3))+up(b[..., c])
    out = t.gamut_map(t.ink_guard(lab, out))
    del lab
    rgb = (np.clip(t.oklab2rgb(out), 0, 1)*255+.5).astype(np.uint8)
    q = cv2.resize(out, (q0.shape[1], q0.shape[0]), interpolation=cv2.INTER_AREA)
    miss = float(np.median(t.de(q, t.ink_guard(q0, q1, 3))))
    prof.update(count=3, dtype='uint8', compress='deflate', predictor=2, zlevel=6, tiled=True, blockxsize=512, blockysize=512, photometric='RGB')
    with rasterio.open(f'{OUT}/{os.path.basename(f)}', 'w', **prof) as o:
        o.write(np.moveaxis(rgb, -1, 0))
        o.colorinterp = [rasterio.enums.ColorInterp.red, rasterio.enums.ColorInterp.green, rasterio.enums.ColorInterp.blue]
    return name, round(miss, 3), round(time.time()-t0)

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    T, grid, rows, cols = t.load()
    Z = np.load(FINAL)
    jobs = [(x['s']['name'], x['f'], x['lab'], Z[str(x['s']['scan'])].astype(np.float32)) for x in T]
    with mp.get_context('fork').Pool(3) as p:
        for r in p.imap_unordered(one, jobs): print(r, flush=True)
