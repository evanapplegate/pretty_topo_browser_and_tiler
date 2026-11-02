# Georeference the Photoshop render on the original mosaic grid, reusing the original empty-cell mask as alpha.
import numpy as np, rasterio
S='/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/scripts/2_psd_and_tone'
M='/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/nw_fl_topos/FL_Bruce_IndianPass_1982_24000_mosaic.tif'
A=np.memmap(S+'/nw_ps.raw','uint8','r',shape=(47740,41524,3))
with rasterio.open(M) as d:
    mk=d.dataset_mask(); crs=d.crs; tr=d.transform
with rasterio.open(S+'/nw_rgba.tif','w',driver='GTiff',width=41524,height=47740,count=4,dtype='uint8',crs=crs,transform=tr,BIGTIFF='YES',tiled=True,blockxsize=512,blockysize=512,photometric='RGB',alpha='YES') as o:
    for i in range(3):
        o.write(np.array(A[...,i]),i+1)
    o.write(mk,4)
print('mask filled fraction',round(float((mk>0).mean()),4))
