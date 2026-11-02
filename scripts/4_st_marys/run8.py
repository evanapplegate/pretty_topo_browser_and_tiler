# Final candidate: broader evening only, warm inks protected, saturation trimmed. Compared with the raw mosaic side by side.
import numpy as np, cv2, tone as t
from PIL import Image
T, grid, rows, cols = t.load()
base = [x['lab'] for x in T]
L0 = t.stack2(T, grid, base, rows, cols, rounds=(3, 4), sigmas=((260, 180, 120), (90,)), finish=.5)
L = t.finish(T, grid, base, L0)
print('band', t.band_profile(T, L), flush=True)
v = t.visibility(T, grid, L); m = t.metrics(T, grid, L, base)
print({k: round(a, 2) for k, a in v.items()}); print({a: (round(b, 3) if isinstance(b, float) else b) for a, b in m.items() if a != 'worst'})
np.savez('work/final_q.npz', **{str(x['s']['scan']): l.astype(np.float32) for x, l in zip(T, L)})
G = [t.gamut_map(l) for l in L]
Image.fromarray(t.mosaic(T, G, rows, cols, 2)).resize((1103, 1278), Image.LANCZOS).save('qa/run8.png')
t.seam_crops(T, grid, G, rows, cols, 'qa/run8_seams.png')
a = np.asarray(Image.open('qa/base.png').convert('RGB')); b = np.asarray(Image.open('qa/run8.png').convert('RGB'))
S = np.full((a.shape[0]*3//4, a.shape[1]*3//2+20, 3), 255, np.uint8); h, w = S.shape[0], a.shape[1]*3//4
S[:, :w] = cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA); S[:, -w:] = cv2.resize(b, (w, h), interpolation=cv2.INTER_AREA)
Image.fromarray(S).save('qa/run8_ba.png')
