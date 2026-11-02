import glob, re, sys, numpy as np, rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window
from pyproj import Transformer
from PIL import Image, ImageDraw
S=sys.argv[1]
info=[]
for f in glob.glob('LA_*_tif/*.tif'):
    b={k:float(v) for k,v in re.findall(r'<(westbc|eastbc|northbc|southbc)>([^<]+)',open(f+'.xml',errors='ignore').read())}
    info.append((f,b))
info.sort(key=lambda i:(-i[1]['northbc'],i[1]['westbc']))
# whole sheets, collars included, laid out on the quad grid
W,H=330,388
la0=29.75; lo0=-90.25
sh=Image.new('RGB',(W*8,H*4),(40,40,40))
R=40;Z=2;cell=2*R*Z
C=Image.new('RGB',(10*(cell+4),8*(cell+4)),'white')
n=0
widths=[];heights=[]
for f,b in info:
    with rasterio.open(f) as d:
        a=d.read(out_shape=(3,H,W),resampling=Resampling.average)
        sh.paste(Image.fromarray(np.moveaxis(a,0,-1)),(round((b['westbc']-lo0)/.125)*W,round((la0-b['northbc'])/.125)*H))
        t=Transformer.from_crs('EPSG:4267',d.crs,always_xy=True); inv=~d.transform
        pts=[(b['westbc'],b['northbc']),(b['eastbc'],b['northbc']),(b['westbc'],b['southbc']),(b['eastbc'],b['southbc'])]
        P=[inv*t.transform(*p) for p in pts]
        widths+= [P[1][0]-P[0][0],P[3][0]-P[2][0]]; heights+=[P[2][1]-P[0][1],P[3][1]-P[1][1]]
        for px,py in P:
            w=Window(int(px)-R,int(py)-R,2*R,2*R)
            a=d.read(window=w,boundless=True,fill_value=255)
            im=Image.fromarray(np.moveaxis(a,0,-1)).resize((cell,cell),Image.NEAREST)
            dr=ImageDraw.Draw(im); cx=(px-int(px)+R)*Z; cy=(py-int(py)+R)*Z
            for seg in [((cx,0),(cx,cell*.2)),((cx,cell*.8),(cx,cell)),((0,cy),(cell*.2,cy)),((cell*.8,cy),(cell,cy))]:
                dr.line(seg,fill=(255,0,255),width=1)
            C.paste(im,((n%10)*(cell+4),(n//10)*(cell+4))); n+=1
sh.save(S+'/qa/la_sheets.png'); C.save(S+'/qa/la_corners.png')
print('sheet width px %.1f..%.1f  height px %.1f..%.1f'%(min(widths),max(widths),min(heights),max(heights)))
