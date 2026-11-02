# Write a layered PSD/PSB directly: one group per clipped sheet (blend Normal) holding
# the sheet and an untouched Selective Color adjustment layer, placed on the mosaic grid.
import glob, os, re, struct, sys
import numpy as np, rasterio
from psd_tools.compression import rle_impl
CLIPDIR, SRCGLOB, OUT, MERGED = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == 'merged'
TMP = sys.argv[5]
os.makedirs(TMP, exist_ok=True)
names = {}
for f in glob.glob(SRCGLOB):
    p = os.path.basename(f).split('_')
    names[p[2]] = p[1]
sheets = []
for f in sorted(glob.glob(CLIPDIR+'/*.tif')):
    with rasterio.open(f) as d:
        sheets.append(dict(path=f, name=names[os.path.basename(f).split('_')[2]], w=d.width, h=d.height,
                           left=d.bounds.left, top=d.bounds.top, xres=d.res[0], yres=d.res[1]))
L0 = min(s['left'] for s in sheets); T0 = max(s['top'] for s in sheets)
for s in sheets:
    s['x'] = int(round((s['left']-L0)/s['xres'])); s['y'] = int(round((T0-s['top'])/s['yres']))
sheets.sort(key=lambda s: (s['y'], s['x']))
W = max(s['x']+s['w'] for s in sheets); H = max(s['y']+s['h'] for s in sheets)
PSB = W > 30000 or H > 30000
assert PSB == OUT.endswith('.psb')
ROW = '>I' if PSB else '>H'
LEN = '>Q' if PSB else '>I'
RES = 300
u16 = lambda v: struct.pack('>H', v)
i16 = lambda v: struct.pack('>h', v)
u32 = lambda v: struct.pack('>I', v)
i32 = lambda v: struct.pack('>i', v)
def block(key, data):
    assert len(data) % 4 == 0
    return b'8BIM'+key+u32(len(data))+data
def luni(name):
    raw = u32(len(name))+name.encode('utf-16-be')
    return block(b'luni', raw+b'\0'*(-len(raw) % 4))
def pascal(name):
    raw = name.encode('ascii', 'replace')[:255]
    raw = bytes([len(raw)])+raw
    return raw+b'\0'*(-len(raw) % 4)
RANGES = b'\x00\x00\xff\xff'*10
EMPTY = u16(0)
def record(rect, channels, name, flags, blocks, mask=False):
    out = b''.join(i32(v) for v in rect)+u16(len(channels))
    for cid, n in channels:
        out += i16(cid)+struct.pack(LEN, n)
    out += b'8BIM'+b'norm'+bytes([255, 0, flags, 0])
    m = (i32(0)*4+bytes([255, 0, 0, 0])) if mask else b''
    extra = u32(len(m))+m+u32(len(RANGES))+RANGES+pascal(name)+b''.join(blocks)
    return out+u32(len(extra))+extra
def channel_blob(arr, fh):
    rows = [rle_impl.encode(r.tobytes()) for r in arr]
    table = np.array([len(r) for r in rows], dtype='>u4' if PSB else '>u2').tobytes()
    fh.write(u16(1)); fh.write(table)
    for r in rows: fh.write(r)
    return 2+len(table)+sum(len(r) for r in rows)
def solid_blob(w, h, value=255):
    row = rle_impl.encode(bytes([value])*w)
    table = np.full(h, len(row), dtype='>u4' if PSB else '>u2').tobytes()
    return u16(1)+table+row*h
SELC = u16(1)+u16(0)+bytes(80)
recs = []; data = []; lid = 1; merged = np.full((H, W, 3), 255, np.uint8) if MERGED else None
ids = lambda: block(b'lyid', u32(lid))
empties = [(c, 2) for c in (-1, 0, 1, 2)]
for s in reversed(sheets):
    with rasterio.open(s['path']) as d:
        a = d.read()
    if MERGED: merged[s['y']:s['y']+s['h'], s['x']:s['x']+s['w']] = np.moveaxis(a, 0, -1)
    tmp = os.path.join(TMP, re.sub(r'\W', '', s['name'])+'.bin')
    alpha = solid_blob(s['w'], s['h'])
    with open(tmp, 'wb') as fh:
        lens = [channel_blob(a[i], fh) for i in range(3)]
    # closing divider
    recs.append(record((0, 0, 0, 0), empties, '</Layer group>', 24, [luni('</Layer group>'), ids(), block(b'lsct', u32(3))])); lid += 1
    data.append(EMPTY*4)
    # sheet
    rect = (s['y'], s['x'], s['y']+s['h'], s['x']+s['w'])
    recs.append(record(rect, [(-1, len(alpha)), (0, lens[0]), (1, lens[1]), (2, lens[2])], s['name'], 8, [luni(s['name']), ids()])); lid += 1
    data.append(alpha); data.append(tmp)
    # adjustment
    recs.append(record((0, 0, 0, 0), empties+[(-2, 2)], 'Selective Color', 24, [luni('Selective Color'), ids(), block(b'selc', SELC)], mask=True)); lid += 1
    data.append(EMPTY*5)
    # group header, Normal rather than Pass Through
    recs.append(record((0, 0, 0, 0), empties, s['name'], 24, [luni(s['name']), ids(), block(b'lsct', u32(1)+b'8BIM'+b'norm')])); lid += 1
    data.append(EMPTY*4)
    print(s['name'], s['x'], s['y'], 'MB', sum(lens)//1048576, flush=True)
head = i16(len(recs))+b''.join(recs)
size = len(head)+sum(os.path.getsize(d) if isinstance(d, str) else len(d) for d in data)
pad = size % 2
info = size+pad
glob_mask = u32(0)
res = b'8BIM'+u16(1005)+u16(0)+u32(16)+u32(RES << 16)+u16(1)+u16(1)+u32(RES << 16)+u16(1)+u16(1)
ustr = lambda t: u32(len(t))+t.encode('utf-16-be')
vi = u32(1)+bytes([1 if MERGED else 0])+ustr('Python')+ustr('Python')+u32(1)
res += b'8BIM'+u16(1057)+u16(0)+u32(len(vi))+vi+b'\0'*(len(vi) % 2)
part = OUT+'.part'
with open(part, 'wb') as o:
    o.write(b'8BPS'+u16(2 if PSB else 1)+bytes(6)+u16(3)+u32(H)+u32(W)+u16(8)+u16(3))
    o.write(u32(0))
    o.write(u32(len(res))+res)
    o.write(struct.pack(LEN, len(struct.pack(LEN, 0))+info+len(glob_mask)))
    o.write(struct.pack(LEN, info))
    o.write(head)
    for d in data:
        if isinstance(d, str):
            with open(d, 'rb') as fh:
                while True:
                    c = fh.read(1 << 24)
                    if not c: break
                    o.write(c)
            os.remove(d)
        else:
            o.write(d)
    if pad: o.write(b'\0')
    o.write(glob_mask)
    o.write(u16(1))
    if MERGED:
        planes = [[rle_impl.encode(r.tobytes()) for r in merged[..., i]] for i in range(3)]
        o.write(np.array([len(r) for p in planes for r in p], dtype='>u4' if PSB else '>u2').tobytes())
        for p in planes:
            for r in p: o.write(r)
    else:
        row = rle_impl.encode(bytes([255])*W)
        o.write(np.full(H*3, len(row), dtype='>u4' if PSB else '>u2').tobytes())
        o.write(row*(H*3))
os.replace(part, OUT)
print('wrote', OUT, os.path.getsize(OUT)//1048576, 'MB', W, H, 'groups', len(sheets))
