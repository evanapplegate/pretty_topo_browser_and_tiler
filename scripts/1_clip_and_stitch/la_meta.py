import glob, re, numpy as np, rasterio, collections
rows=[]
for f in sorted(glob.glob('LA_*_tif/*.tif')):
    x=open(f+'.xml',errors='ignore').read()
    b={k:float(v) for k,v in re.findall(r'<(westbc|eastbc|northbc|southbc)>([^<]+)',x)}
    si=re.search(r'<supplinf>(.*?)</supplinf>',x,re.S).group(1)
    tint=re.search(r'Woodland Tint = (\w)',si)
    pub=re.search(r'<pubdate>(\d+)',x).group(1)
    prj=open(f+'.prj').read()
    dat=re.search(r'DATUM\["([^"]+)',prj).group(1)
    cm=re.search(r'central_meridian",([-\d.]+)',prj).group(1)
    with rasterio.open(f) as d:
        rows.append((b['northbc'],b['westbc'],f.split('/')[1].split('_')[1],b['eastbc']-b['westbc'],b['northbc']-b['southbc'],d.width,d.height,d.count,d.dtypes[0],round(d.res[0],3),d.tags(ns="IMAGE_STRUCTURE").get("COMPRESSION"),dat,cm,pub))
for r in sorted(rows,key=lambda r:(-r[0],r[1])): print(r)
print(collections.Counter((r[3],r[4]) for r in rows))
cells={(r[0],r[1]):r[2] for r in rows}
la=sorted({r[0] for r in rows},reverse=True); lo=sorted({r[1] for r in rows})
print('\n'+' '*8+' '.join(f'{v:>14.3f}' for v in lo))
for a in la: print(f'{a:7.3f} '+' '.join(f"{cells.get((a,v),'-')[:14]:>14s}" for v in lo))
print('dup cells',len(rows)-len(cells))
