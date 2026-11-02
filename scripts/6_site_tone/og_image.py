# Cut the 1200x630 social preview from a tone-matched mosaic.
import sys, numpy as np, rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window
from PIL import Image
src, cx, cy, width, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
with rasterio.open(src) as d:
    h = int(width*630/1200); x = int(cx*d.width-width/2); y = int(cy*d.height-h/2)
    x = max(0, min(x, d.width-width)); y = max(0, min(y, d.height-h))
    a = d.read(window=Window(x, y, width, h), out_shape=(3, 630, 1200), resampling=Resampling.average)
Image.fromarray(np.moveaxis(a, 0, -1)).save(out, 'JPEG', quality=86, optimize=True, progressive=True)
