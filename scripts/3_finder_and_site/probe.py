import glob, json, os, re, urllib.parse, random, pickle
from concurrent.futures import ThreadPoolExecutor as TP
import numpy as np, tnm, hue
T='/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/'
pos=[]
for g,tag in ((T+'FL_*_tif/*.tif','Canaveral'),(T+'louisiana_topos/LA_*_tif/*.tif','Louisiana'),(T+'nw_fl_topos/FL_*_tif/*.tif','NWFL')):
    for f in glob.glob(g):
        b=os.path.basename(f).replace('_geo.tif',''); st=b[:2]
        pos.append((tag,b,f'https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/HistoricalTopo/PDF/{st}/24000/{urllib.parse.quote(b)}_tn.jpg'))
def run(p):
    a=hue.fetch(p[2]); return (p,None if a is None else hue.features(a))
with TP(10) as e: R=list(e.map(run,pos))
ok=[(p,f) for p,f in R if f]; print('positives fetched',len(ok),'of',len(pos)); print('thumb size',ok[0][1]['w'],ok[0][1]['h'])
for k in ('score','green','blue','darkgreen','pale','warm','L','tex'):
    v=np.array([f[k] for _,f in ok]); print(f'pos {k:9s} min {v.min():.3f} p10 {np.percentile(v,10):.3f} med {np.median(v):.3f} max {v.max():.3f}')
print('lowest pos score',sorted((round(f['score'],2),p[1]) for p,f in ok)[:6])
d=tnm.page(bbox='-98,25,-80,31.5',prodExtents='7.5 x 7.5 minute',start='1965-01-01',end='1995-12-31',dateType='Publication',max=200,offset=1500)
smp=[(i['title'],i['previewGraphicURL']) for i in d['items']]
def r2(s):
    a=hue.fetch(s[1]); return (s,None if a is None else hue.features(a))
with TP(10) as e: Q=[x for x in e.map(r2,smp) if x[1]]
sc=np.array([f['score'] for _,f in Q]); print('sample of Gulf sheets',len(Q),'score hist',np.histogram(sc,bins=[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.01])[0].tolist())
pickle.dump((ok,Q),open('probe.pkl','wb'))
it,tot=tnm.all_items(q='orthophoto')
print('national q=orthophoto',tot,len(it))
import collections
c=collections.Counter(m.group(1) for m in (re.search(r', ([A-Z]{2}) \d{4}$',i['title']) for i in it) if m)
print(c.most_common()); json.dump(it,open('ortho_all.json','w'))
