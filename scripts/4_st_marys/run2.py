# Second pass: class-aware local tone mapping on top of the stronger global fit.
import numpy as np, cv2, tone as t
from PIL import Image
T, grid, rows, cols = t.load()
base = [x['lab'] for x in T]
print('seamless baseline med %.2f p90 %.2f' % t.baseline(T, base))
K = t.canvas(T, [t.classify(b) for b in base], rows, cols)[..., 0]
print('class share', {n: round(float((K == i).mean()), 3) for i, n in enumerate(t.CLASSES)}, 'other', round(float((K < 0).mean()), 3))
col = np.array([[230, 225, 215], [20, 110, 40], [150, 210, 90], [40, 170, 150], [80, 160, 230]], np.uint8)
Image.fromarray(col[K+1][::3, ::3]).resize((736, 853), Image.NEAREST).save('qa/classes.png')
L, info = t.pipeline(T, grid, base, rows, cols)
m = t.metrics(T, grid, L, base)
print({a: (round(b, 3) if isinstance(b, float) else b) for a, b in m.items()})
print('after baseline med %.2f p90 %.2f' % t.baseline(T, L))
G = [t.gamut_map(l) for l in L]
Image.fromarray(t.mosaic(T, G, rows, cols, 2)).resize((1103, 1278), Image.LANCZOS).save('qa/run2.png')
