app.displayDialogs = DialogModes.NO;
var d=app.documents.getByName('LA_Barataria_Venice_1971-73_24000_sheets.psb'); app.activeDocument=d;
var f=d.duplicate('la_flat',true);
var r='';
try {
  f.flatten();
  var o=new RawSaveOptions(); o.alphaChannels=false; o.spotColors=false;
  f.saveAs(File('/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/scripts/2_psd_and_tone/la_ps.raw'),o,true,Extension.LOWERCASE);
  r='exported '+f.width+' x '+f.height+' bits '+f.bitsPerChannel;
} finally {
  f.close(SaveOptions.DONOTSAVECHANGES);
}
r;
