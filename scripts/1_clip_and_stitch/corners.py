import glob, re, sys, json
import numpy as np, rasterio
from rasterio.windows import Window
from pyproj import Transformer
from PIL import Image, ImageDraw
S=sys.argv[1]; R=int(sys.argv[2]); Z=int(sys.argv[3])
os_order=['Orsino','False Cape','Courtenay','Cape Canaveral','Cocoa_','Cocoa Beach']
files=sorted(glob.glob('*/*.tif'), key=lambda f:[i for i,n in enumerate(os_order) if n in f][0])
cell=(2*R)*Z
sheet=Image.new('RGB',(cell*4+15,(cell+4)*len(files)),'white')
d0=ImageDraw.Draw(sheet)
for r,f in enumerate(files):
    x=open(f+'.xml',errors='ignore').read()
    b={k:float(v) for k,v in re.findall(r'<(westbc|eastbc|northbc|southbc)>([^<]+)',x)}
    with rasterio.open(f) as d:
        t=Transformer.from_crs('EPSG:4267',d.crs,always_xy=True)
        corners=[(b['westbc'],b['northbc']),(b['eastbc'],b['northbc']),(b['westbc'],b['southbc']),(b['eastbc'],b['southbc'])]
        for c,(lon,lat) in enumerate(corners):
            px,py=~d.transform*t.transform(lon,lat)
            print(f.split('/')[1][:22],'NE NW SW SE'.split()[[1,0,2,3][c]],round(px,1),round(py,1),'of',d.width,d.height)
            w=Window(int(px)-R,int(py)-R,2*R,2*R)
            a=d.read(window=w,boundless=True,fill_value=255)
            im=Image.fromarray(np.moveaxis(a,0,-1)).resize((cell,cell),Image.NEAREST)
            dr=ImageDraw.Draw(im)
            cx=(px-(int(px)-R))*Z; cy=(py-(int(py)-R))*Z
            for seg in [((cx,0),(cx,cell*.2)),((cx,cell*.8),(cx,cell)),((0,cy),(cell*.2,cy)),((cell*.8,cy),(cell,cy))]:
                dr.line(seg,fill=(255,0,255),width=1)
            sheet.paste(im,(c*(cell+5),r*(cell+4)))
sheet.save(S+'/qa/corners_%d.png'%R)
