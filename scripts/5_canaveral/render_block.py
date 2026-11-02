# Full-resolution render of the Canaveral sheets with the St Marys renderer, in its own process so OpenCV threads never meet a fork.
import multiprocessing as mp, numpy as np, cfg, render
from cfg import t
if __name__ == '__main__':
    render.OUT = cfg.DATA+'/matched'
    T, grid, rows, cols = t.load()
    Z = np.load('work/final2_q.npz')
    jobs = [(x['s']['name'], x['f'], x['lab'], Z[str(x['s']['scan'])].astype(np.float32)) for x in T]
    with mp.get_context('fork').Pool(3) as p:
        for r in p.imap_unordered(render.one, jobs): print(r, flush=True)
