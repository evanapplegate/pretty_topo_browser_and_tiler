# List candidate sheets from TNM, score every thumbnail, and save the features for ranking.
import csv, json, pickle, re, time
from concurrent.futures import ThreadPoolExecutor as TP
import numpy as np, tnm, hue
t0=time.time()
se,tot=tnm.all_items(bbox='-98,24.5,-75,36.5',prodExtents='7.5 x 7.5 minute',start='1965-01-01',end='1995-12-31',dateType='Publication')
print('southeast listed',len(se),'of',tot,flush=True)
oq=json.load(open('ortho_all.json'))
cand={}
for src,items in (('se',se),('q',oq)):
    for i in items:
        u=(i.get('urls') or {}).get('GeoTIFF')
        if not u or not i.get('previewGraphicURL'): continue
        r=cand.setdefault(u,dict(item=i,q=False))
        if src=='q': r['q']=True
print('unique sheets with GeoTIFF',len(cand),flush=True)
def run(kv):
    u,r=kv
    a=hue.fetch(r['item']['previewGraphicURL'])
    return u,(None if a is None else hue.features(a))
out={}; L=list(cand.items())
with TP(12) as e:
    for n,(u,f) in enumerate(e.map(run,L),1):
        out[u]=f
        if n%1000==0: print(n,round(time.time()-t0),'s',flush=True)
pickle.dump((cand,out),open('scan.pkl','wb'))
print('done',len(out),'failed',sum(v is None for v in out.values()),round(time.time()-t0),'s')
