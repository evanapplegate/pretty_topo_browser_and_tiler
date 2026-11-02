import glob, sys, numpy as np, rasterio
from rasterio.enums import Resampling
from PIL import Image
order=['Orsino','False Cape','Courtenay','Cape Canaveral','Cocoa_','Cocoa Beach']
files=sorted(glob.glob('*/*.tif'), key=lambda f:[i for i,n in enumerate(order) if n in f][0])
W=480;Hh=570
s=Image.new('RGB',(W*2,Hh*3),'white')
for i,f in enumerate(files):
    with rasterio.open(f) as d:
        a=d.read(out_shape=(3,Hh,W),resampling=Resampling.average)
    s.paste(Image.fromarray(np.moveaxis(a,0,-1)),((i%2)*W,(i//2)*Hh))
s.save(sys.argv[1])
