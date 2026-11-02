# Independent read-back: structure via psd_tools, pixels compared against the clipped TIFFs.
import glob, os, sys, numpy as np, rasterio
from psd_tools import PSDImage
P, CLIP = sys.argv[1], sys.argv[2]; full = len(sys.argv) > 3
p = PSDImage.open(P)
print(os.path.basename(P), p.version, p.width, p.height, 'mode', p.color_mode.name, 'depth', p.depth, 'res', [getattr(r,'horizontal',None) for r in []])
tops = list(p); print('top-level', len(tops), 'all groups', all(l.is_group() for l in tops))
bad = 0
tifs = {os.path.basename(f).split('_')[2]: f for f in glob.glob(CLIP+'/*.tif')}
import re
src = {}
for l in tops:
    k = [c.kind for c in l]; names = [c.name for c in l]
    ok = l.blend_mode.name == 'NORMAL' and k == ['pixel', 'selectivecolor'] or l.blend_mode.name == 'NORMAL' and sorted(k) == ['pixel', 'selectivecolor']
    px = next(c for c in l if c.kind == 'pixel'); adj = next(c for c in l if c.kind == 'selectivecolor')
    d = None
    for f in tifs.values():
        with rasterio.open(f) as t:
            if os.path.basename(f).split('_')[1] == re.sub(r'\s', '', px.name): d = f
    with rasterio.open(d) as t:
        a = t.read()
        x = round((t.bounds.left-min(rasterio.open(g).bounds.left for g in tifs.values()))/t.res[0]); y = round((max(rasterio.open(g).bounds.top for g in tifs.values())-t.bounds.top)/t.res[1])
    same = None
    if full:
        im = px.numpy()[..., :3]; same = bool((np.rint(im*255).astype(np.uint8) == np.moveaxis(a, 0, -1)).all())
    pos = (px.left, px.top) == (x, y) and px.width == a.shape[2] and px.height == a.shape[1]
    zero = all(all(v == 0 for v in rec) for rec in adj.data) if hasattr(adj, 'data') else None
    print(f'{l.name:22s} blend {l.blend_mode.name:7s} stack {names} kinds {k} xy {px.left},{px.top} pos_ok {pos} pixels_match {same}')
    bad += not (ok and pos and same is not False)
print('FAILED' if bad else 'ALL OK', bad)
