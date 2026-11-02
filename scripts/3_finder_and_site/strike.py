# Remove named sheets from the site and every list, delete their map images, and bump the data version.
import csv, json, os, re, sys
T = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/topo_finder/'
strike = set(sys.argv[1:])
R = json.load(open('site_rows.json'))
out = [r for r in R if f"{r['name']}|{r['st']}|{r['yr']}" in strike or str(r['scan']) in strike]
R = [r for r in R if r not in out]
for r in out:
    for d in ('clip', 'clip8'):
        p = f"{T}site/{d}/{r['scan']}.jpg"
        if os.path.exists(p): os.remove(p)
json.dump(R, open('site_rows.json', 'w'))
open(T+'site/sheets.js', 'w').write('const SHEETS='+json.dumps(R, separators=(',', ':'))+';\n')
rows = [dict(tier=r['tier'], state=r['st'], name=r['name'], year=r['yr'], scale=r['scale'], match_dist=r['dist'], image_cover=r['cover'], already_have=r['have'], west=r['bbox'][0], south=r['bbox'][1], east=r['bbox'][2], north=r['bbox'][3], topoview_id=r['id'], geotiff_url=r['tif'], thumb_url=r['thumb']) for r in R]
with open(T+'blue_green_image_topos.csv', 'w', newline='') as o:
    w = csv.DictWriter(o, list(rows[0])); w.writeheader(); w.writerows(rows)
open(T+'tier1_geotiff_urls.txt', 'w').write('\n'.join(r['tif'] for r in R if r['tier'] == 1 and not r['have'])+'\n')
p = T+'site/index.html'; s = open(p).read(); v = int(re.search(r'sheets\.js\?v=(\d+)', s).group(1))
open(p, 'w').write(s.replace(f'sheets.js?v={v}', f'sheets.js?v={v+1}').replace(f'app.js?v={v}', f'app.js?v={v+1}'))
print('struck', [(r['name'], r['st'], r['yr'], r['scan']) for r in out], '| sheets now', len(R))
