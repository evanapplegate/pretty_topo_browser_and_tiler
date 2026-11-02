# Measure the printed neatline stroke against the nominal 7.5' edge, per sheet and per edge.
import glob, os, re, sys, json
import numpy as np, rasterio
from pyproj import Transformer
OUT=sys.argv[1]
SRC = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos/src'
SHEETS = {s['scan']: s for s in json.load(open(os.path.dirname(os.path.abspath(__file__))+'/sheets.json'))}
def sheet(f):
    s = SHEETS[int(re.search(r'_(\d+)_\d{4}_\d+_geo\.tif', os.path.basename(f)).group(1))]
    w, so, e, n = s['bbox']
    return s, dict(westbc=w, eastbc=e, southbc=so, northbc=n)
H=22; BAND=4; STEP=20
res={}
for f in sorted(glob.glob(SRC+'/*.tif')):
    s_,b=sheet(f); name=s_['name']
    W,E,N,S=b['westbc'],b['eastbc'],b['northbc'],b['southbc']
    with rasterio.open(f) as d:
        rgb=d.read().astype(np.float32); gray=rgb.mean(0)
        t=Transformer.from_crs('EPSG:4267',d.crs,always_xy=True); inv=~d.transform
        h,w=gray.shape
        res[name]={}
        for edge in 'WENS':
            n=int(6900/STEP)
            s=np.linspace(0,1,n)
            if edge in 'WE':
                lon=np.full(n,W if edge=='W' else E); lat=N+(S-N)*s
            else:
                lat=np.full(n,N if edge=='N' else S); lon=W+(E-W)*s
            X,Y=t.transform(lon,lat)
            px,py=inv*(X,Y); px=np.asarray(px); py=np.asarray(py)
            outer=np.full(n,np.nan); inner=np.full(n,np.nan)
            for i in range(n):
                if edge in 'WE':
                    r=int(round(py[i])); c=px[i]-0.5
                    if r-BAND<0 or r+BAND>=h: continue
                    c0=int(round(c)); p=gray[r-BAND:r+BAND+1,c0-H:c0+H+1].mean(0); frac=c-c0
                    sign=1 if edge=='W' else -1
                else:
                    r=int(round(px[i])); c=py[i]-0.5
                    if r-BAND<0 or r+BAND>=w: continue
                    c0=int(round(c)); p=gray[c0-H:c0+H+1,r-BAND:r+BAND+1].mean(1); frac=c-c0
                    sign=1 if edge=='N' else -1
                # offsets are measured inward from nominal, in source pixels
                off=np.arange(-H,H+1)-frac if sign==1 else (np.arange(-H,H+1)-frac)[::-1]*-1
                if sign==-1: p=p[::-1]
                base=np.median(p[:8])
                if base<195 or p[:8].min()<170: continue
                j=np.argmax(p<base-60)
                if p[j]>=base-60 or j==0: continue
                k=j+int(np.argmin(p[j:j+7])); dark=p[k]
                if dark>110: continue
                th=(base+dark)/2
                j=np.argmax(p[:k+1]<th)
                outer[i]=off[j-1]+(p[j-1]-th)/(p[j-1]-p[j])*(off[j]-off[j-1])
                insideL=np.median(p[k+6:k+14]) if k+14<len(p) else np.nan
                if insideL-dark>70:
                    th2=(dark+insideL)/2
                    m=k+int(np.argmax(p[k:]>th2))
                    if p[m]>th2:
                        inner[i]=off[m-1]+(th2-p[m-1])/(p[m]-p[m-1])*(off[m]-off[m-1])
            # robust fit of the outer edge
            ok=np.isfinite(outer); t01=s
            keep=ok.copy()
            for _ in range(6):
                c=np.polyfit(t01[keep],outer[keep],5)
                r=outer-np.polyval(c,t01)
                sd=max(np.nanstd(r[keep]),0.15)
                keep=ok&(np.abs(r)<2.5*sd)
            fit=np.polyval(c,t01)
            wid=inner-outer
            res[name][edge]=dict(coef=c.tolist(),n_ok=int(ok.sum()),n_keep=int(keep.sum()),n=n,
                 rms=float(np.std(r[keep])),fit_min=float(fit.min()),fit_max=float(fit.max()),
                 width=float(np.nanmedian(wid)),width_n=int(np.isfinite(wid).sum()))
            q=res[name][edge]
            print(f"{name:14s} {edge} valid {q['n_ok']:3d}/{n} kept {q['n_keep']:3d} rms {q['rms']:.2f} outer-offset {q['fit_min']:+.2f}..{q['fit_max']:+.2f} stroke {q['width']:.2f} (n={q['width_n']})")
json.dump(res,open(OUT,'w'),indent=1)
