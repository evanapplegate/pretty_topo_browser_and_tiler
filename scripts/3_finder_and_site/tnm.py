# Page through TNM Historical Topo search results; shared by the probe and the scan.
import json, urllib.parse, urllib.request, time
BASE = 'https://tnmaccess.nationalmap.gov/api/v1/products?'
def page(**k):
    u = BASE+urllib.parse.urlencode(dict(datasets='Historical Topographic Maps', outputFormat='JSON', **k))
    for t in range(4):
        try:
            return json.load(urllib.request.urlopen(u, timeout=90))
        except Exception:
            time.sleep(2+3*t)
    raise RuntimeError('failed '+u)
def all_items(**k):
    out = []; off = 0
    while True:
        d = page(max=200, offset=off, **k); it = d.get('items', [])
        out += it; off += len(it)
        if not it or off >= d.get('total', 0): return out, d.get('total')
