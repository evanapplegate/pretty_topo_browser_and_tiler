# Third pass: reclassify from the corrected image on every pass, and inspect the worst seams directly.
import numpy as np, tone as t
from PIL import Image
T, grid, rows, cols = t.load()
base = [x['lab'] for x in T]
L, info = t.pipeline(T, grid, base, rows, cols)
m = t.metrics(T, grid, L, base)
print({a: (round(b, 3) if isinstance(b, float) else b) for a, b in m.items()})
print('baseline med %.2f p90 %.2f' % t.baseline(T, L))
for q in t.last_seams[:12]: print('  %-22s med %.1f p90 %.1f' % (q[2], q[0], q[1]))
K = t.canvas(T, [t.classify(b) for b in L], rows, cols)[..., 0]
print('class share', {n: round(float((K == i).mean()), 3) for i, n in enumerate(t.CLASSES)}, 'other', round(float((K < 0).mean()), 3))
G = [t.gamut_map(l) for l in L]
Image.fromarray(t.mosaic(T, G, rows, cols, 2)).resize((1103, 1278), Image.LANCZOS).save('qa/run3.png')
t.seam_crops(T, grid, G, rows, cols, 'qa/run3_seams.png')
