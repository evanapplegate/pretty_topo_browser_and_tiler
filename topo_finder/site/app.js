// Map on the left, contact sheet on the right; each sheet owns one image on the map and one card.
// USGS serves its ZIPs only to requests coming from topoView, so thumbs fetch the public GeoTIFF and the ZIP stays one step away on topoView.
const $ = id => document.getElementById(id);
const HOME = {center: [-108, 46], zoom: 2.1};
const center = s => [(s.bbox[0] + s.bbox[2]) / 2, (s.bbox[1] + s.bbox[3]) / 2];
const topoView = s => { const [lo, la] = center(s); return `https://ngmdb.usgs.gov/topoview/viewer/#14/${la.toFixed(4)}/${lo.toFixed(4)}`; };
const links = s => `<a href="${s.tif}">TIF ${Math.round(s.mb)} MB</a> · <a href="${topoView(s)}" target="_blank" rel="noopener" title="Open on topoView, where the GeoTIFF ZIP downloads">topoView</a>`;
const fmt = (v, p, n) => `${Math.abs(v).toFixed(3)}°${v >= 0 ? p : n}`;
const box = s => { const [w, so, e, n] = s.bbox; return [[w, n], [e, n], [e, so], [w, so], [w, n]]; };
const byScan = new Map(SHEETS.map(s => [s.scan, s]));

// Public token: restrict it to this site's URL in the Mapbox account before deploying.
mapboxgl.accessToken = 'pk.eyJ1IjoiZXZhbmRhcHBsZWdhdGUiLCJhIjoiY2tmbzA1cWM1MWozeTM4cXV4eHUwMzFhdiJ9.Z5f9p8jJD_N1MQwycF2NEw';
const map = new mapboxgl.Map({container: 'map', style: 'mapbox://styles/evandapplegate/cm0o5j76w024v01o0ds82fzpr', projection: 'globe', center: HOME.center, zoom: HOME.zoom, dragRotate: false, pitchWithRotate: false});
map.addControl(new mapboxgl.NavigationControl({showCompass: false}), 'top-left');
// Keep space the page colour instead of Mapbox's default black and stars.
map.on('style.load', () => map.setFog({color: '#fefaf6', 'high-color': '#fefaf6', 'space-color': '#fefaf6', 'star-intensity': 0, 'horizon-blend': .03}));

const featureOf = s => ({type: 'Feature', id: s.scan, properties: {scan: s.scan, color: s.color}, geometry: {type: 'Polygon', coordinates: [box(s)]}});
const empty = {type: 'FeatureCollection', features: []};
const imgLayer = s => `img-${s.scan}`;
let shownOnMap = new Set(SHEETS.map(s => s.scan));

// 1/8-scale images are 2.5 MB each as textures, so only the top sheet of each quad near the view is upgraded, and sheets leaving it drop back to the small copy.
const HI_ZOOM = 7.75, HI_MAX = 60;
const hiLoaded = new Set();
// The small image stays underneath and the sharp one is a separate layer, because replacing an image in place blanks it while it loads.
const hiId = s => `hi8-${s.scan}`;
function addHi(s) {
  map.addSource(hiId(s), {type: 'image', url: `clip8/${s.scan}.jpg`, coordinates: box(s).slice(0, 4)});
  map.addLayer({id: hiId(s), type: 'raster', source: hiId(s), paint: {'raster-fade-duration': 0}}, 'cells-line');
}
function dropHi(s) { map.removeLayer(hiId(s)); map.removeSource(hiId(s)); }
function refreshHi() {
  if (!map.getLayer('cells-line')) return;
  const want = new Set();
  if (map.getZoom() >= HI_ZOOM) {
    const v = map.getBounds(), c = map.getCenter(), top = new Map();
    for (const s of SHEETS) {
      if (!s.hi || !shownOnMap.has(s.scan) || !inView(s, v)) continue;
      const k = s.bbox.join(), t = top.get(k);
      if (!t || s.dist < t.dist) top.set(k, s);
    }
    const near = s => { const [lo, la] = center(s); return (lo-c.lng)**2+(la-c.lat)**2; };
    [...top.values()].sort((a, b) => near(a)-near(b)).slice(0, HI_MAX).forEach(s => want.add(s.scan));
  }
  for (const scan of [...hiLoaded]) if (!want.has(scan)) { hiLoaded.delete(scan); dropHi(byScan.get(scan)); }
  for (const scan of want) if (!hiLoaded.has(scan)) { hiLoaded.add(scan); addHi(byScan.get(scan)); }
}
// Mapbox fills in hundreds of image layers gradually, leaving gaps, so only sheets within one screen of the view stay active.
const layerOn = new Set(SHEETS.map(s => s.scan));
function cull() {
  if (!map.getLayer('cells-line')) return;
  const v = map.getBounds(), all = map.getZoom() < 3.5, px = v.getEast()-v.getWest(), py = v.getNorth()-v.getSouth();
  for (const s of SHEETS) {
    const near = all || (s.bbox[2] >= v.getWest()-px && s.bbox[0] <= v.getEast()+px && s.bbox[3] >= v.getSouth()-py && s.bbox[1] <= v.getNorth()+py);
    const on = shownOnMap.has(s.scan) && near;
    if (on === layerOn.has(s.scan)) continue;
    map.setLayoutProperty(imgLayer(s), 'visibility', on ? 'visible' : 'none');
    if (on) layerOn.add(s.scan); else layerOn.delete(s.scan);
  }
}
let cullWait = false;
map.on('move', () => { if (cullWait) return; cullWait = true; setTimeout(() => { cullWait = false; cull(); }, 150); });
let hiTimer;
const queueHi = () => { clearTimeout(hiTimer); hiTimer = setTimeout(refreshHi, 200); };

map.on('load', () => {
  // Paint best matches last so they win where several editions share one quad.
  const beforeLabels = map.getStyle().layers.find(l => l.type === 'symbol')?.id;
  for (const s of [...SHEETS].sort((a, b) => b.dist - a.dist)) {
    map.addSource(imgLayer(s), {type: 'image', url: `clip/${s.scan}.jpg`, coordinates: box(s).slice(0, 4)});
    map.addLayer({id: imgLayer(s), type: 'raster', source: imgLayer(s), paint: {'raster-fade-duration': 0}}, beforeLabels);
  }
  map.addSource('cells', {type: 'geojson', data: {type: 'FeatureCollection', features: SHEETS.map(featureOf)}});
  // A quad is about 1.5 px wide at USA zoom, so a coloured outline carries it there and fades as the images take over.
  map.addLayer({id: 'cells-line', type: 'line', source: 'cells', paint: {'line-color': ['get', 'color'], 'line-width': ['interpolate', ['linear'], ['zoom'], 3, 3, 5, 1.5, 6, 0]}}, beforeLabels);
  map.addLayer({id: 'cells-hit', type: 'fill', source: 'cells', paint: {'fill-opacity': 0}});
  map.addSource('picked', {type: 'geojson', data: empty});
  map.addSource('hi', {type: 'geojson', data: empty});
  const hiColor = '#6E5950';
  map.addLayer({id: 'picked-line', type: 'line', source: 'picked', layout: {'line-join': 'round'}, paint: {'line-color': hiColor, 'line-width': 1.5}});
  map.addLayer({id: 'hi-box', type: 'line', source: 'hi', filter: ['==', ['get', 'k'], 'box'], layout: {'line-join': 'round'}, paint: {'line-color': hiColor, 'line-width': 3}});

  map.on('mousemove', 'cells-hit', e => {
    const s = visibleAt(e); if (!s) return;
    if (hovered === s) return;
    if (hovered) cards.get(hovered.id).classList.remove('on');
    hovered = s; highlight(s); cards.get(s.id).classList.add('on'); map.getCanvas().style.cursor = 'pointer';
  });
  map.on('mouseleave', 'cells-hit', clearHover);
  map.on('click', 'cells-hit', e => {
    const s = visibleAt(e); if (!s) return;
    new mapboxgl.Popup({closeButton: false, maxWidth: '190px'}).setLngLat(e.lngLat).setHTML(`<div class="pop"><img src="${s.thumb}" alt=""><b>${s.name}, ${s.st} ${s.yr}</b><br>1:${s.scale.toLocaleString()}<br>${links(s)}</div>`).addTo(map);
    cards.get(s.id).scrollIntoView({block: 'center', behavior: 'smooth'});
  });
  render();
});

// Where editions overlap, act on the same sheet the map is showing: the best match still passing the filters.
function visibleAt(e) {
  const hits = map.queryRenderedFeatures(e.point, {layers: ['cells-hit']}).map(f => byScan.get(f.properties.scan)).filter(s => shownOnMap.has(s.scan));
  return hits.sort((a, b) => a.dist - b.dist)[0];
}
let hovered = null;
function clearHover() {
  if (hovered) cards.get(hovered.id).classList.remove('on');
  hovered = null; map.getCanvas().style.cursor = ''; clearHighlight();
}
function highlight(s) {
  clearTimeout(clearTimer);
  if (!map.getSource('hi')) return;
  const [lo, la] = center(s);
  map.getSource('hi').setData({type: 'Feature', properties: {k: 'box'}, geometry: {type: 'LineString', coordinates: box(s)}});
  const r = $('readout'), out = inView(s, map.getBounds()) ? '' : ' · outside map view';
  r.style.display = 'block';
  r.innerHTML = `<b>${s.name}, ${s.st} ${s.yr}</b><span>${fmt(s.bbox[1], 'N', 'S')} to ${fmt(s.bbox[3], 'N', 'S')}, ${fmt(s.bbox[0], 'E', 'W')} to ${fmt(s.bbox[2], 'E', 'W')}${out}</span>`;
}
// Wait a beat before clearing, so crossing the gap between thumbs doesn't blink the outline and readout.
let clearTimer;
function clearHighlight() {
  clearTimeout(clearTimer);
  clearTimer = setTimeout(() => {
    if (!map.getSource('hi')) return;
    map.getSource('hi').setData(empty); $('readout').style.display = 'none';
  }, 120);
}

const grid = $('grid'), cards = new Map();
for (const s of SHEETS) {
  const a = document.createElement('div');
  a.className = 'card' + (s.have ? ' have' : '');
  a.innerHTML = `<a href="${s.tif}" title="${s.name}, ${s.st} ${s.yr} · 1:${s.scale.toLocaleString()} · download GeoTIFF"><img loading="lazy" src="${s.thumb}" alt="${s.name}, ${s.st} ${s.yr}"></a><div>${s.name}<br><small>${s.st} ${s.yr}</small><br><small>${links(s)}</small></div>`;
  a.addEventListener('mouseenter', () => highlight(s));
  a.addEventListener('mouseleave', clearHighlight);
  cards.set(s.id, a);
}
for (const st of [...new Set(SHEETS.map(s => s.st))].sort()) $('state').add(new Option(st, st));

// One sheet per quad: the earliest year, and the closest colour match where two editions share that year.
const firstEdition = new Set([...SHEETS.reduce((m, s) => {
  const k = s.bbox.join(), t = m.get(k);
  if (!t || s.yr < t.yr || (s.yr === t.yr && s.dist < t.dist)) m.set(k, s);
  return m;
}, new Map()).values()].map(s => s.scan));

const sorts = {
  dist: (a, b) => a.dist - b.dist,
  st: (a, b) => a.st.localeCompare(b.st) || a.dist - b.dist,
  yr: (a, b) => a.yr - b.yr || a.dist - b.dist,
  west: (a, b) => a.bbox[0] - b.bbox[0] || b.bbox[3] - a.bbox[3],
};
// Zoomed out, the globe's bounds can't describe what is showing, so test where the sheet lands on screen and keep it to the near side.
const GLOBE_ZOOM = 6, NEAR_SIDE = 80, rad = Math.PI/180;
function onNearSide(lo, la) {
  const c = map.getCenter();
  const cos = Math.sin(la*rad)*Math.sin(c.lat*rad)+Math.cos(la*rad)*Math.cos(c.lat*rad)*Math.cos((lo-c.lng)*rad);
  return Math.acos(Math.min(1, cos))/rad < NEAR_SIDE;
}
// A sheet counts as in view only with at least 8 px on screen, so neighbours merely touching the map edge stay out.
const inView = (s, v) => {
  const el = map.getContainer();
  if (map.getZoom() < GLOBE_ZOOM) {
    const [lo, la] = center(s), p = map.project([lo, la]);
    return onNearSide(lo, la) && p.x >= 0 && p.x <= el.clientWidth && p.y >= 0 && p.y <= el.clientHeight;
  }
  const mx = (v.getEast()-v.getWest())*8/el.clientWidth, my = (v.getNorth()-v.getSouth())*8/el.clientHeight;
  return s.bbox[2] >= v.getWest()+mx && s.bbox[0] <= v.getEast()-mx && s.bbox[3] >= v.getSouth()+my && s.bbox[1] <= v.getNorth()-my;
};
// Touch only the cards that changed, so thumbs already on screen don't reload or lose their scroll position.
function placeCards(nodes) {
  const want = new Set(nodes);
  for (const el of [...grid.children]) if (el !== $('empty') && !want.has(el)) el.remove();
  let at = grid.firstElementChild;
  for (const el of nodes) {
    if (el === at) at = at.nextElementSibling;
    else grid.insertBefore(el, at);
  }
}
function render() {
  const st = $('state').value, view = $('inview').checked, first = $('earliest').checked;
  const keep = s => (!st || s.st === st) && (!first || firstEdition.has(s.scan));
  const list = SHEETS.filter(keep), next = new Set(list.map(s => s.scan));
  if (map.getLayer('cells-line')) map.getSource('cells').setData({type: 'FeatureCollection', features: list.map(featureOf)});
  shownOnMap = next;
  cull();
  queueHi();
  const v = map.getBounds();
  const shown = (view ? list.filter(s => inView(s, v)) : [...list]).sort(sorts[$('sort').value]);
  placeCards(shown.map(s => cards.get(s.id)));
  $('empty').style.display = shown.length ? 'none' : 'block';
  $('count').textContent = `${shown.length} of ${SHEETS.length} sheets`;
  return list;
}
for (const id of ['sort', 'inview']) $(id).addEventListener('change', render);
$('earliest').addEventListener('change', () => { clearPick(); render(); });
$('state').addEventListener('change', () => {
  clearPick();
  const list = render();
  if ($('state').value && list.length) {
    const b = new mapboxgl.LngLatBounds();
    list.forEach(s => { b.extend([s.bbox[0], s.bbox[1]]); b.extend([s.bbox[2], s.bbox[3]]); });
    map.fitBounds(b, {padding: 40, duration: 500});
  } else if (!$('state').value) map.easeTo({...HOME, duration: 500});
});
// Box tool: drag on the map, then download the GeoTIFF URLs of every sheet touching the box as a plain list for curl.
const boxBtn = $('boxBtn'), getBtn = $('getBtn'), drag = $('drag'), band = $('band');
let picked = [], start = null;
function setBoxMode(on) {
  boxBtn.classList.toggle('on', on);
  drag.style.display = on ? 'block' : 'none';
  band.style.display = 'none';
  start = null;
}
function clearPick() {
  picked = [];
  getBtn.hidden = true;
  if (map.getSource('picked')) map.getSource('picked').setData(empty);
}
function pickBox(a, b) {
  const seen = new Set(map.queryRenderedFeatures([a, b], {layers: ['cells-hit']}).map(f => f.properties.scan));
  picked = [...seen].map(scan => byScan.get(scan)).filter(s => shownOnMap.has(s.scan));
  map.getSource('picked').setData({type: 'FeatureCollection', features: picked.map(s => featureOf(s))});
  getBtn.textContent = `${picked.length} topos selected, download .txt to curl`;
  getBtn.disabled = !picked.length;
  getBtn.hidden = false;
}
const point = e => { const r = drag.getBoundingClientRect(); return [Math.max(0, Math.min(r.width, e.clientX-r.left)), Math.max(0, Math.min(r.height, e.clientY-r.top))]; };
boxBtn.addEventListener('click', () => { const on = !boxBtn.classList.contains('on'); clearPick(); setBoxMode(on); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') setBoxMode(false); });
drag.addEventListener('pointerdown', e => {
  start = point(e);
  drag.setPointerCapture(e.pointerId);
  Object.assign(band.style, {display: 'block', left: `${start[0]}px`, top: `${start[1]}px`, width: 0, height: 0});
});
drag.addEventListener('pointermove', e => {
  if (!start) return;
  const p = point(e);
  Object.assign(band.style, {left: `${Math.min(start[0], p[0])}px`, top: `${Math.min(start[1], p[1])}px`, width: `${Math.abs(p[0]-start[0])}px`, height: `${Math.abs(p[1]-start[1])}px`});
});
drag.addEventListener('pointerup', e => {
  if (!start) return;
  const a = start, b = point(e);
  setBoxMode(false);
  if (Math.abs(a[0]-b[0]) > 3 && Math.abs(a[1]-b[1]) > 3) pickBox(a, b);
});
getBtn.addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([picked.map(s => s.tif).join('\n')+'\n'], {type: 'text/plain'}));
  const a = document.createElement('a');
  a.href = url; a.download = 'orthophoto-topos.txt'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  clearPick();
});

map.on('moveend', () => { cull(); if ($('inview').checked) render(); queueHi(); });
render();
