# Keep sheets whose map body is image-toned blue or green, rank by colour distance to the user's sheets, write CSV and contact sheet.
import collections, csv, glob, os, pickle, re, urllib.parse
from concurrent.futures import ThreadPoolExecutor as TP
import numpy as np, hue
from PIL import Image, ImageDraw
T='/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/'
OUT=T+'topo_finder/'; os.makedirs(OUT,exist_ok=True)
cand,feat=pickle.load(open('scan.pkl','rb'))
mine={os.path.basename(f).replace('_geo.tif','') for g in ('FL_*_tif/*.tif','louisiana_topos/LA_*_tif/*.tif','nw_fl_topos/FL_*_tif/*.tif') for f in glob.glob(T+g)}
GREEN=np.array([52.6,-28.7,30.4]); BLUE=np.array([65.1,-19.,-5.1])
rows=[]; why=collections.Counter()
for u,f in feat.items():
    if not f: why['no thumbnail']+=1; continue
    if f['rich']<.2: why['line map']+=1; continue
    if f['warm_img']>=.12: why['orange or red']+=1; continue
    lg,lb=f['lab_green'],f['lab_blue']
    cg=np.hypot(*lg[1:]) if lg[0] is not None else 0; cb=np.hypot(*lb[1:]) if lb[0] is not None else 0
    wg,wb=f['rich_green'],f['rich_blue']
    hg=float(np.degrees(np.arctan2(lg[2],lg[1]))%360) if lg[0] is not None else None
    # Sheets with image-toned water qualify on their blue, which keeps dark teal marsh; sheets without must be dark, saturated green.
    if wb>=.02:
        if cb<8: why['grey or olive']+=1; continue
    elif cg<30 or f['L']>=74 or (hg is not None and hg<115):
        why['grey or olive']+=1; continue
    dg=np.linalg.norm(np.array(lg,float)-GREEN) if lg[0] is not None else None
    db=np.linalg.norm(np.array(lb,float)-BLUE) if lb[0] is not None else None
    w=[(d,x) for d,x in ((dg,wg),(db,wb)) if d is not None]
    dist=sum(d*x for d,x in w)/sum(x for _,x in w)
    if dist>26: why['too far from your colours']+=1; continue
    i=cand[u]['item']; m=re.search(r'1:(\d+)-scale Quadrangle for (.+), ([A-Z]{2}) (\d{4})',i['title'])
    if not m: why['unparsed title']+=1; continue
    base=urllib.parse.unquote(u.rsplit('/',1)[1]).replace('_geo.tif',''); bb=i['boundingBox']
    rows.append(dict(tier=1 if dist<=15 else 2,state=m[3],name=m[2],year=int(m[4]),scale=int(m[1]),match_dist=round(dist,1),image_cover=round(f['rich'],2),green_share=round(wg,2),blue_share=round(wb,2),
                     already_have=base in mine,west=bb['minX'],south=bb['minY'],east=bb['maxX'],north=bb['maxY'],size_mb=None,geotiff_url=u,thumb_url=i['previewGraphicURL'],_tn=i['previewGraphicURL']))
rows.sort(key=lambda r:r['match_dist'])
print('candidates',len(feat),'kept',len(rows),dict(why))
print('of your 57:',sum(r['already_have'] for r in rows),'kept')
print('states',collections.Counter(r['state'] for r in rows).most_common())
print('years',sorted(collections.Counter(r['year'] for r in rows).items()))
print('tiers',collections.Counter(r['tier'] for r in rows))
print('new, not already held',sum(not r['already_have'] for r in rows))
gl=[r for r in rows if r['state'] in ('LA','TX','MS','AL')]
print('near your view (bbox -94.5,29,-92,30.5):',sum(1 for r in rows if r['west']>=-94.5 and r['east']<=-92 and r['south']>=29 and r['north']<=30.5))
with open(OUT+'blue_green_image_topos.csv','w',newline='') as o:
    k=[x for x in rows[0] if not x.startswith('_') and x!='size_mb']
    w=csv.DictWriter(o,k,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
order=sorted(rows,key=lambda r:(r['state'],r['match_dist']))
with TP(12) as e: A=list(e.map(lambda r:hue.fetch(r['_tn']),order))
cols=24; W,H=84,112
C=Image.new('RGB',(cols*W,(len(order)//cols+1)*H),'white'); d=ImageDraw.Draw(C)
for i,(r,a) in enumerate(zip(order,A)):
    x,y=(i%cols)*W,(i//cols)*H
    if a is not None: C.paste(Image.fromarray(a).resize((W-3,H-14),Image.LANCZOS),(x,y))
    d.text((x+1,y+H-13),f"{r['state']} {r['year']} {r['match_dist']:.0f}",fill='black')
C.save(OUT+'blue_green_image_topos_contact.png'); print(C.size)
