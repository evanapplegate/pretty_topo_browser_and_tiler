import sys
from psd_tools import PSDImage
from psd_tools.constants import Tag
p=PSDImage.open(sys.argv[1])
g=list(p)[0]; a=[c for c in g if c.kind=='selectivecolor'][0]; r=a._record
d=r.tagged_blocks.get_data(Tag.SELECTIVE_COLOR)
sec=g._record.tagged_blocks.get_data(Tag.SECTION_DIVIDER_SETTING)
f=r.flags; print('selc version',d.version,'method',d.method,'records',len(d.data),'all zero',all(v==0 for rec in d.data for v in rec),'adj flags',f.photoshop_v5_later,f.pixel_data_irrelevant,'mask',a.has_mask(),a.mask.background_color if a.has_mask() else None,'channels',[int(c.id) for c in r.channel_info])
print('group lsct',sec.kind.name,sec.blend_mode.name,'record blend',g._record.blend_mode.name,'layer ids unique',len({l._record.tagged_blocks.get_data(Tag.LAYER_ID) for l in p.descendants()})==len(list(p.descendants())))
print('resolution res',p.image_resources.get_data(1005).horizontal if p.image_resources.get_data(1005) else None,'version info',p.image_resources.get_data(1057).has_composite)
