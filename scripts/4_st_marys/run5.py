# Score candidate settings on seam visibility, spread, detail and colour shift.
import json, numpy as np, tone as t
T, grid, rows, cols = t.load()
base = [x['lab'] for x in T]
print('raw', {k: round(v, 2) for k, v in t.visibility(T, grid, base).items()}, flush=True)
V = {
 'A now':          dict(),
 'B tighter':      dict(along=30, node=24),
 'C tightest':     dict(along=20, node=20),
 'D stronger':     dict(seam_w=80.),
 'E more rounds':  dict(rounds=5),
 'F softer dodge': dict(alpha=(.6, .45, .5, .3)),
 'G less tone':    dict(tone_w=.25),
}
R = {}
for n, kw in V.items():
    L = t.stack(T, grid, base, rows, cols, **kw)
    v = t.visibility(T, grid, L); m = t.metrics(T, grid, L, base)
    shift = float(np.mean([np.median(t.de(a, b)) for a, b in zip(L, base)]))
    print(f"{n:15s} vis {v['ratio']:.2f} worst {v['ratio_worst']:.2f} step {v['seam']:.2f}/{v['control']:.2f} | land {m['land_spread']:.2f} water {m['water_spread']:.2f} chroma {m['chroma']:.3f} detail {m['detail']:.3f}/{m['detail_min']:.3f} shift {shift:.1f}", flush=True)
