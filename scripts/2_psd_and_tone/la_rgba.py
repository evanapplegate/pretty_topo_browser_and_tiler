# Georeference the Photoshop render on the original mosaic grid, reusing the original empty-cell mask as alpha.
import numpy as np, rasterio
S='/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/scripts/2_psd_and_tone'
M='/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/louisiana_topos/LA_Barataria_Venice_1971-73_24000_mosaic.tif'
A=np.memmap(S+'/la_ps.raw','uint8','r',shape=(27280,47840,3))
with rasterio.open(M) as d:
    mk=d.dataset_mask(); crs=d.crs; tr=d.transform
with rasterio.open(S+'/la_rgba.tif','w',driver='GTiff',width=47840,height=27280,count=4,dtype='uint8',crs=crs,transform=tr,BIGTIFF='YES',tiled=True,blockxsize=512,blockysize=512,photometric='RGB',alpha='YES') as o:
    for i in range(3):
        o.write(np.array(A[...,i]),i+1)
    o.write(mk,4)
print('mask filled fraction',round(float((mk>0).mean()),4))
