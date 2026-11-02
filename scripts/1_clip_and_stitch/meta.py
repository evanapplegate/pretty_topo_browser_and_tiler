import glob, rasterio, re
for f in sorted(glob.glob('*/*.tif')):
    with rasterio.open(f) as d:
        print('==', f)
        print(' drv', d.driver, 'size', d.width, d.height, 'bands', d.count, d.dtypes, 'interp', d.colorinterp, 'photometric', d.tags(ns='IMAGE_STRUCTURE'), d.compression, 'nodata', d.nodata)
        print(' crs', d.crs.to_wkt()[:200] if d.crs else None)
        print(' transform', tuple(d.transform)[:6])
        print(' bounds', d.bounds)
        print(' cmap', d.count==1 and d.colorinterp[0].name=='palette' and len(d.colormap(1)))
        print(' tags', {k:v for k,v in d.tags().items()})
    x=open(f+'.xml',errors='ignore').read()
    print(' bbox', re.findall(r'<(westbc|eastbc|northbc|southbc)>([^<]+)',x))
    print(' cm', open(f+'.prj').read().split('central_meridian",')[1].split(']')[0])
