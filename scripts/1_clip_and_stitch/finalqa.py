import glob, re, sys, numpy as np, rasterio, cv2
from pyproj import Transformer
M='FL_CapeCanaveral_1976_24000_mosaic.tif'
COLS,ROWS=6036,6816
d=rasterio.open(M); print('crs',d.crs.to_string(),'size',d.width,d.height,'overviews',d.overviews(1),'bounds',tuple(round(v,9) for v in d.bounds))
A=np.moveaxis(d.read(),0,-1); g=A.mean(2).astype(np.float32)
print('pure black px',int((A.max(2)==0).sum()),' pure white px %.3f%%'%(100*(A.min(2)==255).mean()))
for tag,p in (('top',g[:12].mean(1)),('bottom',g[-12:][::-1].mean(1)),('left',g[:,:12].mean(0)),('right',g[:,-12:][::-1].mean(0))):
    print('outer edge',tag,' '.join(f'{v:.0f}' for v in p[:8]))
hp=lambda a:a-cv2.GaussianBlur(a.reshape(-1,1).astype(np.float32),(1,41),10).ravel()
def shift(a,b,L=360,R=14):
    a=hp(a);b=hp(b);out=[]
    for i in range(0,len(a)-L,L//2):
        x=a[i:i+L];y=b[i+R:i+L-R]
        if x.std()<5 or y.std()<5: continue
        c=np.array([np.corrcoef(x[k:k+len(y)],y)[0,1] for k in range(2*R+1)])
        k=int(c.argmax())
        if c[k]>0.6 and 0<k<2*R: out.append(k-R)
    return np.array(out)
def show(tag,r):
    if len(r): print(f'{tag:14s} n={len(r):3d} median {np.median(r):+.1f}  p90|s| {np.percentile(abs(r),90):.1f}  max|s| {abs(r).max()} px')
    else: print(tag,'no usable blocks')
for i,t in enumerate(['row1','row2','row3']):
    a=g[i*ROWS:(i+1)*ROWS]; show('E-W join '+t,shift(a[:,COLS-4:COLS-1].mean(1),a[:,COLS+1:COLS+4].mean(1)))
for i in (1,2):
    for c,t in ((0,'west'),(1,'east')):
        a=g[:,c*COLS:(c+1)*COLS]; show(f'N-S join {i} {t}',shift(a[i*ROWS-4:i*ROWS-1].mean(0),a[i*ROWS+1:i*ROWS+4].mean(0)))
# georef survival: same lon/lat patch in source sheet vs mosaic, at 5 points per sheet
for f in sorted(glob.glob('FL_*_tif/*.tif')):
    b={k:float(v) for k,v in re.findall(r'<(westbc|eastbc|northbc|southbc)>([^<]+)',open(f+'.xml',errors='ignore').read())}
    s=rasterio.open(f); t=Transformer.from_crs('EPSG:4267',s.crs,always_xy=True); inv=~s.transform; res=[]
    for fu,fv in ((.5,.5),(.2,.2),(.8,.2),(.2,.8),(.8,.8)):
        lon=b['westbc']+fu*.125; lat=b['northbc']-fv*.125
        sx,sy=inv*t.transform(lon,lat); mx,my=~d.transform*(lon,lat)
        h=200
        p=s.read(window=((int(sy)-h,int(sy)+h),(int(sx)-h,int(sx)+h))).mean(0).astype(np.float32)
        q=g[int(my)-h:int(my)+h,int(mx)-h:int(mx)+h]
        w=cv2.createHanningWindow((2*h,2*h),cv2.CV_32F)
        (dx,dy),r=cv2.phaseCorrelate(p.astype(np.float64),q.astype(np.float64),w.astype(np.float64))
        if r>0.1: res.append(np.hypot(dx-(mx-int(mx)-(sx-int(sx))),dy-(my-int(my)-(sy-int(sy)))))
    print(f.split('/')[1].split('_')[1].ljust(15),'source vs mosaic offset px',' '.join(f'{v:.1f}' for v in res))
