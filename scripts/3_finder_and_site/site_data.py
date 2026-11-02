# Join ranked hits with topoView IDs and thumbnail colours for the site.
import csv, io, json, re, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor as TP
import numpy as np, hue
T='/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/topo_finder/'
R=list(csv.DictReader(open(T+'blue_green_image_topos.csv')))
scan=lambda u:int(re.search(r'_(\d+)_\d{4}_\d+_geo\.tif',u).group(1))
for r in R: r['scan']=scan(r['geotiff_url'])
ids=sorted({r['scan'] for r in R})
B='https://energy.usgs.gov/arcgis/rest/services/topoview/ustOverlay/MapServer/0/query?'
md5={}
for i in range(0,len(ids),150):
    q=urllib.parse.urlencode(dict(where='scan_id IN (%s)'%','.join(map(str,ids[i:i+150])),outFields='scan_id,md5,drg_name',returnGeometry='false',f='json'))
    d=json.load(urllib.request.urlopen(urllib.request.Request(B+q,headers={'User-Agent':'curl/8.7.1'}),timeout=90))
    for f in d['features']:
        a=f['attributes']; md5[a['scan_id']]=(a['md5'],a['drg_name'])
print('scans',len(ids),'ids found',len(md5),'missing',[s for s in ids if s not in md5][:10])
def color(r):
    a=hue.fetch(r['thumb_url'])
    if a is None: return None
    h,w=a.shape[:2]; b=a[int(h*.1):int(h*.82),int(w*.12):int(w*.86)].reshape(-1,3)
    return '#%02x%02x%02x'%tuple(int(v) for v in b.mean(0))
with TP(12) as e: C=list(e.map(color,R))
out=[]
for r,c in zip(R,C):
    m=md5.get(r['scan'])
    if not m: continue
    out.append(dict(id=m[0],scan=r['scan'],name=r['name'],st=r['state'],yr=int(r['year']),scale=int(r['scale']),tier=int(r['tier']),dist=float(r['match_dist']),cover=float(r['image_cover']),
                    have=r['already_have']=='True',bbox=[float(r['west']),float(r['south']),float(r['east']),float(r['north'])],thumb=r['thumb_url'],color=c or '#5a8f7b',file=m[1]))
json.dump(out,open('site_rows.json','w'))
print('rows',len(out),'unique ids',len({o['id'] for o in out}),'no colour',sum(c is None for c in C)); print(out[0])
