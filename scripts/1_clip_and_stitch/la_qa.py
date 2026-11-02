import glob, re, sys, numpy as np, rasterio, cv2
from PIL import Image
S=sys.argv[1]; M='LA_Barataria_Venice_1971-73_24000_mosaic.tif'
COLS,ROWS=5980,6820
d=rasterio.open(M); print('mosaic',d.crs.to_string(),d.width,d.height,d.count,'overviews',d.overviews(1),'bounds',tuple(round(v,6) for v in d.bounds),'mask',d.mask_flag_enums[0])
A=np.moveaxis(d.read(),0,-1); mk=d.dataset_mask(); g=A.mean(2).astype(np.float32)
cells={}
for f in glob.glob(S+'/la_work/*.tif'):
    with rasterio.open(f) as c:
        cells[(round((29.75-c.bounds.top)/.125),round((c.bounds.left+90.25)/.125))]=f.split('/')[-1].split('_')[1]
exp=np.zeros(mk.shape,bool)
for r,c in cells: exp[r*ROWS:(r+1)*ROWS,c*COLS:(c+1)*COLS]=True
print('cells',len(cells),' mask matches filled cells:',bool(((mk>0)==exp).all()),' px inside cells masked:',int(((mk==0)&exp).sum()))
hp=lambda a:a-cv2.GaussianBlur(a.reshape(-1,1).astype(np.float32),(1,41),10).ravel()
def shift(a,b,L=360,R=14):
    a=hp(a);b=hp(b);out=[]
    for i in range(0,len(a)-L,L//2):
        x=a[i:i+L];y=b[i+R:i+L-R]
        if x.std()<4 or y.std()<4: continue
        cc=np.array([np.corrcoef(x[k:k+len(y)],y)[0,1] for k in range(2*R+1)])
        k=int(cc.argmax())
        if cc[k]>0.5 and 0<k<2*R: out.append(k-R)
    return out
dips=[];al=[]
for (r,c),n in sorted(cells.items()):
    t=A[r*ROWS:r*ROWS+1]
    if (r,c+1) in cells:
        a=g[r*ROWS:(r+1)*ROWS]; x=(c+1)*COLS; p=a[:,x-16:x+16].mean(0)
        dips.append((float(min(p[:12].mean(),p[-12:].mean())-p[12:20].min()),n,'E'))
        al+=shift(a[:,x-4:x-1].mean(1),a[:,x+1:x+4].mean(1))
    if (r+1,c) in cells:
        a=g[:,c*COLS:(c+1)*COLS]; y=(r+1)*ROWS; p=a[y-16:y+16].mean(1)
        dips.append((float(min(p[:12].mean(),p[-12:].mean())-p[12:20].min()),n,'S'))
        al+=shift(a[y-4:y-1].mean(0),a[y+1:y+4].mean(0))
dips.sort(reverse=True); al=np.array(al)
print('seams',len(dips),'worst darkening below both sides:',[(round(a,1),b,c) for a,b,c in dips[:4]])
print('along-seam offset blocks',len(al),'median %+.1f  p50|s| %.1f  p90|s| %.1f  max|s| %d px'%(np.median(al),np.median(abs(al)),np.percentile(abs(al),90),abs(al).max()))
for tag,p in (('top',g[:12,:COLS*5].mean(1)),('bottom',g[-12:,3*COLS:][::-1].mean(1))):
    print('outer edge',tag,' '.join(f'{v:.0f}' for v in p[:6]))
Image.fromarray(cv2.resize(A,(1600,int(1600*A.shape[0]/A.shape[1])),interpolation=cv2.INTER_AREA)).save(S+'/qa/la_mosaic.png')
