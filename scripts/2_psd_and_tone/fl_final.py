import json, sys, numpy as np, rasterio, tifffile
from psd_tools import PSDImage
from psd_tools.constants import Tag
S='/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/scripts/2_psd_and_tone'
T='/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/'
sl=json.load(open(S+'/fl_sliders.json')); ORDER=['reds','yellows','greens','cyans','blues','magentas','whites','neutrals','blacks']
p=PSDImage.open(T+'FL_CapeCanaveral_1976_24000_sheets.psd')
print('psd',p.version,p.width,p.height,'groups',len(list(p)),'has composite',p.has_preview())
bad=0
for g in p:
    a=[c for c in g if c.kind=='selectivecolor'][0]; d=a._record.tagged_blocks.get_data(Tag.SELECTIVE_COLOR)
    got={r:list(v) for r,v in zip(ORDER,d.data[1:])}; want=sl[g.name.replace(' ','')]
    ok=all(got[r]==list(want.get(r,[0,0,0,0])) for r in ORDER)
    print(f'{g.name:15s} blend {g.blend_mode.name} method {d.method} sliders_match {ok}'); bad+=not ok
print('slider mismatch groups',bad)
c=np.asarray(p.topil().convert('RGB')); f=tifffile.imread(S+'/fl_ps.tif')[...,:3]
print('psd composite vs flat export, mean abs diff',round(float(np.abs(c.astype(int)-f.astype(int)).mean()),3))
m=rasterio.open(T+'FL_CapeCanaveral_1976_24000_mosaic_matched.tif'); o=rasterio.open(T+'FL_CapeCanaveral_1976_24000_mosaic.tif')
print('matched',m.crs.to_string(),m.width,m.height,'same grid as original',m.transform.almost_equals(o.transform,1e-12),'overviews',m.overviews(1))
b=np.moveaxis(m.read(),0,-1); print('matched vs PS render, mean abs diff',round(float(np.abs(b.astype(int)-f.astype(int)).mean()),2))
