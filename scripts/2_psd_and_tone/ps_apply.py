# Generate a JSX that sets each group's Selective Color sliders, then exports a flat TIFF copy.
import json, sys
SL, DOC, TIF, JSX = sys.argv[1:5]
sl = json.load(open(SL))
js = """app.displayDialogs = DialogModes.NO;
var S = %s;
var DOC = %s, TIF = %s;
var C = function(s){return charIDToTypeID(s);};
var CODES = {reds:'Rds ',yellows:'Ylws',greens:'Grns',cyans:'Cyns',blues:'Bls ',magentas:'Mgnt',whites:'Whts',neutrals:'Ntrl',blacks:'Blks'};
function setSC(v){
  var d=new ActionDescriptor(), r=new ActionReference();
  r.putEnumerated(C('AdjL'),C('Ordn'),C('Trgt'));
  d.putReference(C('null'),r);
  var t=new ActionDescriptor();
  t.putEnumerated(C('Mthd'),C('CrcM'),C('Rltv'));
  var l=new ActionList();
  for(var k in CODES){
    var a=v[k]||[0,0,0,0], e=new ActionDescriptor();
    e.putEnumerated(C('Clrs'),C('Clrs'),C(CODES[k]));
    e.putUnitDouble(C('Cyn '),C('#Prc'),a[0]);
    e.putUnitDouble(C('Mgnt'),C('#Prc'),a[1]);
    e.putUnitDouble(C('Ylw '),C('#Prc'),a[2]);
    e.putUnitDouble(C('Blck'),C('#Prc'),a[3]);
    l.putObject(C('ClrC'),e);
  }
  t.putList(C('ClrC'),l);
  d.putObject(C('T   '),C('SlcC'),t);
  executeAction(C('setd'),d,DialogModes.NO);
}
var d=app.documents.getByName(DOC); app.activeDocument=d;
var n=0;
for(var i=0;i<d.layerSets.length;i++){
  var g=d.layerSets[i], key=g.name.replace(/ /g,'');
  d.activeLayer=g.layers.getByName('Selective Color');
  setSC(S[key]); n++;
}
var o=new TiffSaveOptions(); o.layers=false; o.imageCompression=TIFFEncoding.NONE; o.alphaChannels=false; o.embedColorProfile=false; o.transparency=false;
d.saveAs(File(TIF),o,true,Extension.LOWERCASE);
'set '+n+' groups';
""" % (json.dumps(sl), json.dumps(DOC), json.dumps(TIF))
open(JSX, 'w').write(js)
