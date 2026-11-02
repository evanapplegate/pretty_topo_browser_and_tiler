# Read the saved PSB back from disk and confirm groups, blend modes and every slider value.
import json
from psd_tools import PSDImage
from psd_tools.constants import Tag
S='/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/scripts/2_psd_and_tone'
sl=json.load(open(S+'/la_sliders.json')); ORDER=['reds','yellows','greens','cyans','blues','magentas','whites','neutrals','blacks']
p=PSDImage.open('/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/louisiana_topos/LA_Barataria_Venice_1971-73_24000_sheets.psb')
print('psb version',p.version,p.width,p.height,'groups',len(list(p)))
bad=0; nonnorm=0; rel=0
for g in p:
    a=[c for c in g if c.kind=='selectivecolor'][0]; d=a._record.tagged_blocks.get_data(Tag.SELECTIVE_COLOR)
    got={r:list(v) for r,v in zip(ORDER,d.data[1:])}; want=sl[g.name.replace(' ','')]
    ok=all(got[r]==list(want.get(r,[0,0,0,0])) for r in ORDER); bad+=not ok
    nonnorm+=g.blend_mode.name!='NORMAL' and g.blend_mode.name!='PASS_THROUGH'; rel+=d.method
    if not ok or g.blend_mode.name!='NORMAL': print(g.name,g.blend_mode.name,ok)
print('slider mismatch groups',bad,'| blend modes',sorted({g.blend_mode.name for g in p}),'| method values',sorted({a._record.tagged_blocks.get_data(Tag.SELECTIVE_COLOR).method for g in p for a in g if a.kind=="selectivecolor"}))
