# Build a deployable copy of the site: finished clusters use matched images, everything else keeps its originals. Same file names, so app.js is unchanged.
import collections, glob, json, os, shutil, sys
import blocks as b
OUT = sys.argv[1]
HOLD = set()                    # clusters listed here stay on their originals until they pass review
G, C, Q, rep = b.clusters()
shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT+'/clip'); os.makedirs(OUT+'/clip8')
for f in ('index.html', '404.html', 'app.js', 'sheets.js', 'chop.png', 'favicon.png', 'og.jpg', 'robots.txt', 'sitemap.xml', '_headers'): shutil.copy2(f'{b.SITE}/{f}', OUT)
use = {}; count = collections.Counter(); skipped = []
for i, g in enumerate(G):
    if len(g) < 2: continue
    if i in HOLD: count['held for review'] += sum(len(Q[tuple(C[c])]) for c in g); continue
    if not os.path.exists(f'work/c{i}.json'):
        skipped.append((i, len(g))); continue
    for c in g:
        for s in Q[tuple(C[c])]: use[s['scan']] = 1
if os.path.exists('work/crest.json'):
    multi = {tuple(C[c]) for g in G if len(g) > 1 for c in g}
    for bbox in Q:
        if bbox in multi: continue
        top = rep(bbox)['scan']
        for s in Q[bbox]:
            if s['scan'] != top: use[s['scan']] = 1     # the top sheet keeps its original, so it isn't JPEG-compressed again
missing = [s for s in use if not (os.path.exists(f'{b.SITE}/clip8_tm/{s}.jpg') and os.path.exists(f'{b.SITE}/clip_tm/{s}.jpg'))]
assert not missing, missing[:5]
for r in b.R:
    s = r['scan']; d = '_tm' if s in use else ''
    shutil.copy2(f'{b.SITE}/clip{d}/{s}.jpg', f'{OUT}/clip/{s}.jpg'); shutil.copy2(f'{b.SITE}/clip8{d}/{s}.jpg', f'{OUT}/clip8/{s}.jpg')
    count['matched' if s in use else 'original'] += 1
print(dict(count), '| clusters not ready', skipped)
print('by state, matched', collections.Counter(r['st'] for r in b.R if r['scan'] in use).most_common(12))
json.dump(sorted(use), open('work/deployed_matched.json', 'w'))
