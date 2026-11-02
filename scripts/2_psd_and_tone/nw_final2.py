# Confirm the matched mosaic shares the original grid and mask and carries the Photoshop render's pixels.
import numpy as np, rasterio
S='/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/scripts/2_psd_and_tone'
T='/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/nw_fl_topos/FL_Bruce_IndianPass_1982_24000_mosaic'
o=rasterio.open(T+'.tif'); m=rasterio.open(T+'_matched.tif')
print('matched',m.crs.to_string(),m.width,m.height,m.count,'same grid',m.transform.almost_equals(o.transform,1e-12) and m.shape==o.shape,'overviews',m.overviews(1),m.tags(ns='IMAGE_STRUCTURE').get('LAYOUT'),m.tags(ns='IMAGE_STRUCTURE').get('JPEG_QUALITY'))
mk=m.dataset_mask(); mo=o.dataset_mask(); print('mask identical',bool((mk==mo).all()),'filled',round(float((mk>0).mean()),4))
A=np.memmap(S+'/nw_ps.raw','uint8','r',shape=(47740,41524,3)); B=np.moveaxis(m.read(),0,-1)
d=np.abs(B.astype(np.int16)-np.array(A).astype(np.int16)).mean(2); print('matched vs PS render, mean abs diff inside mask',round(float(d[mk>0].mean()),2))
