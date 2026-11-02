# Seam QA: stitch working clips in memory, flag dark seam lines, measure feature offset across seams.
import glob, sys, numpy as np, rasterio, cv2
from PIL import Image
W=sys.argv[1]; S=sys.argv[2]
COLS,ROWS=6036,6816
fs=sorted(glob.glob(W+'/*.tif'))
A=np.zeros((ROWS*3,COLS*2,3),np.uint8); filled=np.zeros((ROWS*3,COLS*2),bool)
for f in fs:
    with rasterio.open(f) as d:
        r=int(round((28.625-d.bounds.top)/0.125)); c=int(round((d.bounds.left+80.75)/0.125))
        A[r*ROWS:(r+1)*ROWS,c*COLS:(c+1)*COLS]=np.moveaxis(d.read(),0,-1)
        filled[r*ROWS:(r+1)*ROWS,c*COLS:(c+1)*COLS]=True
print('all cells filled', filled.all())
g=A.mean(2).astype(np.float32)
def report(tag,p,c):
    base=np.median(np.r_[p[c-14:c-6],p[c+6:c+14]])
    print(f'{tag:26s} line depth at seam {base-p[c-3:c+3].min():5.1f} of 255   profile', ' '.join(f'{v:.0f}' for v in p[c-5:c+5]))
# dark-line test, using a low percentile-free mean along each seam
report('vert seam row1',g[:ROWS].mean(0),COLS)
report('vert seam row2',g[ROWS:2*ROWS].mean(0),COLS)
report('vert seam row3',g[2*ROWS:].mean(0),COLS)
report('horiz seam 1 west',g[:,:COLS].mean(1),ROWS)
report('horiz seam 1 east',g[:,COLS:].mean(1),ROWS)
report('horiz seam 2 west',g[:,:COLS].mean(1),2*ROWS)
report('horiz seam 2 east',g[:,COLS:].mean(1),2*ROWS)
# feature offset: correlate 1-D profiles either side of a seam, in blocks along it
def offset(a,b):
    a=a-cv2.blur(a,(1,101)) if a.ndim==2 else a
    r=[]
    n=len(a); L=400
    for i in range(0,n-L,L):
        x=a[i:i+L]-a[i:i+L].mean(); y=b[i:i+L]-b[i:i+L].mean()
        if x.std()<6 or y.std()<6: continue
        cc=np.correlate(x,y[12:-12],'valid'); k=cc.argmax()
        peak=cc[k]/(np.linalg.norm(x[k:k+L-24])*np.linalg.norm(y[12:-12])+1e-6)
        if peak>0.75 and 0<k<len(cc)-1:
            d=(cc[k-1]-cc[k+1])/(2*(cc[k-1]-2*cc[k]+cc[k+1]))
            r.append(k+d-12)
    return np.array(r)
def seam(tag,a,b):
    r=offset(a,b)
    print(f'{tag:26s} blocks {len(r):3d}  median shift {np.median(r) if len(r) else float("nan"):+.2f} px  p90 |shift| {np.percentile(abs(r),90) if len(r) else float("nan"):.2f}')
for i,tag in enumerate(['row1','row2','row3']):
    a=g[i*ROWS:(i+1)*ROWS]
    seam('vert '+tag,a[:,COLS-5:COLS-2].mean(1),a[:,COLS+2:COLS+5].mean(1))
for i in (1,2):
    for c,tag in ((0,'west'),(1,'east')):
        a=g[:,c*COLS:(c+1)*COLS]
        seam(f'horiz {i} {tag}',a[i*ROWS-5:i*ROWS-2].mean(0),a[i*ROWS+2:i*ROWS+5].mean(0))
np.save(S+'/mosaic_preview.npy',cv2.resize(A,(COLS//3,ROWS*3//6),interpolation=cv2.INTER_AREA))
Image.fromarray(cv2.resize(A,(1200,int(1200*A.shape[0]/A.shape[1])),interpolation=cv2.INTER_AREA)).save(S+'/qa/mosaic.png')
# closeups centred on each seam at high-gradient spots
crops=[]
def pick(profile_axis,fixed,lo,hi):
    best=None;bs=-1
    for p in range(lo+200,hi-200,150):
        if profile_axis=='v': w=g[p-120:p+120,fixed-120:fixed+120]
        else: w=g[fixed-120:fixed+120,p-120:p+120]
        s=float(cv2.Laplacian(w,cv2.CV_32F).var())
        if s>bs: bs=s;best=p
    return best
pts=[]
for i in range(3): pts.append((pick('v',COLS,i*ROWS,(i+1)*ROWS),COLS))
for i in (1,2):
    for c in (0,1): pts.append((i*ROWS,pick('h',i*ROWS,c*COLS,(c+1)*COLS)))
pts.append((ROWS,COLS)); pts.append((2*ROWS,COLS))
T=Image.new('RGB',(4*484,2*484),'white')
for n,(y,x) in enumerate(pts):
    c=A[y-120:y+120,x-120:x+120]
    T.paste(Image.fromarray(c).resize((480,480),Image.NEAREST),((n%4)*484,(n//4)*484))
T.save(S+'/qa/seams.png')
print(pts)
