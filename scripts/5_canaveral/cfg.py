# Point the St Marys colour library at the Cape Canaveral clips; sheet bounds come from the clips themselves.
import glob, os, sys
import rasterio
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE+'/../4_st_marys')
import tone as t
DATA = os.path.abspath(HERE+'/../../canaveral_topos')
t.LOSSLESS = DATA+'/lossless'
t.SHEETS = {}
for f in glob.glob(t.LOSSLESS+'/*.tif'):
    p = os.path.basename(f).split('_')
    with rasterio.open(f) as d:
        b = d.bounds
    t.SHEETS[int(p[2])] = dict(scan=int(p[2]), name=p[1], st=p[0], yr=int(p[3]), bbox=[round(b.left, 6), round(b.bottom, 6), round(b.right, 6), round(b.top, 6)])
