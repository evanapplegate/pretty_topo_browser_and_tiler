app.displayDialogs = DialogModes.NO;
var S = {"CapeCanaveral": {"yellows": [30, 22, -15, 39], "greens": [6, 2, 7, 17], "cyans": [20, 48, -25, 47], "blues": [23, 21, -7, 27], "neutrals": [-26, -20, -29, 30], "whites": [19, 52, -28, 50]}, "Cocoa": {"yellows": [-28, -9, 14, -13], "greens": [-14, -21, 10, 20], "cyans": [3, 6, 19, -2], "blues": [6, -17, 20, -23], "neutrals": [-36, -31, -34, 42], "whites": [21, 38, 4, 38]}, "CocoaBeach": {"yellows": [6, 0, 8, 13], "greens": [3, -8, 9, 7], "cyans": [-5, 10, 5, 14], "blues": [-4, 8, 6, -2], "neutrals": [-13, -15, -1, 16], "whites": [-10, -1, 9, 11]}, "Courtenay": {"yellows": [-6, 1, -3, -5], "greens": [-3, 4, 1, 5], "cyans": [-2, -9, -1, -10], "blues": [-2, -5, -1, -5], "neutrals": [-6, -14, -14, 2], "whites": [-5, 1, -4, -5]}, "FalseCape": {"yellows": [9, -10, 8, -14], "greens": [8, -4, 9, 15], "cyans": [7, -19, 13, -19], "blues": [8, -12, 11, -13], "neutrals": [-7, -19, 2, -19], "whites": [-9, -14, 9, 8]}, "Orsino": {"yellows": [-19, 19, -4, 0], "greens": [-13, 29, -7, 19], "cyans": [-10, -9, -2, -22], "blues": [-2, 1, -5, -6], "neutrals": [-20, 13, -13, 18], "whites": [-9, 8, -7, -9]}};
var DOC = "FL_CapeCanaveral_1976_24000_sheets.psd", TIF = "/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/scripts/2_psd_and_tone/fl_ps.tif";
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
var o=new TiffSaveOptions(); o.layers=false; o.imageCompression=TIFFEncoding.NONE; o.alphaChannels=false; o.embedColorProfile=false;
d.saveAs(File(TIF),o,true,Extension.LOWERCASE);
'set '+n+' groups';
