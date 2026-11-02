app.displayDialogs = DialogModes.NO;
function openReport(path){
  var t=new Date().getTime();
  var d=app.open(File(path));
  var o=[d.name+' '+d.width.as('px')+'x'+d.height.as('px')+' res '+d.resolution+' mode '+d.mode+' bits '+d.bitsPerChannel+' sets '+d.layerSets.length+' open_s '+((new Date().getTime()-t)/1000)];
  for(var i=0;i<d.layerSets.length;i++){
    var s=d.layerSets[i], k=[];
    for(var j=0;j<s.layers.length;j++){var l=s.layers[j]; k.push(l.name+':'+l.kind);}
    var b=s.layers[s.layers.length-1].bounds;
    o.push(s.name+' | '+s.blendMode+' | '+k.join(', ')+' | '+b[0].as('px')+','+b[1].as('px')+' '+b[2].as('px')+','+b[3].as('px'));
  }
  return o.join('\n');
}
openReport("/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/nw_fl_topos/FL_Bruce_IndianPass_1982_24000_sheets.psb");
