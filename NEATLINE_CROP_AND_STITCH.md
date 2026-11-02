# Neatline cropping and stitching USGS topos

How the Cape Canaveral, Louisiana, NW Florida and St Marys GeoTIFFs were clipped at their printed neatlines, joined into seamless mosaics and color matched, and how the same tone mapping was run across the site's map images.

The scripts are in [scripts/](scripts/README.md), with the run order.

- **Method:** the steps from raw sheet to mosaic, starting at [Why a plain clip doesn't work](#why-a-plain-clip-doesnt-work).
- **[St Marys block](#st-marys-block-stitch-and-tone-match):** a full log of the 9-sheet stitch and tone match, including what failed.
- **[Cape Canaveral tone match](#cape-canaveral-tone-match):** the same method on a water-heavy block, and what had to change.
- **[Site images](#site-images-cluster-matching):** the same tone mapping across 880 map images, one connected cluster at a time.
- **[Learnings](#learnings):** what carries over to the next block.
- **[Earlier color matching](#earlier-color-matching):** the Selective Color work on the first three sets.
- **[Appendix](#appendix-scripts):** the St Marys, Canaveral and site-image scripts in full.

The short version: don't clip to the coordinates the metadata gives you. Measure where the neatline was actually printed on each scan, warp each sheet so that line lands exactly on the quad edge, and resample every sheet onto one shared grid so seams fall on pixel boundaries.

## Why a plain clip doesn't work

Clipping each sheet to its nominal 7.5' bounds leaves slivers of collar or a dark neatline along the seams, for three reasons:

- **Paper and scanning:** the printed neatline is not perfectly straight or square in the scan. It wanders by a few pixels along each edge.
- **Georeferencing:** a sheet's georeferencing isn't exact. The neatline sat up to about 5 px from its nominal position here.
- **Different projections:** every sheet has its own Transverse Mercator or Polyconic projection centered on that quad, so sheets don't share a pixel grid.

Measuring the line itself solves the first two. A shared output grid solves the third.

## Inputs

USGS Historical Topographic Map Collection GeoTIFFs, each with `.tfw`, `.prj` and FGDC `.xml` sidecars.

| | |
|---|---|
| Scale and format | 1:24,000 7.5' quads, 300 ppi, 2.032 m per pixel |
| Datum | NAD27 |
| Projection | Per-sheet TM (Florida) or Polyconic (Louisiana), central meridian at the quad center |
| Quad bounds | `westbc`, `eastbc`, `northbc`, `southbc` in the FGDC XML |

| Set | Sheets | Output px per quad | Grid |
|---|---|---|---|
| Cape Canaveral | 6 | 6036 × 6816 | 2 × 3 |
| Louisiana | 19 | 5980 × 6820 | 8 × 4 |
| NW Florida | 32 | 5932 × 6820 | 7 × 7 |
| St Marys | 9 | 5886 × 6820 | 3 × 3 |

Output width changes with latitude because 0.125° of longitude shrinks going north. Each size is about the sheet's real width in source pixels, so the data is neither stretched nor thrown away.

## Step 1: Locate the nominal edge

For each edge, sample points along the quad boundary in lat/lon, transform them from EPSG:4267 into the sheet's CRS, then through the inverse geotransform to pixels.

```python
t = Transformer.from_crs('EPSG:4267', d.crs, always_xy=True)
inv = ~d.transform
X, Y = t.transform(lon, lat)
px, py = inv * (X, Y)
```

Samples are spaced about every 20 px, 345 per edge.

## Step 2: Measure the printed neatline

At each sample, take a brightness profile across the edge:

- **Profile:** 45 px long, 22 px either side of nominal, averaged over 9 px along the edge to reduce noise.
- **Collar check:** the 8 outermost pixels must be bright paper, median at least 195 and minimum at least 170. Otherwise the sample is skipped, which rejects text, grid ticks and map data running into the margin.
- **Find the stroke:** walk inward to the first drop of 60 levels below the paper, then find the darkest pixel within the next 7. It must be 110 or darker.
- **Outer edge:** the sub-pixel position where brightness crosses halfway between paper and stroke.
- **Inner edge:** the same crossing on the map side, only where the map is at least 70 levels brighter than the stroke. Dark map content gives no usable inner edge.

Each edge then gets a smooth curve, a 5th-degree polynomial of offset against position, fitted with 6 rounds of 2.5-sigma outlier rejection:

```python
keep = ok.copy()
for _ in range(6):
    c = np.polyfit(s[keep], outer[keep], 5)
    r = outer - np.polyval(c, s)
    sd = max(np.nanstd(r[keep]), 0.15)
    keep = ok & (np.abs(r) < 2.5 * sd)
```

The fitted curve is the line's position even where individual samples failed, such as where map color runs up to the edge.

| Set | Median fit error | Worst edge | Stroke width | Offset from nominal |
|---|---|---|---|---|
| Cape Canaveral | 0.17 px | 0.42 px | 1.8-2.2 px | -3.7 to +2.2 px |
| Louisiana | 0.15 px | 0.33 px | 2.2-2.7 px | -3.6 to +1.4 px |
| NW Florida | 0.16 px | 1.17 px | 1.5-2.3 px | -4.7 to +2.5 px |

Before clipping, check a corner crop of every sheet with the nominal corner marked. The metadata's bounds are for the map cell, and it's worth confirming they really are the neatline corners.

## Step 3: Warp each sheet to its quad

For each output pixel, work out which source pixel to read. Start from the plain georeferenced position, then add a displacement that moves the *inner* side of the printed line onto the quad edge.

For an edge, the inset is:

```
inset(s) = fitted outer offset + stroke width + 1.5 px margin
```

The stroke width is the sheet's median across its four edges. The 1.5 px margin steps safely past the line, so no dark pixels survive at the seam.

The insets blend across the sheet, with `u` and `v` running 0 to 1 from the northwest corner:

```
dx = (1 - u) * W(v) - u * E(v)
dy = (1 - v) * N(u) - v * S(u)
```

So each edge moves exactly as far as its own line requires, and the correction fades to nothing at the opposite edge. The middle of the sheet barely moves.

In practice this is computed on a 129 × 129 grid of control points, then interpolated up to full resolution:

```python
U, V = np.meshgrid(uc, vc)                       # 0 to 1, 129 points
X, Y = t.transform(W + (E-W)*U, N + (S-N)*V)
px, py = inv * (X, Y)
px = px + (1-U)*inset('W', V) - U*inset('E', V) - 0.5
py = py + (1-V)*inset('N', U) - V*inset('S', U) - 0.5
mx = RectBivariateSpline(vc, uc, px)(vi, ui)     # full-res source x
my = RectBivariateSpline(vc, uc, py)(vi, ui)     # full-res source y
out = cv2.remap(src, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
```

The 0.5 converts from pixel corners to the pixel centers `remap` expects.

## Step 4: Write onto a shared grid

Every sheet is written in EPSG:4267 with the same pixel size, aligned to the quad corner:

```python
tr = Affine((E-W)/COLS, 0, W, 0, (S-N)/ROWS, N)
```

Because each quad is a whole number of pixels on one lat/lon grid, neighbors meet exactly on a pixel boundary with no overlap, no gap and no resampling at the seam. Pixels aren't square in degrees, which is fine: they're close to square on the ground.

Each sheet is written twice:

- **Lossless (DEFLATE, predictor 2):** for building the mosaic, so it isn't JPEG-compressed twice.
- **JPEG quality 92:** for the delivered `clipped/` folder.

## Step 5: Mosaic

```bash
gdalbuildvrt -q -addalpha mosaic.vrt work/*.tif
gdal_translate -q -of COG -co COMPRESS=JPEG -co QUALITY=92 -co BLOCKSIZE=512 \
  -co OVERVIEW_RESAMPLING=AVERAGE -co NUM_THREADS=ALL_CPUS -co BIGTIFF=IF_SAFER \
  mosaic.vrt mosaic.tif
```

`-addalpha` matters when the grid has holes, as Louisiana and NW Florida do: empty cells become a mask rather than solid black. The mosaic is a Cloud-Optimized GeoTIFF, so it opens quickly at any zoom.

## Step 6: Check the seams

Automatic checks on the finished mosaic:

- **Mask:** filled cells match the mask exactly, with no masked pixels inside a sheet.
- **Leftover neatline:** compare each seam's brightness with both sides. The worst was 3.7 levels out of 255, across all 50 NW Florida seams, so no line survives.
- **Registration:** cross-correlate a thin strip either side of each seam, in blocks, to measure how far features are offset along it.

| Set | Typical offset | Worst measured |
|---|---|---|
| Cape Canaveral | not summarized | about 7 px |
| Louisiana | mostly within 5 px | 12 px (24 m) |
| NW Florida | 2 px median, 7 px at the 90th percentile | 11 px (22 m) |
| St Marys | 2 px median, 10 px at the 90th percentile | 13 px (26 m) |

These offsets are in the original printing and scanning: adjacent sheets were not always drawn to match perfectly. Fixing them would mean rubber-sheeting map content across seams, which wasn't done. Sample counts are small on featureless water, so treat the worst-case figures as sparse.

## Limits

- **Resampled once:** every pixel passes through one cubic interpolation.
- **JPEG twice:** sources are JPEG, and delivered files are JPEG again at quality 92.
- **Margins lost:** about 3.5 px, or 7 m, is lost per sheet edge: the 2 px stroke plus the 1.5 px margin.
- **Colors unchanged:** this step doesn't touch tone. Sheet-to-sheet color was handled separately: see [Earlier color matching](#earlier-color-matching) and the [St Marys block](#st-marys-block-stitch-and-tone-match).
- **Neighbors aren't aligned:** each sheet is fitted to its own quad edges, not to its neighbors.

## The website's versions

The Orthophoto-topos site uses a lighter method for its 880 sheets, because it can't afford to read every full scan:

1. Read only the header of each remote GeoTIFF to get its size and georeferencing.
2. Compute where the quad's four corners fall in the image.
3. Warp those four corners to a rectangle with a perspective transform, pulled in slightly so collar can't bleed in: 1.5% for the thumbnails, 0.3% for the 1/8 images.

| Version | Source | Size |
|---|---|---|
| Small | USGS `_tn.jpg` thumbnail | 170 × 195 px |
| Sharp | The GeoTIFF's 1/8 overview | 740 × 850 px |

This relies on the georeferencing alone, with no neatline measurement. That's accurate enough here: the 5 px error at full resolution is under 1 px at 1/8.

These images were later color matched. See [Site images](#site-images-cluster-matching).

## St Marys block: stitch and tone match

A full log of the last and most demanding job: nine sheets around St Marys on the Georgia-Florida line, picked with the box tool on the Orthophoto-topos site, stitched to a BigTIFF and color matched by tone mapping rather than Selective Color sliders.

The brief was a neatline stitch to `BIGTIFF=YES` and real color matching, where the seams and the overall look both had to hold up.

### Result

| File | Size | Notes |
|---|---|---|
| `st_marys_topos/GA_Woodbine_Fernandina_1979-81_24000_mosaic_matched.tif` | 1.03 GB | The deliverable: color matched, lossless DEFLATE, BigTIFF, COG |
| `st_marys_topos/GA_Woodbine_Fernandina_1979-81_24000_mosaic.tif` | 1.01 GB | Raw neatline stitch on the same grid |
| `st_marys_topos/before_after.png` | 6.6 MB | Side by side from the two files above |
| `st_marys_topos/src/` | 120 MB | The 9 source GeoTIFFs |
| `st_marys_topos/lossless/` | 805 MB | Lossless clips, used as color input |
| `st_marys_topos/clipped/` | 154 MB | JPEG quality 92 clips |
| `st_marys_topos/matched/` | 836 MB | Lossless color-matched clips |

Both mosaics are 17,658 × 20,460 px, 3-band 8-bit, EPSG:4267, covering 81.75° to 81.375° W and 30.625° to 31.0° N.

### The sheets

The list came from `orthophoto-topos (2).txt`, nine URLs forming a complete 3 × 3 block with no gaps. Sheets were downloaded one at a time with `curl`, 125 MB in all.

| Row | West | Middle | East |
|---|---|---|---|
| North | Woodbine, GA 1979 | Kingsland NE, GA 1979 | Cumberland Island North, GA 1979 |
| Middle | Kingsland, GA 1980 | Harrietts Bluff, GA 1980 | Cumberland Island South, GA 1979 |
| South | Gross, FL 1979 | St Marys, GA 1979 | Fernandina Beach, FL 1981 |

The raw problem was severe: dark north row, saturated middle row, and a yellow Gross sheet in the southwest, with hard rectangular steps at every seam.

### Stitch

This follows steps 1 to 5 above with three changes:

- **Bounds:** bare `.tif` downloads from S3 have no FGDC XML, so quad bounds came from the TNM API record, saved in `sheets.json`. Georeferencing came from the GeoTIFF's own tags.
- **Grid size:** the nominal quad measured 5875 to 5898 px wide and 6820 px tall, so the shared size is 5886 × 6820.
- **Mosaic:** lossless DEFLATE with `BIGTIFF=YES` rather than JPEG quality 92, so nothing is compressed twice on the way to color work.

| Sheet | Worst edge fit error | Stroke | Offset from nominal |
|---|---|---|---|
| Woodbine | 0.17 px | 1.96 px | -3.3 to +1.2 px |
| Kingsland NE | 0.48 px | 2.41 px | -2.3 to +0.6 px |
| Cumberland Island North | 0.37 px | 2.07 px | -2.6 to +1.0 px |
| Kingsland | 0.42 px | 2.46 px | -2.6 to +1.9 px |
| Harrietts Bluff | 0.26 px | 2.37 px | -1.9 to +0.2 px |
| Cumberland Island South | 0.33 px | 1.97 px | -2.4 to +0.4 px |
| Gross | 0.21 px | 2.00 px | -3.0 to +0.4 px |
| St Marys | 0.22 px | 1.98 px | -2.9 to +0.5 px |
| Fernandina Beach | 0.15 px | 1.84 px | -2.8 to +1.5 px |

Seam QA on the raw mosaic: all 12 seams, worst leftover darkening 4.7 levels out of 255, so no neatline survives. Features along seams are offset by 2 px at the median, 10 px at the 90th percentile and 13 px (26 m) at worst, from only 31 measurable blocks. Those offsets are in the printing and were left alone.

### How the color match works

All color work happens in OKLab, a perceptual color space, at quarter resolution (1471 × 1705 px per sheet). Full resolution comes last. Color differences below are OKLab distance × 100, which is not the same scale as the CIELAB ΔE quoted for the earlier sets.

**1. Global tone map, solved jointly.** Each sheet gets a 13-term cubic polynomial mapping from (L, a, b) to (L, a, b). All nine are solved together so that mirrored pixels across every seam agree:

- **Pairs:** blurred at sigma 4, sampled every 3 px, at depths 4, 10, 18 and 30 px from the seam.
- **Robustness:** 8 rounds of reweighting, with a Huber-style weight floored at 0.012, so labels and line work don't steer the fit.
- **Regularization:** a pull toward the identity (0.005), plus pins at black and paper white so tones stay anchored.

This handles each sheet's overall tone and printing color, but it can't fix drift within a sheet.

**2. Class-aware local tone mapping.** Each pixel is sorted into forest, clearing, marsh or water by color. For each class, a large Gaussian measures how far the local average sits from that class's median across the mosaic, and a correction moves it part of the way back.

| Class | Rule | Strength | Share of map |
|---|---|---|---|
| Forest | Green, b ≥ 0.045, L < 0.62 | 0.8 | 47% |
| Clearing | Green, b ≥ 0.045, L ≥ 0.62 | 0.6 | 24% |
| Marsh | Green, -0.002 ≤ b < 0.045, L < 0.74 | 0.7 | 4% |
| Water | L ≥ 0.72, b < 0.03, a < 0.012 | 0.4 | 22% |

Shares are from the raw image under an earlier form of the water rule.

Passes run at sigma 260, 180 and 120 quarter-pixels (about 2.1, 1.5 and 1.0 km), then 90 (about 730 m) at half strength. Classes are recomputed on each pass from the current estimate, because raw colors differ too much by sheet to classify reliably. Pale pixels stay pinned to water using the raw image.

**3. Tone-aware seam solver.** This is the step that removed the seams. Each sheet gets a smooth color field over three dimensions: position y, position x and tone. Tone nodes sit at L = 0.22, 0.38, 0.52, 0.66, 0.80, 0.92 and 1.0, and position nodes every 24 quarter-pixels (about 195 m). Water and forest can then get different corrections at the same spot, which a plain offset can't do. The idea is a bilateral grid.

- **Evidence:** at each seam position and tone, a robust average of the color difference across the seam, using pairs at depths 2, 4, 7, 11 and 16 px within a 30 px Gaussian window along the seam.
- **Which pairs count:** only pairs that look like the same material. Limits are |ΔL| < 0.09 and |Δab| < 0.05, tightening to 0.035 and 0.02 between L 0.70 and 0.85.
- **Solve:** one sparse linear system couples all nine sheets, with spatial smoothness 1, tone smoothness 0.6 and seam weight 30, each side taking half the correction. A small pull to zero (0.003, or 0.06 for the top three tones) keeps the field from wandering where there's no evidence.

The solver runs 3 rounds after the first evening passes and 4 more after the last one.

**4. Saturation trim.** Matching adds some saturation, so a and b are scaled by 0.965.

**5. Full-resolution render.** Each sheet's color change at quarter scale is turned into a local affine map (a guided filter on the color change, 13 × 13 window, regularization 2e-4), upsampled and applied to the original full-resolution pixels. Fine detail therefore comes from the source, not from an upscaled image. Each sheet is done separately, so no window crosses a seam.

**6. Ink guard.** Printed inks aren't land, so they're protected at full resolution:

- **Warm inks** (sand, roads, town tint): a and b return to the original values.
- **Thin blue lines:** found by being bluer than their surroundings, then given the original color plus the local background shift, so flat ocean tints stay matched.

**7. Gamut map and write.** Out-of-gamut colors have chroma reduced by binary search, holding lightness and hue, instead of clipping channels. Output is 8-bit lossless DEFLATE, built into a COG with `BIGTIFF=YES`.

### Metrics

- **Seam visibility:** the median color step on the real seam divided by the same measure on control lines 24 quarter-pixels inside each sheet. 1.0 means the seam is no stronger than ordinary map content.
- **Seam median and p90:** the plain color step across each seam. This counts real features, so it can't reach zero. Fake seams through sheet centers read 3.4 median and 8.7 p90.
- **Land and water spread:** how far each sheet's class average sits from the average of all sheets.
- **Chroma:** matched saturation relative to raw.
- **Band profile:** forest lightness against distance from the seam, to catch a band along it.
- **Exaggerated view:** low-frequency color within each class at 3.5× contrast, side by side with raw. Numbers don't show sheet-shaped patches; this does.

### Iteration log

Numbers are as printed at the time.

| Run | Change | Seam median | Seam p90 | Land | Water | Chroma | Finding |
|---|---|---|---|---|---|---|---|
| Raw | Neatline stitch only | 11.78 | 21.02 | 4.34 | 2.18 | 1.000 | Hard blocks everywhere |
| 1a | Global quadratic | 9.48 | 18.60 | 2.75 | 2.49 | 1.002 | Tone improved, steps remain |
| 1b | Plus one smooth offset per sheet | 4.53 | 11.13 | 2.92 | 2.66 | 1.003 | Seams mostly gone, yellow southwest remains |
| 2 | Cubic, class-aware evening | 4.45 | 10.74 | 1.84 | 2.04 | 1.028 | Class map read the yellow Gross sheet as all clearing |
| 3 | Reclassify each pass, 3 scales | 4.44 | 10.85 | 2.12 | 1.82 | 1.050 | Even overview, but close up, water steps where forest matches |
| 4 | Tone-aware seam solver, 3 rounds | 3.76 | 12.55 | 2.05 | 1.90 | 1.051 | Crops look continuous; p90 is now real features, so the metric stopped being useful |

Run 5 added seam visibility and swept the solver settings. Raw scored 2.70, worst seam 6.98.

| Setting | Visibility | Worst | Land | Water |
|---|---|---|---|---|
| A: along 45, node 30, 3 rounds | 0.94 | 1.25 | 2.05 | 1.90 |
| B: along 30, node 24 | 0.90 | 1.18 | 1.93 | 1.89 |
| C: along 20, node 20 | 0.86 | 1.11 | 1.86 | 1.88 |
| D: seam weight 80 | 0.94 | 1.24 | 2.06 | 1.89 |
| E: 5 rounds | 0.89 | 1.12 | 2.09 | 1.86 |
| F: softer evening | 0.94 | 1.22 | 2.24 | 2.07 |
| G: tone smoothness 0.25 | 0.94 | 1.25 | 2.04 | 1.89 |

Tighter windows and more rounds helped; seam weight and tone smoothness didn't. Setting C wasn't chosen because very tight fields risk chasing real content. Along 30, node 24 with more rounds reached a similar worst seam in run 6.

| Run | Change | Visibility | Worst | Land | Water | Chroma | Finding |
|---|---|---|---|---|---|---|---|
| 6 | Along 30, node 24, 5 rounds | 0.86 | 1.09 | 1.96 | 1.86 | 1.051 | Exaggerated view: blocks gone, faint dark band along the first east-west seam |
| 7 | Alternate evening and seams, adds sigma 90 and 60 | 0.83 | 1.02 | 1.68 | 1.50 | 1.075 | Best numbers, worse picture: too green and flat, tan sandbars went olive |
| 8 | Drop sigma 60, protect warm inks, trim chroma | 0.84 | 1.03 | 1.82 | 1.71 | 1.022 | Looked right in overview |

Run 7 is why a lower number wasn't the goal: sigma 60 is about 490 m, small enough to erase real landscape.

### Defects found at native pixels

The first full render passed every number. Crops at 1:1, raw above matched, showed two problems invisible in overviews.

**Pink tidal flats.** Pale flats near the Harrietts Bluff seam turned cream-pink, from (L 0.951, a -0.041, b +0.012) to (0.904, -0.019, +0.046).

- **First theory, partly right:** classification feedback, where flats drifted yellow and were pulled toward clearing. Pale pixels were pinned to water, but the patch barely moved, to (0.915, -0.014, +0.038).
- **Real cause, found by tracing the patch through each stage:** it stayed stable through the global and evening steps, then drifted a little on every seam solver round. Near white, unrelated materials look alike, so the solver paired flats with near-whites and treated the content difference as a color offset. Each round compounded it.
- **Fix:** tighter pair limits at high tones and a stronger pull to zero on the top tone nodes. Result: (0.928, -0.032, +0.019), with seam visibility unchanged at 0.86.

**Grey blue contours.** Thin blue depth lines were taking the correction meant for land of the same brightness. In the worst patch, ink went from (0.735, -0.074, -0.045) to (0.737, -0.055, -0.039). The quarter-scale warm guard couldn't see lines that thin, so the guard moved to full resolution, then to detecting lines against their surroundings.

| Render | Change | File visibility | Worst | Blue chroma kept, worst patch |
|---|---|---|---|---|
| 1 | Run 8 candidate | 0.85 | 1.08 | about 78% |
| 2 | Flats fixed, full-resolution ink guard | 0.86 | 1.09 | 83% |
| 3 (delivered) | Line detection for blue ink | 0.86 | 1.09 | 80% |

Render 3 didn't help this patch. Its lines keep their original color but pick up the shift of the water around them, and in a patch this small that shift works against them. It's the delivered version, and the defect is still open. The render 1 figure is worked out from the sampled values above.

### Final verification

Every check reads the delivered BigTIFFs, not working copies (`verify.py`, `seamqa.py`).

| Check | Raw | Matched |
|---|---|---|
| File header | `II+` (BigTIFF) | `II+` (BigTIFF) |
| Layout, compression | COG, DEFLATE | COG, DEFLATE |
| Grid | | Identical to raw |
| Mask | | All pixels valid |
| Overviews | | 2, 4, 8, 16, 32, 64 |
| Seam visibility | 2.69 | 0.86 |
| Worst seam | 6.93 | 1.09 |
| Seam step against control | 11.86 / 4.73 | 3.86 / 4.57 |
| Land spread | 4.34 | 1.65 |
| Water spread | 2.18 | 1.99 |
| Chroma | 1.000 | 1.006 |
| Pixels at the edge of the sRGB gamut | 0.04% | 0.38% |

| Other | Result |
|---|---|
| Fine detail kept at native pixels | 97% median, 94% to 102% across sheets |
| Full-resolution render vs quarter-scale target | 0.12 to 0.34 median |
| Render time | About 10 seconds per sheet, 3 at a time |

Band profile, forest lightness × 100 relative to sheet interiors, by distance from a seam in quarter-pixels:

| Distance | 0-15 | 15-40 | 40-80 | 80-140 | 140-220 |
|---|---|---|---|---|---|
| Raw | -2.20 | -2.22 | -1.94 | -1.63 | -0.49 |
| Matched | -0.56 | -0.93 | -0.70 | -0.44 | +0.07 |

Those figures come from the last candidate build, before the final render.

### Known limits

- **Blue contours:** about 80% of original saturation in the worst patch. Fine at normal zoom, slightly dull up close.
- **Line offsets:** rivers and contours can step up to 13 px at a seam. That's the printing, and color can't fix it.
- **Faint band:** forests read up to about 0.9 lightness units darker near seams, down from 2.2. Visible only under exaggeration.
- **Water spread:** barely improved, 2.18 to 1.99. Run 7 reached 1.50, but only with the flattening that was rejected.
- **Detail:** the matched image keeps a median 97% of local contrast, because bringing mismatched sheets together compresses some of it.
- **Different dates:** sheets span 1979 to 1981. Tones are matched, not the landscape or the tide.
- **Masks are color-based:** the class map uses fixed thresholds tuned on this block, so another block would need them rechecked.
- **Not a full rerun:** the delivered file came from the last `run9.py` output and `render.py`, and the chain hasn't been rerun from scratch. Since then, `tone.py` has gained the optional `select`, `limits` and `weight` arguments and `water_pass` for Canaveral, and `band_profile` now handles incomplete grids. None of those change the St Marys path, whose defaults are unchanged, and `run9.py` changed only in its preview call.
- **Earlier runs:** `run1.py` to `run8.py`, `diag.py` and `diag2.py` were written against earlier states of `tone.py` and may not reproduce the table above.
- **Dead code:** `tone.py` keeps superseded functions for those runs, such as `fit_field`, `pipeline`, `stack` and `finish`.

### Commands

From `~/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos`, with `R=~/Dropbox/freelance/pretty_topo_browser_and_tiler/scripts/4_st_marys` and `G=/Applications/QGIS.app/Contents/MacOS`. `PROJ_DATA` and `GDAL_DATA` must be set as in the [scripts README](scripts/README.md).

Download, one at a time:

```bash
cd src
while IFS= read -r u; do
  f=$(python3 -c "import sys,urllib.parse;print(urllib.parse.unquote(sys.argv[1].rsplit('/',1)[1]))" "$u")
  curl -sS --fail --retry 3 -C - -o "$f" "$u"
done < "../../orthophoto-topos (2).txt"
cd ..
```

Measure, clip and stitch:

```bash
python3 $R/measure.py $R/neatline.json
python3 $R/clip.py $R/neatline.json lossless 1.5 deflate 5886 6820
python3 $R/clip.py $R/neatline.json clipped 1.5 jpeg 5886 6820
$G/gdalbuildvrt -q lossless/mosaic.vrt lossless/*.tif
$G/gdal_translate -q -of COG -co BIGTIFF=YES -co COMPRESS=DEFLATE -co PREDICTOR=YES -co LEVEL=6 \
  -co BLOCKSIZE=512 -co OVERVIEW_RESAMPLING=AVERAGE -co NUM_THREADS=ALL_CPUS \
  lossless/mosaic.vrt GA_Woodbine_Fernandina_1979-81_24000_mosaic.tif
```

Color match, from inside `$R` because `work/` and `qa/` are relative:

```bash
cd $R
python3 -W ignore run9.py
python3 -W ignore render.py
```

Build the matched BigTIFF, then verify:

```bash
T=~/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos
$G/gdalbuildvrt -q $T/matched/mosaic.vrt $T/matched/*.tif
$G/gdal_translate -q -of COG -co BIGTIFF=YES -co COMPRESS=DEFLATE -co PREDICTOR=YES -co LEVEL=6 \
  -co BLOCKSIZE=512 -co OVERVIEW_RESAMPLING=AVERAGE -co NUM_THREADS=ALL_CPUS \
  $T/matched/mosaic.vrt $T/GA_Woodbine_Fernandina_1979-81_24000_mosaic_matched.tif
python3 -W ignore verify.py
python3 -W ignore seamqa.py
```

`render.py` reads `work/final_q.npz`, which `run9.py` writes.

## Cape Canaveral tone match

The 6 Cape Canaveral sheets were redone with the St Marys tone mapping, to test how well it carries to a different kind of block.

| File | Size | Notes |
|---|---|---|
| `canaveral_topos/FL_CapeCanaveral_1976_24000_mosaic_tonemapped.tif` | 672 MB | The deliverable: lossless DEFLATE, BigTIFF, COG |
| `canaveral_topos/FL_CapeCanaveral_1976_24000_mosaic_lossless.tif` | 662 MB | Raw neatline stitch on the same grid |
| `canaveral_topos/before_after.png` | | Side by side from those two files |
| `canaveral_topos/lossless/` | | Lossless clips, used as color input |
| `canaveral_topos/matched/` | | Lossless color-matched clips |

Both mosaics are 12,072 × 20,448 px, 3-band 8-bit, EPSG:4267, covering 80.75° to 80.5° W and 28.25° to 28.625° N. The earlier `FL_CapeCanaveral_1976_24000_mosaic_matched.tif` was left alone.

### How this block differs

- **Input:** the source sheets are gone, so this starts from the clips. `clipped/` holds JPEG versions, but the lossless originals had survived in a temp folder. Same grid, and they differ from the JPEGs by 2.0 to 2.5 levels of compression noise, so the lossless ones were used and saved to `canaveral_topos/lossless/`.
- **Mostly water:** about 58% of the block by the class map, and strongly blue (b around -0.03 to -0.09) rather than pale.
- **Seams run through water:** the Banana River and the ocean cross most of them.
- **Worse to start:** seam visibility 4.54 raw, against 2.69 for St Marys. Water makes seams stand out, because there's so little content to hide them.

### Runs

**Run 1, St Marys settings unchanged.** Seam visibility fell to 1.03, worst seam 1.23. The overview was strong, but seam crops showed a dark rectangle of water at the Courtenay corner in the Banana River, with hard edges. Smaller versions showed at the Cocoa Beach marsh and the Crawlerway canal.

The cause was the St Marys flats fix. It rejects bright pairs that disagree by more than 0.035 in lightness or 0.02 in color, to stop near-white materials being confused. Here that test threw out the real water differences, and the leash on the top tone nodes held back what was left. So the solver simply ignored those seams.

**Run 2, plus a water-only seam pass.** `water_pass` in `tone.py` adds 3 rounds on top of run 1:

- **Pairs:** cool pixels only (b < -0.004 on both sides), with limits loosened to |ΔL| < 0.16 and |Δab| < 0.09.
- **Leash:** the highlight leash drops to 0.003.
- **Applied through a soft mask:** weight rises from b = 0 to b = -0.018, so land keeps its own correction.

| Run | Visibility | Worst | Seam p90 | Courtenay / Cape Canaveral p90 | Land | Water |
|---|---|---|---|---|---|---|
| Raw | 4.54 | 11.42 | 15.27 | | 3.88 | 3.17 |
| 1 | 1.03 | 1.23 | 8.33 | 13.7 | 1.20 | 1.01 |
| 2 round 1 | 0.95 | 1.25 | 5.94 | | 1.20 | 1.00 |
| 2 round 2 | 0.92 | 1.21 | 5.85 | | 1.20 | 1.04 |
| 2 round 3 | 0.91 | 1.19 | 5.79 | 2.2 | 1.20 | 1.08 |

Each round cost a little water spread, so it stopped at 3.

### Final verification

Read from the delivered BigTIFFs by `5_canaveral/verify.py`. The Selective Color column is the older `..._mosaic_matched.tif`, scored the same way.

| Check | Raw | Selective Color | Tone mapped |
|---|---|---|---|
| Seam visibility | 4.54 | 3.58 | 0.91 |
| Worst seam | 11.45 | 5.82 | 1.21 |
| Land spread | 3.88 | 0.67 | 1.24 |
| Water spread | 3.16 | 0.49 | 1.07 |
| Chroma | 1.000 | 0.969 | 0.997 |
| Quarter-scale detail | 1.000 | 0.988 | 0.953 |

| Other | Result |
|---|---|
| File header | `II+` (BigTIFF), COG, DEFLATE, overviews 2 to 64 |
| Grid | Identical to the raw stitch |
| Seam step against control | 8.33 / 2.63 raw, 2.15 / 2.62 matched |
| Fine detail kept at native pixels | 98% median, 93% to 100% across sheets |
| Full-resolution render vs quarter-scale target | 0.10 to 0.22 median |
| Pixels at the edge of the sRGB gamut | 0.20% |
| Render time | 11 to 15 seconds per sheet, 3 at a time |

Native-pixel crops at seam junctions show no color step, and blue contours held their color here.

### Known limits

- **Print texture:** Courtenay's water has a coarser grain than its neighbors. Tone matched, grain didn't.
- **Worst seam:** Orsino / False Cape at 1.21. Most of what's left is line offsets and real features.
- **Sheet averages:** further apart than the Selective Color version. See the first learning below.
- **Thresholds:** the class rules weren't retuned. Deep water off False Cape falls into "other" and gets a blended correction, which worked here.
- **Not rerun end to end** after the water pass moved into `tone.py`, except `run2.py`, which reproduced its output exactly (max difference 0.0). The render and BigTIFFs came from that same data.

### Commands

From `scripts/5_canaveral/`, with the lossless clips in `canaveral_topos/lossless/`:

```bash
python3 -W ignore run1.py
python3 -W ignore run2.py
python3 -W ignore render_block.py
```

Then build each mosaic with `gdalbuildvrt` and `gdal_translate` as in the St Marys commands, from `lossless/` to `..._mosaic_lossless.tif` and from `matched/` to `..._mosaic_tonemapped.tif`, and run `python3 -W ignore verify.py`.

## Site images: cluster matching

The site's map images were matched with the same tone mapping, one connected cluster at a time, so each region keeps its own look instead of the whole country being forced toward one color. 833 of the 880 sheets are matched. The other 47 keep their original color.

### Clusters

- **Grouping:** quads that share an edge form a cluster. The site has 650 quads, 632 of them standard 7.5' cells, which fall into 47 groups: 18 with two or more sheets and 29 lone sheets. The largest are 208 in Minnesota and 131 in the Florida peninsula and Keys.
- **Top sheet:** each quad is represented by the sheet the site shows by default, the earliest year, then the closest color match.
- **Stacked editions:** the other 230 editions follow their top sheet through `match_edition`: a cubic tone fit to its final color, plus slow drift capped at 0.08 so changed land and labels don't print through.
- **Left alone:** lone sheets and the 18 non-standard quads have no seams to fix, so they keep their color. Their other editions still follow them.

### Input

These are the site's 740 × 850 clipped images, about 1/8 of full resolution, read from JPEG. Distances in the chain are half the St Marys values, which ran at 1/4 scale: evening at sigma 130, 90, 60 and 45, seam window 15, node spacing 12. Output is JPEG quality 88.

### Two methods

`match` is the St Marys and Canaveral chain at this scale, and it was enough for most clusters. `match_wide` was added for clusters with big jumps between sheets, and was used on Florida's 131 sheets, Louisiana's 39 and 5, North Carolina's 16 and Virginia's 6.

| Addition in `match_wide` | Why |
|---|---|
| Dark blue water counts as water | The class rules were tuned on pale water, so dark tints skipped evening |
| `level_sheets` moves each sheet's class medians 85% toward the cluster's | Evening's wide blur can't fix a step exactly at a seam; a whole-sheet shift can |
| Early seam rounds accept wide pairs: (0.30, 0.16) twice, then (0.16, 0.09) | The strict limits rejected the seams that most needed fixing |
| `open_water` sets the water target from sheets at least 40% water | Marsh tints inland were dragging the target toward teal |
| `warm_area` limits the warm ink guard to small features | Large orange Everglades areas are land, not printed ink |
| Saturation returns to the cluster's own level, within 0.94 to 1.12 | The fixed 0.965 trim was tuned on St Marys and could overshoot |

### Solver

Direct solves stop being practical at this size, so above 450,000 unknowns per color the seam solve uses conjugate gradients with a diagonal preconditioner and a tolerance of 0.002. The Minnesota cluster reaches about 6.6 million unknowns per color. That makes each solve approximate, which is a reasonable trade for a smooth correction field, but it hasn't been compared against an exact solve.

### Results

Scored on the images at this scale, at control lines 12 pixels inside each sheet. Land and water are spread between sheets, before to after, in OKLab × 100.

| States | Sheets | Editions | Visibility raw | Worst raw | Visibility | Worst | Land | Water | Chroma | Method | Time |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MN | 208 | 6 | 2.25 | 18.95 | 0.91 | 2.46 | 5.45 to 3.43 | 4.55 to 3.28 | 0.974 | base | 682 s |
| FL | 131 | 85 | 3.29 | 17.53 | 0.77 | 1.24 | 7.93 to 4.87 | 6.99 to 2.87 | 1.032 | wide | 538 s |
| FL | 43 | 24 | 2.96 | 19.22 | 0.82 | 1.32 | 5.21 to 2.58 | 7.38 to 2.97 | 0.992 | base | 173 s |
| LA | 39 | 9 | 3.18 | 12.00 | 0.74 | 1.08 | 5.57 to 2.51 | 2.88 to 0.91 | 1.009 | wide | 158 s |
| FL, GA, SC | 36 | 30 | 2.65 | 8.83 | 0.83 | 1.25 | 6.04 to 2.76 | 3.15 to 1.63 | 0.993 | base | 158 s |
| LA | 29 | 15 | 2.49 | 19.49 | 0.88 | 1.26 | 5.98 to 3.54 | 4.86 to 3.64 | 1.016 | base | 130 s |
| MD | 25 | 12 | 3.07 | 8.74 | 0.84 | 1.50 | 5.11 to 2.49 | 6.91 to 2.04 | 1.009 | base | 80 s |
| NC | 16 | 5 | 4.18 | 8.94 | 0.66 | 0.85 | 5.07 to 2.85 | 4.00 to 0.51 | 1.013 | wide | 64 s |
| FL, GA | 14 | 5 | 2.77 | 6.84 | 0.79 | 1.08 | 4.00 to 3.14 | 2.55 to 4.14 | 0.982 | base | 328 s |
| TX | 13 | 2 | 3.66 | 14.12 | 0.81 | 1.15 | 5.52 to 0.98 | 3.10 to 1.21 | 0.983 | base | 239 s |
| GA | 11 | 0 | 2.23 | 4.23 | 0.88 | 1.14 | 5.97 to 1.58 | 2.50 to 2.88 | 0.982 | base | 226 s |
| NC | 11 | 9 | 1.84 | 2.73 | 0.93 | 1.20 | 5.52 to 3.01 | 6.23 to 3.20 | 0.956 | base | 222 s |
| VA | 6 | 4 | 4.47 | 9.71 | 0.72 | 0.98 | 5.65 to 1.56 | none | 1.007 | wide | 161 s |
| FL | 6 | 4 | 3.23 | 5.15 | 0.77 | 0.99 | 3.96 to 1.49 | 2.08 to 0.68 | 0.994 | base | 101 s |
| LA | 5 | 4 | 1.41 | 1.75 | 0.71 | 0.89 | 2.77 to 1.38 | 5.55 to 2.05 | 0.956 | wide | 146 s |
| FL | 4 | 4 | 4.62 | 11.02 | 0.87 | 0.94 | 4.22 to 2.77 | 7.94 to 1.01 | 0.959 | base | 56 s |
| LA | 4 | 2 | 1.66 | 2.32 | 0.67 | 0.72 | 4.61 to 1.37 | 2.20 to 0.73 | 0.948 | base | 56 s |
| MO | 2 | 0 | 1.51 | 1.51 | 1.16 | 1.16 | 5.30 to 2.05 | none | 0.975 | base | 23 s |

Times are from a shared machine with other clusters running, so they aren't comparable. The 220 stacked editions in these clusters are included in the times.

### What broke

- **Empty grid cells counted as forest.** A block's canvas includes empty cells, whose zeros classified as dark forest. Evening then chased a huge false forest area, and the first Georgia test came out at chroma 0.455 with land spread up from 6 to 9. Empty cells are now excluded.
- **A class missing from a whole cluster.** An empty median gave NaN, which spread through every sheet and crashed the solver. Two-sheet clusters with no water also crashed the metrics. Both are guarded now.
- **A line map beside an image map.** Fitchburg and Shirley, MA can't match, and forcing them put dark rings around lakes. Shirley was a false positive and was struck, leaving Fitchburg alone at its original color. A very low chroma score flagged this pair: 0.827.
- **Dark smudges on North Carolina water.** The first run left them along the Outer Banks, with a worst seam of 3.47. The wide method cleared them: 0.85.
- **Hard seams in Florida.** The first run reached only 1.19, worst 5.36, with dark blue water against pale at Sandy Key / East Bahia. Testing the wide method on the worst 60 sheets took 3 minutes and went from 4.02 to 0.79, worst 1.74. Full cluster: 0.78, worst 1.26.
- **Orange Everglades.** Seams stayed in orange land because the ink guard kept its original hue. `warm_area` fixed it.
- **Mint Keys.** Florida's water came out teal, because inland marsh tints shared the water target. `open_water` gave a bluer result, with water spread down from 3.16 to 2.87 and seams about the same at 0.77.

### Deploying

`site/clip/` and `site/clip8/` keep the originals, and matched images are in `site/clip_tm/` and `site/clip8_tm/`, which aren't in git. `stage_deploy.py` builds a deploy folder using the original file names, so `app.js` doesn't need to know. It only takes a cluster's images once that cluster's marker file exists, so a half-written run can't go live, and `HOLD` keeps a cluster back for review.

Don't deploy `topo_finder/site` directly. That would publish the originals plus both `_tm` folders.

### Known limits

- **Review:** clusters were judged from overviews and the worst seam crops, not at 1:1 across all 880 images. Stacked editions weren't reviewed by eye.
- **Lake Okeechobee area:** still somewhat blocky, and it's not settled how much of that is sheet differences and how much is real farmland.
- **Minnesota:** Red Lake is slightly blotchy, and there's a flat sage patch north of it. It ran on the base method, and the wide method wasn't tried.
- **Water spread rose in two clusters:** Florida and Georgia's 14 sheets (2.55 to 4.14) and Georgia's 11 (2.50 to 2.88), where seam fixes took priority over sheet averages.
- **Missouri:** the two-sheet cluster only reached 1.16.
- **Saturation:** the base method's fixed trim left some small clusters at 0.95 to 0.96. Only `match_wide` restores saturation.
- **Contact sheet:** the thumbs on the right are still the original USGS previews, so they don't match the map's colors.
- **Low-zoom outlines:** these still use each sheet's original average color. They fade out by zoom 6.
- **JPEG:** these images are compressed twice, from quality 84 to 88.

## Learnings

What carries over to the next block.

### Color

- **Seams and sheet averages are different problems.** On Canaveral, Selective Color got sheet colors closer together than tone mapping did (land spread 0.67 against 1.24) and still left obvious seams (3.58 against 0.91). A sheet-wide adjustment can match averages, but a seam is a local mismatch along one line.
- **Solve seams jointly, by tone, and separately for water.** Water and forest need different fixes at the same spot, and on Canaveral, water and land at the same brightness did too. One offset per sheet or one field for everything wasn't enough.
- **Protections need the right scope.** The pair limits that saved St Marys near-white flats caused Canaveral's dark rectangle. The danger is low-chroma near-white, not brightness as such, so saturated water needs its own rules.
- **Don't let a classifier feed on its own output.** Reclassifying each pass is needed because raw colors differ by sheet, but it can run away, so pin what the raw image makes certain.
- **Keep evening broad.** Sigma 60 (about 490 m) scored best and erased real landscape. Sigma 90 and up was the limit here.
- **Printed inks aren't terrain.** Sand, roads, town tint and blue lines need protecting, or land corrections quietly grey and muddy them. On Canaveral the blue test also catches 26% to 93% of pixels per sheet, which was harmless (visibility 1.02 to 1.03) only because it keeps the local shift rather than the raw color.
- **Return saturation to the block's own level.** Matching adds some on some blocks and removes it on others, so a fixed trim of 0.965 only suited St Marys. Measure it and scale back within limits.
- **Big jumps need a whole-sheet step first.** Blurred evening can't fix a step exactly at a seam, and strict pair limits reject the worst seams outright. Level whole sheets, then let early seam rounds accept large differences and tighten them after.
- **Take a class's target from where it's pure.** Averaging water across a block let marsh tints turn the Keys mint. Sheets that are mostly water give the real color.
- **A failed match can mean a wrong sheet.** Fitchburg and Shirley couldn't match because one was a line map. When a cluster's chroma collapses, look at the sheets before tuning.

### Checking

- **Look at 1:1 at seam junctions before calling it done.** Pink flats and grey contours passed every number and were invisible in overviews.
- **Use seam visibility, not raw step size.** Raw step counts real features, so it stops improving while the seams keep getting better. Comparing with control lines inside each sheet fixes that.
- **Use the exaggerated view for gestalt.** Sheet-shaped patches show up at 3.5× contrast long before a metric finds them.
- **A better number can be a worse picture.** Run 7 had the best scores and was too green, flat and muddy. Keep the score honest and let the picture decide.
- **Trace a defect through each stage.** The pink flats' first explanation was wrong. Printing one patch's color after every step found the real cause in minutes.
- **Measure the delivered file.** Reading back the final BigTIFF catches anything that happened after the working copy.

### Process

- **On a new block, run the settings unchanged first.** It shows exactly what breaks. Canaveral needed one addition, not a retune.
- **Empty cells are data.** A canvas with holes feeds zeros into every statistic unless they're masked. Check a new block's first numbers for anything impossible: chroma of 0.455 was the giveaway.
- **Test the fix on the worst part.** A 60-sheet Florida test took 3 minutes and proved the method before a 10-minute full run.
- **Mark a cluster finished only once it's written.** Staged deploys can then ship what's ready while the rest is still running, with no half-written cluster going live.
- **Keep lossless clips somewhere durable.** Canaveral's sources were gone, and its lossless clips survived only by luck in a temp folder. Tone mapping JPEG clips would compress everything twice.
- **Never fork after OpenCV has run threads.** On macOS the workers segfault in `cv2.resize` and the pool hangs, with a crash dialog for each worker. Run the color build and the render as separate processes.
- **Plan solver size.** A direct seam solve took 10 to 20 seconds per round at about 185,000 unknowns per color. Beyond about 450,000, conjugate gradients handled up to 6.6 million, at the cost of an approximate answer.
- **zsh doesn't split variables into words.** Options stored in a variable reach `gdal_translate` as one argument, so write them out.
- **A stopped command may have partly run.** One reported as rejected had already moved a folder, committed and created a GitHub repo. Check the disk and the remote before redoing anything.
- **Check the account before publishing.** Wrangler here was logged in to a work account while the personal Pages project lived elsewhere.

## Earlier color matching

The Cape Canaveral, Louisiana and NW Florida sets were matched inside Photoshop rather than by tone mapping, so the result stays editable as layers.

1. **Layers:** each sheet is a group, blend mode Normal, holding the sheet and a Selective Color adjustment layer. The file is written directly as PSD or PSB (`build_psd.py`).
2. **Model:** Selective Color (Relative) is modeled from FFmpeg's `vf_selectivecolor` algorithm, which matched Photoshop's render to within about 0.1 to 0.4 ΔE.
3. **Masks:** water and land are split per set: blue-yellow for Canaveral, lightness per tile for Louisiana, depth bands plus forest, swamp and clearing for NW Florida.
4. **Fit:** sliders are fitted with L-BFGS-B so each group lands on the median across tiles.
5. **Apply and verify:** values are set through ActionManager scripting, then measured on Photoshop's own flattened render.

| Set | Tiles | Mean ΔE before | After | Worst group after |
|---|---|---|---|---|
| Cape Canaveral | 6 | 7.8 | 2.4 | 6.1 |
| Louisiana | 19 | 6.6 | 2.0 | 6.2 |
| NW Florida | 32 | 8.8 | 3.0 | 15.7 |

These figures are CIELAB ΔE to the target and aren't comparable with the OKLab numbers above. A slider acts on a whole tile, so it can't fix gradients within one, which is why the St Marys block moved to tone mapping.

Cape Canaveral was later redone with tone mapping. See [its section](#cape-canaveral-tone-match) for both versions scored the same way.

## Appendix: scripts

The complete working sets, verbatim, in run order. `sheets.json`, `neatline.json` and the iteration scripts are in `scripts/4_st_marys/`.

### 4_st_marys/measure.py

Measure the printed neatline on every edge.

```python
# Measure the printed neatline stroke against the nominal 7.5' edge, per sheet and per edge.
import glob, os, re, sys, json
import numpy as np, rasterio
from pyproj import Transformer
OUT=sys.argv[1]
SRC = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos/src'
SHEETS = {s['scan']: s for s in json.load(open(os.path.dirname(os.path.abspath(__file__))+'/sheets.json'))}
def sheet(f):
    s = SHEETS[int(re.search(r'_(\d+)_\d{4}_\d+_geo\.tif', os.path.basename(f)).group(1))]
    w, so, e, n = s['bbox']
    return s, dict(westbc=w, eastbc=e, southbc=so, northbc=n)
H=22; BAND=4; STEP=20
res={}
for f in sorted(glob.glob(SRC+'/*.tif')):
    s_,b=sheet(f); name=s_['name']
    W,E,N,S=b['westbc'],b['eastbc'],b['northbc'],b['southbc']
    with rasterio.open(f) as d:
        rgb=d.read().astype(np.float32); gray=rgb.mean(0)
        t=Transformer.from_crs('EPSG:4267',d.crs,always_xy=True); inv=~d.transform
        h,w=gray.shape
        res[name]={}
        for edge in 'WENS':
            n=int(6900/STEP)
            s=np.linspace(0,1,n)
            if edge in 'WE':
                lon=np.full(n,W if edge=='W' else E); lat=N+(S-N)*s
            else:
                lat=np.full(n,N if edge=='N' else S); lon=W+(E-W)*s
            X,Y=t.transform(lon,lat)
            px,py=inv*(X,Y); px=np.asarray(px); py=np.asarray(py)
            outer=np.full(n,np.nan); inner=np.full(n,np.nan)
            for i in range(n):
                if edge in 'WE':
                    r=int(round(py[i])); c=px[i]-0.5
                    if r-BAND<0 or r+BAND>=h: continue
                    c0=int(round(c)); p=gray[r-BAND:r+BAND+1,c0-H:c0+H+1].mean(0); frac=c-c0
                    sign=1 if edge=='W' else -1
                else:
                    r=int(round(px[i])); c=py[i]-0.5
                    if r-BAND<0 or r+BAND>=w: continue
                    c0=int(round(c)); p=gray[c0-H:c0+H+1,r-BAND:r+BAND+1].mean(1); frac=c-c0
                    sign=1 if edge=='N' else -1
                # offsets are measured inward from nominal, in source pixels
                off=np.arange(-H,H+1)-frac if sign==1 else (np.arange(-H,H+1)-frac)[::-1]*-1
                if sign==-1: p=p[::-1]
                base=np.median(p[:8])
                if base<195 or p[:8].min()<170: continue
                j=np.argmax(p<base-60)
                if p[j]>=base-60 or j==0: continue
                k=j+int(np.argmin(p[j:j+7])); dark=p[k]
                if dark>110: continue
                th=(base+dark)/2
                j=np.argmax(p[:k+1]<th)
                outer[i]=off[j-1]+(p[j-1]-th)/(p[j-1]-p[j])*(off[j]-off[j-1])
                insideL=np.median(p[k+6:k+14]) if k+14<len(p) else np.nan
                if insideL-dark>70:
                    th2=(dark+insideL)/2
                    m=k+int(np.argmax(p[k:]>th2))
                    if p[m]>th2:
                        inner[i]=off[m-1]+(th2-p[m-1])/(p[m]-p[m-1])*(off[m]-off[m-1])
            # robust fit of the outer edge
            ok=np.isfinite(outer); t01=s
            keep=ok.copy()
            for _ in range(6):
                c=np.polyfit(t01[keep],outer[keep],5)
                r=outer-np.polyval(c,t01)
                sd=max(np.nanstd(r[keep]),0.15)
                keep=ok&(np.abs(r)<2.5*sd)
            fit=np.polyval(c,t01)
            wid=inner-outer
            res[name][edge]=dict(coef=c.tolist(),n_ok=int(ok.sum()),n_keep=int(keep.sum()),n=n,
                 rms=float(np.std(r[keep])),fit_min=float(fit.min()),fit_max=float(fit.max()),
                 width=float(np.nanmedian(wid)),width_n=int(np.isfinite(wid).sum()))
            q=res[name][edge]
            print(f"{name:14s} {edge} valid {q['n_ok']:3d}/{n} kept {q['n_keep']:3d} rms {q['rms']:.2f} outer-offset {q['fit_min']:+.2f}..{q['fit_max']:+.2f} stroke {q['width']:.2f} (n={q['width_n']})")
json.dump(res,open(OUT,'w'),indent=1)
```

### 4_st_marys/clip.py

Warp each sheet onto the shared grid.

```python
# Clip each sheet to its measured neatline and resample onto a shared NAD27 lat/lon grid.
# Target pixels map through the sheet georef, then a displacement that lands the
# inner side of the printed neatline exactly on the nominal 7.5' cell edge.
import glob, re, sys, json, os
import numpy as np, rasterio, rasterio.enums, cv2
from rasterio.transform import Affine
from pyproj import Transformer
from scipy.interpolate import RectBivariateSpline
J, OUTDIR, MARGIN, COMPRESS = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
SRC = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos/src'
SHEETS = {s['scan']: s for s in json.load(open(os.path.dirname(os.path.abspath(__file__))+'/sheets.json'))}
def sheet(f):
    s = SHEETS[int(re.search(r'_(\d+)_\d{4}_\d+_geo\.tif', os.path.basename(f)).group(1))]
    w, so, e, n = s['bbox']
    return s, dict(westbc=w, eastbc=e, southbc=so, northbc=n)
COLS, ROWS = int(sys.argv[5]), int(sys.argv[6])
meas = json.load(open(J))
os.makedirs(OUTDIR, exist_ok=True)
for f in sorted(glob.glob(SRC+'/*.tif')):
    s_, b = sheet(f); name = s_['name']
    W, E, N, S = b['westbc'], b['eastbc'], b['northbc'], b['southbc']
    m = meas[name]
    stroke = float(np.median([m[e]['width'] for e in 'WENS']))
    def inset(edge, s):
        return np.polyval(m[edge]['coef'], s) + stroke + MARGIN
    with rasterio.open(f) as d:
        src = np.moveaxis(d.read(), 0, -1)
        t = Transformer.from_crs('EPSG:4267', d.crs, always_xy=True)
        inv = ~d.transform
    g = 128
    uc = np.linspace(0, 1, g+1); vc = np.linspace(0, 1, g+1)
    U, V = np.meshgrid(uc, vc)
    X, Y = t.transform(W+(E-W)*U, N+(S-N)*V)
    px, py = inv*(X, Y)
    px = np.asarray(px)+(1-U)*inset('W', V)-U*inset('E', V)-0.5
    py = np.asarray(py)+(1-V)*inset('N', U)-V*inset('S', U)-0.5
    ui = (np.arange(COLS)+.5)/COLS; vi = (np.arange(ROWS)+.5)/ROWS
    mx = RectBivariateSpline(vc, uc, px)(vi, ui).astype(np.float32)
    my = RectBivariateSpline(vc, uc, py)(vi, ui).astype(np.float32)
    out = cv2.remap(src, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    tr = Affine((E-W)/COLS, 0, W, 0, (S-N)/ROWS, N)
    opts = dict(driver='GTiff', width=COLS, height=ROWS, count=3, dtype='uint8', crs='EPSG:4267', transform=tr,
                tiled=True, blockxsize=512, blockysize=512, photometric='RGB')
    if COMPRESS == 'jpeg':
        opts.update(compress='JPEG', jpeg_quality=92, photometric='YCBCR')
    else:
        opts.update(compress='DEFLATE', predictor=2, zlevel=9)
    base = os.path.basename(f).replace('_geo.tif', '_clip.tif').replace(' ', '')
    p = os.path.join(OUTDIR, base)
    with rasterio.open(p, 'w', **opts) as o:
        o.write(np.moveaxis(out, -1, 0))
        o.colorinterp = [rasterio.enums.ColorInterp.red, rasterio.enums.ColorInterp.green, rasterio.enums.ColorInterp.blue]
    print(name, 'stroke %.2f' % stroke, p, os.path.getsize(p)//1048576, 'MB')
```

### 4_st_marys/tone.py

The color library: every step of the match, plus the metrics.

```python
# Seam-driven colour harmonisation in OKLab: a jointly solved global tone map per sheet, then seam levelling with a smooth field.
import glob, json, os, re, sys, time
import numpy as np, cv2, rasterio
from rasterio.enums import Resampling
from scipy import sparse
from scipy.interpolate import RectBivariateSpline
from scipy.ndimage import median_filter
from scipy.sparse.linalg import cg, splu

HERE = os.path.dirname(os.path.abspath(__file__))
LOSSLESS = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos/lossless'
SHEETS = {s['scan']: s for s in json.load(open(HERE+'/sheets.json'))}
FAC = 4

def srgb2lin(c):
    return np.where(c <= .04045, c/12.92, ((c+.055)/1.055)**2.4)
def lin2srgb(c):
    c = np.clip(c, 0, None)
    return np.where(c <= .0031308, 12.92*c, 1.055*c**(1/2.4)-.055)
M1 = np.array([[.4122214708, .5363325363, .0514459929], [.2119034982, .6806995451, .1073969566], [.0883024619, .2817188376, .6299787005]], np.float32)
M2 = np.array([[.2104542553, .7936177850, -.0040720468], [1.9779984951, -2.4285922050, .4505937099], [.0259040371, .7827717662, -.8086757660]], np.float32)
M1i = np.linalg.inv(M1); M2i = np.linalg.inv(M2)
def rgb2oklab(rgb):
    return np.cbrt(srgb2lin(rgb)@M1.T)@M2.T
def oklab2rgb(lab):
    return lin2srgb((lab@M2i.T)**3@M1i.T)

def load(fac=FAC):
    T = []
    for f in sorted(glob.glob(LOSSLESS+'/*.tif')):
        scan = int(re.search(r'_(\d+)_\d{4}_', os.path.basename(f)).group(1)); s = SHEETS[scan]
        with rasterio.open(f) as d:
            a = np.moveaxis(d.read(out_shape=(3, d.height//fac, d.width//fac), resampling=Resampling.average), 0, -1).astype(np.float32)/255
        T.append(dict(s=s, f=f, lab=rgb2oklab(a).astype(np.float32)))
    ws = sorted({t['s']['bbox'][0] for t in T}); ns = sorted({t['s']['bbox'][3] for t in T}, reverse=True)
    grid = {}
    for t in T:
        t['rc'] = (ns.index(t['s']['bbox'][3]), ws.index(t['s']['bbox'][0])); grid[t['rc']] = t
    return T, grid, len(ns), len(ws)

def edges(grid):
    # Each seam as (first sheet, second sheet, direction); h means the second sheet lies east.
    E = []
    for (r, c), t in grid.items():
        if (r, c+1) in grid: E.append((t, grid[(r, c+1)], 'h'))
        if (r+1, c) in grid: E.append((t, grid[(r+1, c)], 'v'))
    return E

def strip(lab, side, d):
    return {'E': lab[:, -1-d], 'W': lab[:, d], 'S': lab[-1-d, :], 'N': lab[d, :]}[side]

def phi(c, order):
    L, a, b = c[..., 0], c[..., 1], c[..., 2]
    t = [np.ones_like(L), L, a, b]
    if order >= 2: t += [L*L, a*a, b*b, L*a, L*b, a*b]
    if order >= 3: t += [L**3, L*L*a, L*L*b]
    return np.stack(t, -1).astype(np.float64)

def seam_pairs(grid, sigma, depths, step):
    # Mirrored pixel pairs either side of each seam: they show nearly the same ground.
    P = []
    blur = {id(t): cv2.GaussianBlur(t['lab'], (0, 0), sigma) for t in grid.values()}
    for a, b, k in edges(grid):
        sa, sb = ('E', 'W') if k == 'h' else ('S', 'N')
        A = []; B = []
        for d in depths:
            A.append(strip(blur[id(a)], sa, d)[::step]); B.append(strip(blur[id(b)], sb, d)[::step])
        P.append((a, b, np.concatenate(A), np.concatenate(B)))
    return P

def fit_global(T, grid, order=2, lam=.02, sigma=4, depths=(4, 10, 18, 30), step=3, rounds=8, pin=.2, anchor=None):
    idx = {id(t): i for i, t in enumerate(T)}
    n = len(T); K = phi(np.zeros((1, 3)), order).shape[1]
    I = np.zeros((K, 3)); I[1, 0] = 1; I[2, 1] = 1; I[3, 2] = 1
    M = np.tile(I, (n, 1, 1))
    P = seam_pairs(grid, sigma, depths, step)
    pin_c = np.array([[0, 0, 0], [1, 0, 0], [.05, 0, 0], [.97, 0, 0]], float)
    F = [(idx[id(a)], idx[id(b)], phi(A, order), phi(B, order)) for a, b, A, B in P]
    for _ in range(rounds):
        H = np.zeros((n*K, n*K)); g = np.zeros((n*K, 3))
        for i, j, Fa, Fb in F:
            r = (Fa@M[i])-(Fb@M[j])
            w = 1/np.maximum(np.linalg.norm(r, axis=1), .012)              # Huber-style weights shrug off labels and line work
            w = w/w.mean()/len(w)
            Faw = Fa*w[:, None]; Fbw = Fb*w[:, None]
            ii = slice(i*K, (i+1)*K); jj = slice(j*K, (j+1)*K)
            H[ii, ii] += Fa.T@Faw; H[jj, jj] += Fb.T@Fbw
            cross = Fa.T@Fbw
            H[ii, jj] -= cross; H[jj, ii] -= cross.T
        H /= len(F)
        fp = phi(pin_c, order)
        for i in range(n):
            ii = slice(i*K, (i+1)*K)
            wt = lam*(anchor.get(T[i]['s']['name'], 1) if anchor else 1)
            H[ii, ii] += wt*np.eye(K)+pin*fp.T@fp/len(pin_c)
            g[ii] += wt*I+pin*fp.T@(fp@I)/len(pin_c)
        M = np.linalg.solve(H, g).reshape(n, K, 3)
    return M

def apply_global(lab, m, order):
    return (phi(lab, order)@m).astype(np.float32)

def seam_delta(a, b, sa, sb, depths=(3, 8, 14), along=12):
    # Robust colour offset along a seam, measured from what sits either side of it.
    A = np.mean([strip(a, sa, d) for d in depths], 0); B = np.mean([strip(b, sb, d) for d in depths], 0)
    d = (A-B).astype(np.float32)
    k = along*2+1
    d = median_filter(d, size=(k, 1), mode='nearest').astype(np.float32)
    return cv2.GaussianBlur(d, (1, 0), along, borderType=cv2.BORDER_REPLICATE)

def fit_field(T, grid, labs, node=20, along=40, seam_w=60., eps=.002):
    # One membrane per sheet, coupled across seams so each jump is cancelled, shared half and half.
    H, W = labs[0].shape[:2]
    ny, nx = H//node+2, W//node+2
    n = len(T); N = nx*ny*n
    id_ = lambda s, y, x: s*nx*ny+y*nx+x
    r = []; c = []; v = []
    def add(i, j, w):
        r.extend([i, j, i, j]); c.extend([i, j, j, i]); v.extend([w, w, -w, -w])
    for s in range(n):
        for y in range(ny):
            for x in range(nx):
                if x+1 < nx: add(id_(s, y, x), id_(s, y, x+1), 1.)
                if y+1 < ny: add(id_(s, y, x), id_(s, y+1, x), 1.)
    rhs = np.zeros((N, 3)); pos = {id(t): i for i, t in enumerate(T)}
    for a, b, k in edges(grid):
        ia, ib = pos[id(a)], pos[id(b)]
        sa, sb = ('E', 'W') if k == 'h' else ('S', 'N')
        d = seam_delta(labs[ia], labs[ib], sa, sb, along=along)
        m = ny if k == 'h' else nx
        at = np.linspace(0, len(d)-1, m).round().astype(int)
        for q, dd in zip(range(m), d[at]):
            p1 = id_(ia, q, nx-1) if k == 'h' else id_(ia, ny-1, q)
            p2 = id_(ib, q, 0) if k == 'h' else id_(ib, 0, q)
            add(p1, p2, seam_w)
            rhs[p1] -= seam_w*dd; rhs[p2] += seam_w*dd
    A = sparse.coo_matrix((v, (r, c)), shape=(N, N)).tocsc()+eps*sparse.identity(N, format='csc')
    lu = splu(A)
    X = np.stack([lu.solve(rhs[:, i]) for i in range(3)], -1)
    return X.reshape(n, ny, nx, 3), (ny, nx)

def field_up(fld, shape):
    h, w = shape; ny, nx = fld.shape[:2]
    gy = np.linspace(0, 1, ny); gx = np.linspace(0, 1, nx)
    yi = (np.arange(h)+.5)/h; xi = (np.arange(w)+.5)/w
    return np.stack([RectBivariateSpline(gy, gx, fld[..., c], kx=3, ky=3)(yi, xi) for c in range(3)], -1).astype(np.float32)

def de(a, b):
    return np.linalg.norm(a-b, axis=-1)*100

last_seams = []
def seam_crops(T, grid, labs, rows, cols, path, size=340, n=8):
    # Paired crops centred on the worst stretches of the worst seams, at quarter resolution scaled up.
    from PIL import Image, ImageDraw
    h, w = labs[0].shape[:2]; C = canvas(T, labs, rows, cols); pos = {id(t): i for i, t in enumerate(T)}
    spots = []
    for a, b, k in edges(grid):
        ia, ib = pos[id(a)], pos[id(b)]; sa, sb = ('E', 'W') if k == 'h' else ('S', 'N')
        A = np.mean([strip(labs[ia], sa, d) for d in (2, 5, 8)], 0); B = np.mean([strip(labs[ib], sb, d) for d in (2, 5, 8)], 0)
        q = cv2.GaussianBlur(de(A, B).astype(np.float32).reshape(-1, 1), (1, 0), 30).ravel(); i = int(q.argmax())
        r, c = a['rc']; x = (c+1)*w if k == 'h' else c*w+i; y = r*h+i if k == 'h' else (r+1)*h
        spots.append((float(q[i]), x, y, f"{a['s']['name'][:10]}|{b['s']['name'][:10]} {q[i]:.1f}"))
    spots.sort(reverse=True); out = Image.new('RGB', (4*size+12, 2*size+4), 'white'); dr = ImageDraw.Draw(out)
    for i, (q, x, y, tag) in enumerate(spots[:n]):
        x0 = min(max(x-size//4, 0), C.shape[1]-size//2); y0 = min(max(y-size//4, 0), C.shape[0]-size//2)
        c = (np.clip(oklab2rgb(C[y0:y0+size//2, x0:x0+size//2]), 0, 1)*255).astype(np.uint8)
        px, py = (i % 4)*(size+4), (i//4)*(size+4)
        out.paste(Image.fromarray(c).resize((size, size), Image.BICUBIC), (px, py)); dr.text((px+4, py+4), tag, fill='red')
    out.save(path)

def metrics(T, grid, labs, base):
    pos = {id(t): i for i, t in enumerate(T)}
    J = []
    for a, b, k in edges(grid):
        ia, ib = pos[id(a)], pos[id(b)]
        sa, sb = ('E', 'W') if k == 'h' else ('S', 'N')
        A = np.mean([strip(cv2.GaussianBlur(labs[ia], (0, 0), 3), sa, d) for d in (2, 5, 8)], 0)
        B = np.mean([strip(cv2.GaussianBlur(labs[ib], (0, 0), 3), sb, d) for d in (2, 5, 8)], 0)
        q = cv2.GaussianBlur(de(A, B).astype(np.float32).reshape(-1, 1), (1, 0), 10).ravel()
        J.append((np.median(q), np.percentile(q, 90), f"{a['s']['name'][:9]}|{b['s']['name'][:9]}"))
    def cls(lab):
        L, A, B = lab[..., 0], lab[..., 1], lab[..., 2]; C = np.hypot(A, B)
        return (L > .3) & (A < -.02) & (B > .02), (B < -.004) & (L > .55), C
    sp = {'land': [], 'water': []}; chroma = []; hp = []
    for lab, b0 in zip(labs, base):
        s = cv2.GaussianBlur(lab, (0, 0), 3); land, water, C = cls(cv2.GaussianBlur(b0, (0, 0), 3))
        if land.mean() > .03: sp['land'].append(s[land].mean(0))
        if water.mean() > .03: sp['water'].append(s[water].mean(0))
        chroma.append(np.hypot(lab[..., 1], lab[..., 2]).mean()/np.hypot(b0[..., 1], b0[..., 2]).mean())
        h = lab[..., 0]-cv2.GaussianBlur(lab[..., 0], (0, 0), 6); h0 = b0[..., 0]-cv2.GaussianBlur(b0[..., 0], (0, 0), 6)
        hp.append(h.std()/h0.std())
    spread = {k: float(np.mean(np.linalg.norm(np.array(v)-np.mean(v, 0), axis=1))*100) if v else 0. for k, v in sp.items()}
    rgb = [oklab2rgb(l) for l in labs]
    clipped = float(np.mean([((r < 0) | (r > 1)).any(-1).mean() for r in rgb])*100)
    global last_seams; last_seams = sorted(J, key=lambda j: -j[1])
    return dict(seam_med=float(np.mean([j[0] for j in J])), seam_p90=float(np.mean([j[1] for j in J])), seam_worst=float(max(j[1] for j in J)), worst=max(J, key=lambda j: j[1])[2],
                land_spread=spread['land'], water_spread=spread['water'], chroma=float(np.mean(chroma)), detail=float(np.mean(hp)), detail_min=float(min(hp)), clipped_pct=clipped)

def mosaic(T, labs, rows, cols, fac=2):
    h, w = labs[0].shape[:2]
    C = np.zeros((rows*h//fac, cols*w//fac, 3), np.uint8)
    for t, l in zip(T, labs):
        r, c = t['rc']
        s = cv2.resize(l, (w//fac, h//fac), interpolation=cv2.INTER_AREA)
        C[r*(h//fac):(r+1)*(h//fac), c*(w//fac):(c+1)*(w//fac)] = (np.clip(oklab2rgb(s), 0, 1)*255+.5).astype(np.uint8)
    return C

CLASSES = ('forest', 'clearing', 'marsh', 'water')
def classify(lab):
    # Soft-free class map from a lightly blurred colour image: 0 forest, 1 clearing, 2 marsh, 3 water, -1 other (sand, roads, labels).
    s = cv2.GaussianBlur(lab, (0, 0), 3)
    L, A, B = s[..., 0], s[..., 1], s[..., 2]
    k = np.full(L.shape, -1, np.int8)
    green = A < -.012
    k[green & (B >= .045) & (L < .62)] = 0
    k[green & (B >= .045) & (L >= .62)] = 1
    k[green & (B < .045) & (B >= -.002) & (L < .74)] = 2
    k[(L >= .72) & (B < .03) & (A < .012)] = 3
    return k

def canvas(T, labs, rows, cols):
    h, w = labs[0].shape[:2]
    C = np.zeros((rows*h, cols*w, labs[0].shape[-1] if labs[0].ndim == 3 else 1), labs[0].dtype)
    for t, l in zip(T, labs):
        r, c = t['rc']
        C[r*h:(r+1)*h, c*w:(c+1)*w] = l if l.ndim == 3 else l[..., None]
    return C

def cut(T, C, rows, cols, h, w):
    return [C[t['rc'][0]*h:(t['rc'][0]+1)*h, t['rc'][1]*w:(t['rc'][1]+1)*w] for t in T]

def gblur(a, s):
    # Large Gaussian on a reduced grid; the result is smooth, so nothing is lost and it stays fast.
    f = max(1, int(s/4))
    sm = cv2.resize(a, (a.shape[1]//f, a.shape[0]//f), interpolation=cv2.INTER_AREA) if f > 1 else a
    b = cv2.GaussianBlur(sm, (0, 0), s/f, borderType=cv2.BORDER_REFLECT)
    return cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_CUBIC) if f > 1 else b

def dodge(T, base, labs, rows, cols, sigma=180, alpha=(.8, .6, .7, .4), target=None, over=None):
    # Local tone mapping per class: even out each class's slow drift across the mosaic, leaving real detail alone.
    h, w = labs[0].shape[:2]
    K = canvas(T, [classify(b) for b in labs], rows, cols)[..., 0]             # classify the current estimate, because raw colours differ by sheet
    K[canvas(T, [np.ones(l.shape[:2], np.uint8) for l in labs], rows, cols)[..., 0] == 0] = -1   # empty grid cells are not forest
    R = canvas(T, base, rows, cols); Rs = cv2.GaussianBlur(R, (0, 0), 3)
    K[(Rs[..., 0] >= .78) & (Rs[..., 2] < .03) & (Rs[..., 1] < .012)] = 3      # pale flats stay water: a drifting estimate must not recruit them into land
    C = canvas(T, labs, rows, cols).astype(np.float32)
    corr = np.zeros_like(C); conf = np.zeros(C.shape[:2], np.float32); total = np.zeros_like(C); targets = {}
    for i, name in enumerate(CLASSES):
        if not (K == i).any(): continue                                        # a small block can lack a class, and an empty median would poison everything
        m = (K == i).astype(np.float32)
        den = gblur(m, sigma)
        num = np.stack([gblur(C[..., c]*m, sigma) for c in range(3)], -1)
        mu = num/np.maximum(den, 1e-4)[..., None]
        tau = target[name] if target else np.array([np.median(C[..., c][K == i]) for c in range(3)], np.float32)
        if over and name in over: tau = np.array(over[name], np.float32)
        targets[name] = tau
        ok = np.clip(den/.02, 0, 1)[..., None]                          # fade out where a class is barely present
        d = (tau-mu)*alpha[i]*ok
        corr += d*m[..., None]
        total += d*den[..., None]; conf += den
    other = (K < 0)
    fill = total/np.maximum(conf, 1e-4)[..., None]
    corr[other] = (fill*(1-smooth(C[..., 0], .78, .86))[..., None])[other]
    corr = np.stack([cv2.GaussianBlur(corr[..., c], (0, 0), 2) for c in range(3)], -1)
    return cut(T, C+corr, rows, cols, h, w), cut(T, corr, rows, cols, h, w), targets

def baseline(T, labs):
    # What the seam metric reads on real, unbroken map: fake seams through the sheet centres.
    q = []
    for l in labs:
        s = cv2.GaussianBlur(l, (0, 0), 3); w = s.shape[1]//2; h = s.shape[0]//2
        for A, B in ((np.mean([s[:, w-1-d] for d in (2, 5, 8)], 0), np.mean([s[:, w+d] for d in (2, 5, 8)], 0)), (np.mean([s[h-1-d] for d in (2, 5, 8)], 0), np.mean([s[h+d] for d in (2, 5, 8)], 0))):
            p = cv2.GaussianBlur(de(A, B).astype(np.float32).reshape(-1, 1), (1, 0), 10).ravel()
            q.append((np.median(p), np.percentile(p, 90)))
    return float(np.mean([a for a, _ in q])), float(np.mean([b for _, b in q]))

def gamut_map(lab):
    # Pull out-of-gamut colours in along chroma, holding lightness and hue, instead of clipping channels.
    rgb = oklab2rgb(lab)
    bad = ((rgb < -1e-4) | (rgb > 1+1e-4)).any(-1)
    if not bad.any(): return lab
    p = lab[bad].copy(); lo = np.zeros(len(p)); hi = np.ones(len(p))
    for _ in range(12):
        m = (lo+hi)/2; q = p.copy(); q[:, 1:] *= m[:, None]
        r = oklab2rgb(q); out = ((r < 0) | (r > 1)).any(-1)
        hi = np.where(out, m, hi); lo = np.where(out, lo, m)
    p[:, 1:] *= lo[:, None]
    res = lab.copy(); res[bad] = p
    return res

def pipeline(T, grid, base, rows, cols, order=3, lam=.005, sigma=(260, 180, 120), alpha=(.8, .6, .7, .4), passes=3, along=40, seam_w=60., node=20):
    M = fit_global(T, grid, order=order, lam=lam)
    L = [apply_global(x, m, order) for x, m in zip(base, M)]
    corr = [np.zeros_like(x) for x in base]
    sigmas = sigma if isinstance(sigma, (tuple, list)) else [sigma]*passes
    for sg in sigmas:
        L, c, tau = dodge(T, base, L, rows, cols, sigma=sg, alpha=alpha)
        corr = [a+b for a, b in zip(corr, c)]
    F, _ = fit_field(T, grid, L, node=node, along=along, seam_w=seam_w)
    out = [a+field_up(f, a.shape[:2]) for a, f in zip(L, F)]
    return out, dict(M=M, corr=corr, F=F, tau=tau)

TONES = np.array([.22, .38, .52, .66, .80, .92, 1.0], np.float32)
def tone_basis(L, tones=TONES):
    # Piecewise-linear weights across the tone nodes.
    L = np.clip(L, tones[0], tones[-1]-1e-4)
    i = np.searchsorted(tones, L, side='right')-1
    return i, (L-tones[i])/(tones[i+1]-tones[i])

def seam_tone_delta(a, b, sa, sb, nodes, along, tones=TONES, depths=(2, 4, 7, 11, 16), blur=1.5, select=None, limits=None):
    # Across-seam offset per position and per tone, using only pairs that look like the same material.
    ba = cv2.GaussianBlur(a, (0, 0), blur); bb = cv2.GaussianBlur(b, (0, 0), blur)
    A = np.stack([strip(ba, sa, d) for d in depths], 1); B = np.stack([strip(bb, sb, d) for d in depths], 1)
    d = A-B; L = (A[..., 0]+B[..., 0])/2
    hi = smooth(L, .70, .85)                                                   # near white, everything looks alike, so demand a closer match
    ok = (np.abs(d[..., 0]) < .09-.055*hi) & (np.hypot(d[..., 1], d[..., 2]) < .05-.03*hi)
    if limits: ok = (np.abs(d[..., 0]) < limits[0]) & (np.hypot(d[..., 1], d[..., 2]) < limits[1])
    if select: ok &= select(A) & select(B)
    pos = np.repeat(np.arange(A.shape[0])[:, None], len(depths), 1)
    i, f = tone_basis(L)
    D = np.zeros((len(nodes), len(tones), 3), np.float32); C = np.zeros((len(nodes), len(tones)), np.float32)
    for q, p in enumerate(nodes):
        g = np.exp(-.5*((pos-p)/along)**2)*ok
        for k in range(len(tones)):
            w = g*((i == k)*(1-f)+(i+1 == k)*f)
            s = w.sum()
            if s < 1e-3: continue
            m = (w[..., None]*d).sum((0, 1))/s
            for _ in range(2):
                r = np.linalg.norm(d-m, axis=-1); u = w/np.maximum(r, .012)
                m = (u[..., None]*d).sum((0, 1))/u.sum()
            D[q, k] = m; C[q, k] = s
    return D, C

def fit_bilateral(T, grid, labs, node=30, along=45, seam_w=30., tone_w=.6, eps=.003, hi_eps=.06, c0=25., tones=TONES, select=None, limits=None, cg_above=450000, cg_tol=2e-3):
    # One colour field per sheet over (y, x, tone), coupled across seams, so bright water and dark forest each get their own correction.
    H, W = labs[0].shape[:2]; ny, nx, nt = H//node+2, W//node+2, len(tones)
    n = len(T); per = ny*nx*nt; N = n*per
    idx = lambda s, y, x, k: s*per+(y*nx+x)*nt+k
    Y, X, K = np.meshgrid(np.arange(ny), np.arange(nx), np.arange(nt), indexing='ij')
    pairs = []
    for s in range(n):
        base = idx(s, Y, X, K)
        pairs.append((base[:, :-1].ravel(), base[:, 1:].ravel(), np.ones(base[:, :-1].size)))
        pairs.append((base[:-1].ravel(), base[1:].ravel(), np.ones(base[:-1].size)))
        pairs.append((base[..., :-1].ravel(), base[..., 1:].ravel(), np.full(base[..., :-1].size, tone_w)))
    rhs = np.zeros((N, 3)); pos = {id(t): i for i, t in enumerate(T)}
    for a, b, k in edges(grid):
        ia, ib = pos[id(a)], pos[id(b)]
        sa, sb = ('E', 'W') if k == 'h' else ('S', 'N')
        m = ny if k == 'h' else nx; L = H if k == 'h' else W
        nodes = np.linspace(0, L-1, m)
        D, C = seam_tone_delta(labs[ia], labs[ib], sa, sb, nodes, along, select=select, limits=limits)
        w = seam_w*np.clip(C/c0, 0, 1)
        q, t = np.meshgrid(np.arange(m), np.arange(nt), indexing='ij')
        p1 = idx(ia, q, nx-1, t) if k == 'h' else idx(ia, ny-1, q, t)
        p2 = idx(ib, q, 0, t) if k == 'h' else idx(ib, 0, q, t)
        keep = w.ravel() > 0
        pairs.append((p1.ravel()[keep], p2.ravel()[keep], w.ravel()[keep]))
        np.add.at(rhs, p1.ravel(), -(w[..., None]*D).reshape(-1, 3)); np.add.at(rhs, p2.ravel(), (w[..., None]*D).reshape(-1, 3))
    i = np.concatenate([p[0] for p in pairs]); j = np.concatenate([p[1] for p in pairs]); w = np.concatenate([p[2] for p in pairs])
    leash = np.full(N, eps); leash[(np.arange(N) % nt) >= nt-3] = hi_eps       # highlights stay near zero unless a seam really asks otherwise
    A = sparse.coo_matrix((np.r_[w, w, -w, -w], (np.r_[i, j, i, j], np.r_[i, j, j, i])), shape=(N, N)).tocsc()+sparse.diags(leash, format='csc')
    if N > cg_above:                                                           # a direct solve gets too slow and too large on big blocks
        M = sparse.diags(1/A.diagonal()); A = A.tocsr()
        X = np.stack([cg(A, rhs[:, c], M=M, rtol=cg_tol, maxiter=6000)[0] for c in range(3)], -1)
    else:
        lu = splu(A, permc_spec='COLAMD')
        X = np.stack([lu.solve(rhs[:, c]) for c in range(3)], -1)
    return X.reshape(n, ny, nx, nt, 3).astype(np.float32)

def apply_bilateral(lab, fld, tones=TONES, weight=None):
    h, w = lab.shape[:2]; nt = fld.shape[2]
    ys = np.linspace(0, fld.shape[0]-1, h, dtype=np.float32); xs = np.linspace(0, fld.shape[1]-1, w, dtype=np.float32)
    mx, my = np.meshgrid(xs, ys)
    i, f = tone_basis(lab[..., 0]); out = lab.copy()
    for k in range(nt-1):
        m = (i == k)
        if not m.any(): continue
        lo = cv2.remap(fld[:, :, k], mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        hi = cv2.remap(fld[:, :, k+1], mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        d = lo[m]*(1-f[m])[:, None]+hi[m]*f[m][:, None]
        out[m] += d if weight is None else d*weight[m][:, None]
    return out

def visibility(T, grid, labs, off=24):
    # How much stronger the colour step is on the real seam than on parallel control lines inside each sheet: 1.0 means no seam at all.
    pos = {id(t): i for i, t in enumerate(T)}; R = []; S = []; C = []
    for a, b, k in edges(grid):
        ia, ib = pos[id(a)], pos[id(b)]; sa, sb = ('E', 'W') if k == 'h' else ('S', 'N')
        sA = cv2.GaussianBlur(labs[ia], (0, 0), 2); sB = cv2.GaussianBlur(labs[ib], (0, 0), 2)
        ds = (2, 4, 6)
        seam = de(np.mean([strip(sA, sa, d) for d in ds], 0), np.mean([strip(sB, sb, d) for d in ds], 0))
        ctl = []
        for src, sd in ((sA, sa), (sB, sb)):
            ctl.append(de(np.mean([strip(src, sd, off-1-d) for d in ds], 0), np.mean([strip(src, sd, off+d) for d in ds], 0)))
        ctl = np.mean(ctl, 0)
        w = 40; ker = np.ones(w)/w
        x = np.convolve(seam, ker, 'valid'); y = np.convolve(ctl, ker, 'valid')
        S.append(np.median(x)); C.append(np.median(y)); R.append(np.median(x)/max(np.median(y), 1e-3))
    return dict(ratio=float(np.mean(R)), ratio_worst=float(max(R)), seam=float(np.mean(S)), control=float(np.mean(C)))

def stack(T, grid, base, rows, cols, order=3, lam=.005, sigmas=(260, 180, 120), alpha=(.8, .6, .7, .4), rounds=3, **kw):
    M = fit_global(T, grid, order=order, lam=lam)
    L = [apply_global(x, m, order) for x, m in zip(base, M)]
    for sg in sigmas:
        L, _, _ = dodge(T, base, L, rows, cols, sigma=sg, alpha=alpha)
    for _ in range(rounds):
        F = fit_bilateral(T, grid, L, **kw)
        L = [apply_bilateral(a, f) for a, f in zip(L, F)]
    return L

def band_profile(T, labs, tag=''):
    # Forest and clearing lightness against distance from a sheet edge; a flat line means no band along the seams.
    bins = [0, 15, 40, 80, 140, 220, 320]; out = {}
    cells = {x['rc'] for x in T}
    for name, cl in (('forest', 0), ('clearing', 1)):
        vs = []
        for x, l in zip(T, labs):
            r, c = x['rc']; K = classify(l); h, w = l.shape[:2]
            yy, xx = np.mgrid[0:h, 0:w]
            d = np.full((h, w), 1e9, np.float32)
            if (r-1, c) in cells: d = np.minimum(d, yy)
            if (r+1, c) in cells: d = np.minimum(d, h-1-yy)
            if (r, c-1) in cells: d = np.minimum(d, xx)
            if (r, c+1) in cells: d = np.minimum(d, w-1-xx)
            row = []
            for a, b in zip(bins, bins[1:]):
                m = (K == cl) & (d >= a) & (d < b)
                row.append(l[..., 0][m].mean() if m.sum() > 400 else np.nan)
            vs.append(row)
        p = np.nanmean(np.array(vs), 0)*100
        out[name] = p-p[-1]
    return {k: [round(float(x), 2) for x in v] for k, v in out.items()}

def stack2(T, grid, base, rows, cols, order=3, lam=.005, alpha=(.8, .6, .7, .4), along=30, node=24, rounds=(3, 3, 2), sigmas=((260, 180, 120), (90,), (60,)), finish=.6):
    M = fit_global(T, grid, order=order, lam=lam)
    L = [apply_global(x, m, order) for x, m in zip(base, M)]
    for sgs, rn in zip(sigmas, rounds):
        for sg in sgs:
            L, _, _ = dodge(T, base, L, rows, cols, sigma=sg, alpha=alpha if sgs == sigmas[0] else tuple(a*finish for a in alpha))
        for _ in range(rn):
            F = fit_bilateral(T, grid, L, along=along, node=node)
            L = [apply_bilateral(a, f) for a, f in zip(L, F)]
    return L

def smooth(a, lo, hi):
    x = np.clip((a-lo)/(hi-lo), 0, 1); return x*x*(3-2*x)

def finish(T, grid, base, L, order=3, lam=.005, chroma=.965):
    # Warm inks (sand, roads, town tint) were never green: keep their hue from the global step, and trim the saturation the matching added.
    M = fit_global(T, grid, order=order, lam=lam)
    out = []
    for x, m, l in zip(base, M, L):
        g = apply_global(x, m, order)
        s = cv2.GaussianBlur(x, (0, 0), 1.2)
        w = smooth(s[..., 1], -.022, -.004)*smooth(np.hypot(s[..., 1], s[..., 2]), .02, .05)
        o = l.copy()
        o[..., 1:] = l[..., 1:]*chroma*(1-w)[..., None]+g[..., 1:]*w[..., None]
        out.append(o)
    return out


def ink_guard(src, out, sig=12, warm_area=None):
    # Printed inks keep their colour. Thin blue lines are found by being bluer than their surroundings, so flat ocean tints stay matched;
    # they take the shift of the water around them. Warm inks (sand, roads, town tint) keep their original hue outright.
    s = cv2.GaussianBlur(src, (0, 0), .7)
    bg = cv2.GaussianBlur(src[..., 2], (0, 0), sig)
    blue = np.maximum(smooth(bg-s[..., 2], .008, .022), smooth(-s[..., 2], .028, .05))
    warm = smooth(s[..., 1], -.012, .004)*smooth(np.hypot(s[..., 1], s[..., 2]), .03, .06)
    if warm_area: warm = warm*(1-smooth(cv2.GaussianBlur(warm, (0, 0), warm_area), .3, .6))     # large warm areas are land, not ink
    d = out[..., 1:]-src[..., 1:]
    shift = np.stack([cv2.GaussianBlur(d[..., c], (0, 0), sig) for c in range(2)], -1)
    o = out.copy()
    o[..., 1:] += (src[..., 1:]+shift-out[..., 1:])*blue[..., None]
    o[..., 1:] += (src[..., 1:]-o[..., 1:])*warm[..., None]
    return o

def trim(L, chroma=.965):
    o = [l.copy() for l in L]
    for x in o: x[..., 1:] *= chroma
    return o

def water_mask(lab):
    return smooth(-cv2.GaussianBlur(lab, (0, 0), 1)[..., 2], .0, .018)

def water_pass(T, grid, L, rounds=3, limits=(.16, .09), along=30, node=24):
    # For blocks with saturated water: seam solve on cool pixels only, with looser limits, applied through a soft water mask so land keeps its own correction.
    cool = lambda c: c[..., 2] < -.004
    for _ in range(rounds):
        F = fit_bilateral(T, grid, L, along=along, node=node, hi_eps=.003, select=cool, limits=limits)
        L = [apply_bilateral(a, f, weight=water_mask(a)) for a, f in zip(L, F)]
    return L
```

### 4_st_marys/run9.py

The final St Marys color build. It writes `work/final_q.npz`.

```python
# Rebuild with pale flats pinned and inks guarded, then recheck the two defects.
import numpy as np, cv2, tone as t
from PIL import Image
T, grid, rows, cols = t.load()
base = [x['lab'] for x in T]
L0 = t.stack2(T, grid, base, rows, cols, rounds=(3, 4), sigmas=((260, 180, 120), (90,)), finish=.5)
L = t.trim(L0)
np.savez('work/final_q.npz', **{str(x['s']['scan']): l.astype(np.float32) for x, l in zip(T, L)})
V = [t.ink_guard(b, l, 3) for b, l in zip(base, L)]
print('band', t.band_profile(T, V), flush=True)
print({k: round(a, 2) for k, a in t.visibility(T, grid, V).items()}); m = t.metrics(T, grid, V, base)
print({a: (round(b, 3) if isinstance(b, float) else b) for a, b in m.items() if a != 'worst'})
C = lambda X: t.canvas(T, X, rows, cols)
b, l = C(base), C(V); CW, CH = 5886//4, 6820//4; y0, x0 = int(1.55*CH), 2*CW
r = b[y0-30:y0+30, x0-40:x0-5]; k = r[..., 0] > .86
print('pale flats raw', np.round(r[k].mean(0), 3), 'final', np.round(l[y0-30:y0+30, x0-40:x0-5][k].mean(0), 3))
G = [t.gamut_map(v) for v in V]
Image.fromarray(t.mosaic(T, G, rows, cols, 2)).resize((1103, 1278), Image.LANCZOS).save('qa/run9.png')
t.seam_crops(T, grid, G, rows, cols, 'qa/run9_seams.png')
```

### 4_st_marys/render.py

The full-resolution render.

```python
# Full-resolution render: learn a local affine colour map (before to after) per sheet at quarter scale, then apply it to the original pixels.
import glob, json, multiprocessing as mp, os, sys, time
import cv2, numpy as np, rasterio, rasterio.enums
import tone as t

OUT = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos/matched'
FINAL = 'work/final_q.npz'
R, EPS = 6, 2e-4

def local_affine(I, p, r=R, eps=EPS):
    # A guided filter on the colour change, so full-resolution detail comes from the source, not the small image.
    box = lambda x: cv2.blur(x, (2*r+1, 2*r+1), borderType=cv2.BORDER_REFLECT)
    h, w = I.shape[:2]; d = p-I
    mI = box(I); mD = box(d)
    S = np.zeros((h, w, 3, 3), np.float32); C = np.zeros((h, w, 3, 3), np.float32)
    for i in range(3):
        for j in range(i, 3):
            S[..., i, j] = S[..., j, i] = box(I[..., i]*I[..., j])-mI[..., i]*mI[..., j]
        for c in range(3):
            C[..., i, c] = box(I[..., i]*d[..., c])-mI[..., i]*mD[..., c]
    S += eps*np.eye(3, dtype=np.float32)
    a = np.linalg.solve(S, C).astype(np.float32)
    b = mD-(a*mI[..., :, None]).sum(2)
    a = np.stack([box(a[..., i, c]) for i in range(3) for c in range(3)], -1)
    return a, box(b)

def one(args):
    name, f, q0, q1 = args
    t0 = time.time()
    with rasterio.open(f) as d:
        prof = d.profile.copy(); src = np.moveaxis(d.read(), 0, -1)
    H, W = src.shape[:2]
    a, b = local_affine(q0, q1)
    lab = t.rgb2oklab(src.astype(np.float32)/255).astype(np.float32); del src
    up = lambda x: cv2.resize(x, (W, H), interpolation=cv2.INTER_CUBIC)
    out = lab.copy()
    for c in range(3):
        out[..., c] += sum(up(a[..., i*3+c])*lab[..., i] for i in range(3))+up(b[..., c])
    out = t.gamut_map(t.ink_guard(lab, out))
    del lab
    rgb = (np.clip(t.oklab2rgb(out), 0, 1)*255+.5).astype(np.uint8)
    q = cv2.resize(out, (q0.shape[1], q0.shape[0]), interpolation=cv2.INTER_AREA)
    miss = float(np.median(t.de(q, t.ink_guard(q0, q1, 3))))
    prof.update(count=3, dtype='uint8', compress='deflate', predictor=2, zlevel=6, tiled=True, blockxsize=512, blockysize=512, photometric='RGB')
    with rasterio.open(f'{OUT}/{os.path.basename(f)}', 'w', **prof) as o:
        o.write(np.moveaxis(rgb, -1, 0))
        o.colorinterp = [rasterio.enums.ColorInterp.red, rasterio.enums.ColorInterp.green, rasterio.enums.ColorInterp.blue]
    return name, round(miss, 3), round(time.time()-t0)

# Keep this in its own process, apart from the colour build: OpenCV's threads do not survive a fork on macOS, and forked workers segfault.
if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    T, grid, rows, cols = t.load()
    Z = np.load(FINAL)
    jobs = [(x['s']['name'], x['f'], x['lab'], Z[str(x['s']['scan'])].astype(np.float32)) for x in T]
    with mp.get_context('fork').Pool(3) as p:
        for r in p.imap_unordered(one, jobs): print(r, flush=True)
```

### 4_st_marys/verify.py

Checks on the delivered St Marys files.

```python
# Verify the finished file itself: format, grid, seams and detail, reading only from the delivered BigTIFFs.
import numpy as np, cv2, rasterio, tone as t
from rasterio.windows import Window
from rasterio.enums import Resampling
from PIL import Image, ImageDraw
D = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos/'
A = D+'GA_Woodbine_Fernandina_1979-81_24000_mosaic.tif'; B = D+'GA_Woodbine_Fernandina_1979-81_24000_mosaic_matched.tif'
print('magic', open(B, 'rb').read(4), '(II+ is BigTIFF)')
a = rasterio.open(A); b = rasterio.open(B)
print(b.crs.to_string(), b.width, b.height, b.count, b.dtypes[0], b.compression.name, b.tags(ns='IMAGE_STRUCTURE').get('LAYOUT'), 'overviews', b.overviews(1))
print('same grid as raw', a.transform.almost_equals(b.transform, 1e-12) and a.shape == b.shape, '| bounds', [round(x, 4) for x in b.bounds], '| mask all valid', bool(b.read_masks(1, out_shape=(500, 430)).min() == 255))
CW, CH = 5886, 6820; FAC = 4
qa = np.moveaxis(a.read(out_shape=(3, a.height//FAC, a.width//FAC), resampling=Resampling.average), 0, -1).astype(np.float32)/255
qb = np.moveaxis(b.read(out_shape=(3, b.height//FAC, b.width//FAC), resampling=Resampling.average), 0, -1).astype(np.float32)/255
T, grid, rows, cols = t.load(); h, w = T[0]['lab'].shape[:2]
la = t.cut(T, t.rgb2oklab(qa).astype(np.float32), rows, cols, h, w); lb = t.cut(T, t.rgb2oklab(qb).astype(np.float32), rows, cols, h, w)
print('from file, seam visibility raw', {k: round(v, 2) for k, v in t.visibility(T, grid, la).items()})
print('from file, seam visibility matched', {k: round(v, 2) for k, v in t.visibility(T, grid, lb).items()})
m = t.metrics(T, grid, lb, la); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items() if k != 'worst'})
# Native-resolution detail, sheet centres.
R = []
for r in range(rows):
    for c in range(cols):
        win = Window(c*CW+CW//2-1024, r*CH+CH//2-1024, 2048, 2048)
        x = cv2.cvtColor(np.moveaxis(a.read(window=win), 0, -1), cv2.COLOR_RGB2GRAY).astype(np.float32); y = cv2.cvtColor(np.moveaxis(b.read(window=win), 0, -1), cv2.COLOR_RGB2GRAY).astype(np.float32)
        hp = lambda i: (i-cv2.GaussianBlur(i, (0, 0), 3)).std()
        R.append(hp(y)/hp(x))
print('native detail kept min %.3f median %.3f max %.3f' % (min(R), float(np.median(R)), max(R)))
Image.MAX_IMAGE_PIXELS = None
# Native-pixel crops at seam crossings and hard spots, raw above, matched below.
pts = [(CW, CH), (2*CW, CH), (CW, 2*CH), (2*CW, 2*CH), (2*CW, int(1.55*CH)), (int(1.4*CW), CH), (CW, int(2.45*CH))]
S = 330; O = Image.new('RGB', (len(pts)*(S+4), 2*S+4), 'white')
for i, (x, y) in enumerate(pts):
    for k, d in enumerate((a, b)):
        c = np.moveaxis(d.read(window=Window(x-S//2, y-S//2, S, S)), 0, -1)
        O.paste(Image.fromarray(c), (i*(S+4), k*(S+4)))
O.save('qa/final_native.png'); print(O.size)
```

### 4_st_marys/seamqa.py

Seam QA on the raw mosaic.

```python
# Seam QA on the raw lossless mosaic: leftover neatline darkening, and how far map features are offset along each seam.
import glob, numpy as np, cv2, rasterio
M = '/Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/st_marys_topos/GA_Woodbine_Fernandina_1979-81_24000_mosaic.tif'
COLS, ROWS = 5886, 6820
d = rasterio.open(M); A = np.moveaxis(d.read(), 0, -1); g = A.mean(2).astype(np.float32)
hp = lambda a: a-cv2.GaussianBlur(a.reshape(-1, 1).astype(np.float32), (1, 41), 10).ravel()
def shift(a, b, L=360, R=14):
    a = hp(a); b = hp(b); out = []
    for i in range(0, len(a)-L, L//2):
        x = a[i:i+L]; y = b[i+R:i+L-R]
        if x.std() < 4 or y.std() < 4: continue
        cc = np.array([np.corrcoef(x[k:k+len(y)], y)[0, 1] for k in range(2*R+1)])
        k = int(cc.argmax())
        if cc[k] > .5 and 0 < k < 2*R: out.append(k-R)
    return out
dips = []; al = {}
for r in range(3):
    for c in range(3):
        if c < 2:
            a = g[r*ROWS:(r+1)*ROWS]; x = (c+1)*COLS; p = a[:, x-16:x+16].mean(0)
            dips.append(float(min(p[:12].mean(), p[-12:].mean())-p[12:20].min()))
            al[f'r{r}c{c} EW-neighbours'] = shift(a[:, x-4:x-1].mean(1), a[:, x+1:x+4].mean(1))
        if r < 2:
            a = g[:, c*COLS:(c+1)*COLS]; y = (r+1)*ROWS; p = a[y-16:y+16].mean(1)
            dips.append(float(min(p[:12].mean(), p[-12:].mean())-p[12:20].min()))
            al[f'r{r}c{c} NS-neighbours'] = shift(a[y-4:y-1].mean(0), a[y+1:y+4].mean(0))
v = np.array([s for x in al.values() for s in x])
print('seams', len(dips), 'worst darkening', round(max(dips), 1), '| offset blocks', len(v), 'median %+.1f p50|s| %.1f p90|s| %.1f max|s| %d px' % (np.median(v), np.median(abs(v)), np.percentile(abs(v), 90), abs(v).max()))
```

### 5_canaveral/cfg.py

Points the color library at another block. Start here for a new one.

```python
# Point the St Marys colour library at the Cape Canaveral clips; sheet bounds come from the clips themselves.
import glob, os, sys
import rasterio
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE+'/../4_st_marys')
import tone as t
DATA = os.path.abspath(HERE+'/../../canaveral_topos')
t.LOSSLESS = DATA+'/lossless'
t.SHEETS = {}
for f in glob.glob(t.LOSSLESS+'/*.tif'):
    p = os.path.basename(f).split('_')
    with rasterio.open(f) as d:
        b = d.bounds
    t.SHEETS[int(p[2])] = dict(scan=int(p[2]), name=p[1], st=p[0], yr=int(p[3]), bbox=[round(b.left, 6), round(b.bottom, 6), round(b.right, 6), round(b.top, 6)])
```

### 5_canaveral/run1.py

The St Marys settings, unchanged.

```python
# The latest St Marys settings, unchanged, on the six Canaveral sheets.
import numpy as np, cv2, cfg
from cfg import t
from PIL import Image
T, grid, rows, cols = t.load(); base = [x['lab'] for x in T]
L = t.trim(t.stack2(T, grid, base, rows, cols, rounds=(3, 4), sigmas=((260, 180, 120), (90,)), finish=.5))
np.savez('work/final_q.npz', **{str(x['s']['scan']): l.astype(np.float32) for x, l in zip(T, L)})
V = [t.ink_guard(b, l, 3) for b, l in zip(base, L)]
print('raw', {k: round(v, 2) for k, v in t.visibility(T, grid, base).items()}); print('run', {k: round(v, 2) for k, v in t.visibility(T, grid, V).items()})
print({a: (round(b, 3) if isinstance(b, float) else b) for a, b in t.metrics(T, grid, V, base).items() if a != 'worst'})
for q in t.last_seams[:7]: print('  %-22s med %.1f p90 %.1f' % (q[2], q[0], q[1]))
print('band raw', t.band_profile(T, base)); print('band run', t.band_profile(T, V), flush=True)
G = [t.gamut_map(v) for v in V]
a = t.mosaic(T, base, rows, cols, 2); b = t.mosaic(T, G, rows, cols, 2)
S = np.full((a.shape[0], 2*a.shape[1]+24, 3), 255, np.uint8); S[:, :a.shape[1]] = a; S[:, -a.shape[1]:] = b
Image.fromarray(S).resize((1760, int(1760*S.shape[0]/S.shape[1])), Image.LANCZOS).save('qa/run1_ba.png')
Image.fromarray(b).save('qa/run1.png')
t.seam_crops(T, grid, G, rows, cols, 'qa/run1_seams.png')
```

### 5_canaveral/run2.py

Adds the water-only seam pass.

```python
# Add the water-only seam pass to the run1 result, then preview it.
import numpy as np, cfg
from cfg import t
from PIL import Image
T, grid, rows, cols = t.load(); base = [x['lab'] for x in T]
Z = np.load('work/final_q.npz'); L = [Z[str(x['s']['scan'])].astype(np.float32) for x in T]
L = t.water_pass(T, grid, L)
print({k: round(v, 2) for k, v in t.visibility(T, grid, L).items()}, {a: round(b, 3) for a, b in t.metrics(T, grid, L, base).items() if a in ('seam_med', 'seam_p90', 'land_spread', 'water_spread', 'chroma', 'detail')}, flush=True)
for q in t.last_seams[:7]: print('  %-22s med %.1f p90 %.1f' % (q[2], q[0], q[1]))
np.savez('work/final2_q.npz', **{str(x['s']['scan']): l.astype(np.float32) for x, l in zip(T, L)})
G = [t.gamut_map(t.ink_guard(b, l, 3)) for b, l in zip(base, L)]
b = t.mosaic(T, G, rows, cols, 2); Image.fromarray(b).resize((880, int(880*b.shape[0]/b.shape[1])), Image.LANCZOS).save('qa/run2.png')
t.seam_crops(T, grid, G, rows, cols, 'qa/run2_seams.png')
```

### 5_canaveral/render_block.py

Runs the renderer on this block, in its own process.

```python
# Full-resolution render of the Canaveral sheets with the St Marys renderer, in its own process so OpenCV threads never meet a fork.
import multiprocessing as mp, numpy as np, cfg, render
from cfg import t
if __name__ == '__main__':
    render.OUT = cfg.DATA+'/matched'
    T, grid, rows, cols = t.load()
    Z = np.load('work/final2_q.npz')
    jobs = [(x['s']['name'], x['f'], x['lab'], Z[str(x['s']['scan'])].astype(np.float32)) for x in T]
    with mp.get_context('fork').Pool(3) as p:
        for r in p.imap_unordered(render.one, jobs): print(r, flush=True)
```

### 5_canaveral/verify.py

Checks on the delivered Canaveral files.

```python
# Check the delivered BigTIFFs directly: format, grid, seam visibility, detail, and native-pixel crops at seam junctions.
import numpy as np, cv2, rasterio, cfg
from cfg import t
from rasterio.windows import Window
from rasterio.enums import Resampling
from PIL import Image
A = cfg.DATA+'/FL_CapeCanaveral_1976_24000_mosaic_lossless.tif'; B = cfg.DATA+'/FL_CapeCanaveral_1976_24000_mosaic_tonemapped.tif'
print('magic', open(B, 'rb').read(4), '(II+ is BigTIFF)')
a = rasterio.open(A); b = rasterio.open(B)
print(b.crs.to_string(), b.width, b.height, b.count, b.dtypes[0], b.compression.name, b.tags(ns='IMAGE_STRUCTURE').get('LAYOUT'), 'overviews', b.overviews(1))
print('same grid as raw', a.transform.almost_equals(b.transform, 1e-12) and a.shape == b.shape, '| bounds', [round(x, 4) for x in b.bounds])
CW, CH = 6036, 6816; F = 4
qa = np.moveaxis(a.read(out_shape=(3, a.height//F, a.width//F), resampling=Resampling.average), 0, -1).astype(np.float32)/255
qb = np.moveaxis(b.read(out_shape=(3, b.height//F, b.width//F), resampling=Resampling.average), 0, -1).astype(np.float32)/255
T, grid, rows, cols = t.load(); h, w = T[0]['lab'].shape[:2]
la = t.cut(T, t.rgb2oklab(qa).astype(np.float32), rows, cols, h, w); lb = t.cut(T, t.rgb2oklab(qb).astype(np.float32), rows, cols, h, w)
print('raw    ', {k: round(v, 2) for k, v in t.visibility(T, grid, la).items()})
print('matched', {k: round(v, 2) for k, v in t.visibility(T, grid, lb).items()})
m = t.metrics(T, grid, lb, la); print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items() if k != 'worst'})
print('raw spread', {k: round(v, 3) for k, v in t.metrics(T, grid, la, la).items() if 'spread' in k})
R = []
for r in range(rows):
    for c in range(cols):
        win = Window(c*CW+CW//2-1024, r*CH+CH//2-1024, 2048, 2048)
        x = cv2.cvtColor(np.moveaxis(a.read(window=win), 0, -1), cv2.COLOR_RGB2GRAY).astype(np.float32); y = cv2.cvtColor(np.moveaxis(b.read(window=win), 0, -1), cv2.COLOR_RGB2GRAY).astype(np.float32)
        hp = lambda i: (i-cv2.GaussianBlur(i, (0, 0), 3)).std()
        R.append(hp(y)/hp(x))
print('native detail kept min %.3f median %.3f max %.3f' % (min(R), float(np.median(R)), max(R)))
pts = [(CW, CH), (CW, 2*CH), (CW, CH//2), (CW, int(1.35*CH)), (int(.5*CW), CH), (int(1.5*CW), CH), (int(1.2*CW), 2*CH)]
S = 330; O = Image.new('RGB', (len(pts)*(S+4), 2*S+4), 'white')
for i, (x, y) in enumerate(pts):
    for k, d in enumerate((a, b)):
        c = np.moveaxis(d.read(window=Window(x-S//2, y-S//2, S, S)), 0, -1)
        O.paste(Image.fromarray(c), (i*(S+4), k*(S+4)))
O.save('qa/final_native.png')
ra = np.moveaxis(a.read(out_shape=(3, 1704, 1006), resampling=Resampling.average), 0, -1); rb = np.moveaxis(b.read(out_shape=(3, 1704, 1006), resampling=Resampling.average), 0, -1)
S2 = np.full((1704, 2032, 3), 255, np.uint8); S2[:, :1006] = ra; S2[:, -1006:] = rb
Image.fromarray(S2).save(cfg.DATA+'/before_after.png')
```

### 6_site_tone/blocks.py

Clusters, both match methods, stacked editions and image writing.

```python
# Tone match the site's map images one connected cluster at a time, so each region keeps its own look.
import collections, json, os, sys
import cv2, numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE+'/../4_st_marys')
import tone as t
SITE = os.path.abspath(HERE+'/../../topo_finder/site')
R = json.load(open(HERE+'/../3_finder_and_site/site_rows.json'))
OW, OH = 740, 850

def clusters():
    # Quads sharing an edge form a cluster. The shown sheet in each quad is the site's default: earliest year, then closest match.
    Q = collections.defaultdict(list)
    for r in R: Q[tuple(r['bbox'])].append(r)
    std = lambda b: abs(b[2]-b[0]-.125) < .01 and abs(b[3]-b[1]-.125) < .01
    cell = lambda b: (-round(b[3]/.125), round(b[0]/.125))
    C = {cell(b): b for b in Q if std(b)}
    seen = set(); out = []
    for c in C:
        if c in seen: continue
        st = [c]; seen.add(c); g = []
        while st:
            x = st.pop(); g.append(x)
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x[0]+d[0], x[1]+d[1])
                if n in C and n not in seen: seen.add(n); st.append(n)
        out.append(g)
    out.sort(key=len, reverse=True)
    rep = lambda b: min(Q[b], key=lambda s: (s['yr'], s['dist']))
    return out, C, Q, rep

def load_block(g, C, Q, rep):
    r0 = min(c[0] for c in g); c0 = min(c[1] for c in g)
    rows = max(c[0] for c in g)-r0+1; cols = max(c[1] for c in g)-c0+1
    T = []; grid = {}
    for c in g:
        s = rep(C[c]); f = f"{SITE}/clip8/{s['scan']}.jpg"
        a = np.asarray(Image.open(f).convert('RGB'), np.float32)/255
        x = dict(s=s, f=f, lab=t.rgb2oklab(a).astype(np.float32), rc=(c[0]-r0, c[1]-c0))
        T.append(x); grid[x['rc']] = x
    return T, grid, rows, cols

def match(T, grid, rows, cols, node=12, along=15, water=True, chroma=.965):
    # The St Marys and Canaveral chain with every distance halved, because these images are half the scale that pipeline was tuned on.
    base = [x['lab'] for x in T]; al = (.8, .6, .7, .4)
    M = t.fit_global(T, grid, order=3, lam=.005, sigma=2, depths=(2, 5, 9, 15), step=2)
    L = [t.apply_global(x, m, 3) for x, m in zip(base, M)]
    for sg, a, rounds in ((130, al, 0), (90, al, 0), (60, al, 3), (45, tuple(v*.5 for v in al), 4)):
        L, _, _ = t.dodge(T, base, L, rows, cols, sigma=sg, alpha=a)
        for _ in range(rounds):
            F = t.fit_bilateral(T, grid, L, along=along, node=node)
            L = [t.apply_bilateral(a_, f) for a_, f in zip(L, F)]
    L = t.trim(L, chroma)
    if water: L = t.water_pass(T, grid, L, along=along, node=node)
    return L

def finish(base, L, warm_area=None):
    return [t.gamut_map(t.ink_guard(b, l, 6, warm_area)) for b, l in zip(base, L)]

def to_rgb(l):
    return (np.clip(t.oklab2rgb(l), 0, 1)*255+.5).astype(np.uint8)

def match_edition(e, target, order=3, rounds=6, sigma=60, cap=.08):
    # Another edition of the same quad: fit its tones to the sheet shown on top, then remove slow drift. The cap stops changed land and labels printing through.
    s = cv2.GaussianBlur(e, (0, 0), 2)[::3, ::3].reshape(-1, 3); d = cv2.GaussianBlur(target, (0, 0), 2)[::3, ::3].reshape(-1, 3)
    F = t.phi(s, order); w = np.ones(len(F))
    for _ in range(rounds):
        M = np.linalg.lstsq(F*w[:, None], d*w[:, None], rcond=None)[0]
        w = np.sqrt(1/np.maximum(np.linalg.norm(F@M-d, axis=1), .012))
    o = t.apply_global(e, M, order)
    return o+t.gblur(np.clip(target-o, -cap, cap), sigma)

def save(s, lab):
    # Write the map image and its small copy; the rename means a stopped run never leaves half a file.
    rgb = to_rgb(lab)
    for d, im, q in (('clip8_tm', rgb, 88), ('clip_tm', cv2.resize(rgb, (170, 195), interpolation=cv2.INTER_AREA), 88)):
        p = f"{SITE}/{d}/{s['scan']}.jpg"
        Image.fromarray(im).save(p+'.tmp', 'JPEG', quality=q, optimize=True); os.replace(p+'.tmp', p)

def load_lab(s):
    return t.rgb2oklab(np.asarray(Image.open(f"{SITE}/clip8/{s['scan']}.jpg").convert('RGB'), np.float32)/255).astype(np.float32)

_classify = t.classify
def classify_wide(lab):
    # The St Marys classes, plus dark blue water, which they leave out because they were tuned on pale water.
    k = _classify(lab)
    s = cv2.GaussianBlur(lab, (0, 0), 3)
    k[(s[..., 2] < -.02) & (s[..., 1] < .012) & (s[..., 0] >= .25)] = 3
    return k

def open_water(L, cover=.4):
    # The colour of sheets that really are mostly water, so marsh tints inland can't drag the water target toward teal.
    K = [t.classify(l) for l in L]
    m = [np.median(l[k == 3], axis=0) for l, k in zip(L, K) if (k == 3).mean() >= cover]
    return np.median(np.array(m), axis=0) if len(m) >= 3 else None

def level_sheets(T, L, strength=.85, cover=.03, soft=3, water=None):
    # Shift each sheet's classes toward the cluster's typical values. This acts on whole sheets, so it stays sharp at seams, where evening's wide blur can't reach.
    K = [t.classify(l) for l in L]; meds = {}
    for i in range(len(t.CLASSES)):
        meds[i] = {j: np.median(L[j][K[j] == i], axis=0) for j in range(len(L)) if (K[j] == i).mean() >= cover}
    out = []
    for j, l in enumerate(L):
        o = l.copy()
        for i, m in meds.items():
            if j not in m or len(m) < 3: continue
            tau = np.median(np.array(list(m.values())), axis=0)
            if i == 3 and water is not None: tau = water
            w = cv2.GaussianBlur((K[j] == i).astype(np.float32), (0, 0), soft)
            o += (tau-m[j])[None, None]*strength*w[..., None]
        out.append(o)
    return out

def match_wide(T, grid, rows, cols, node=12, along=15, level=True, wide=((.30, .16), (.30, .16), (.16, .09))):
    # For clusters with big sheet-to-sheet jumps: level whole sheets first, then let early seam rounds accept pairs that disagree a lot.
    base = [x['lab'] for x in T]; al = (.8, .6, .7, .4)
    t.classify = classify_wide
    M = t.fit_global(T, grid, order=3, lam=.005, sigma=2, depths=(2, 5, 9, 15), step=2)
    L = [t.apply_global(x, m, 3) for x, m in zip(base, M)]
    w = open_water(L)
    over = {'water': w} if w is not None else None
    if level: L = level_sheets(T, L, water=w)
    for sg in (130, 90, 60):
        L, _, _ = t.dodge(T, base, L, rows, cols, sigma=sg, alpha=al, over=over)
    for lim in wide:
        F = t.fit_bilateral(T, grid, L, along=along, node=node, limits=lim)
        L = [t.apply_bilateral(a, f) for a, f in zip(L, F)]
    for _ in range(2):
        F = t.fit_bilateral(T, grid, L, along=along, node=node)
        L = [t.apply_bilateral(a, f) for a, f in zip(L, F)]
    L, _, _ = t.dodge(T, base, L, rows, cols, sigma=45, alpha=tuple(v*.5 for v in al), over=over)
    for _ in range(4):
        F = t.fit_bilateral(T, grid, L, along=along, node=node)
        L = [t.apply_bilateral(a, f) for a, f in zip(L, F)]
    L = t.water_pass(T, grid, L, along=along, node=node)
    t.classify = _classify
    mean_c = lambda X: float(np.mean([np.hypot(x[..., 1], x[..., 2]).mean() for x in X]))
    s = float(np.clip(mean_c(base)/mean_c(L), .94, 1.12))                      # return to the cluster's own saturation, rather than a fixed trim
    for x in L: x[..., 1:] *= s
    return L
```

### 6_site_tone/cluster.py

Matches one cluster in its own process.

```python
# Match one cluster plus its stacked editions and write the images. Each runs in its own process and finished clusters are skipped on a rerun.
import json, os, sys, time, numpy as np, blocks as b
from blocks import t
from PIL import Image
for d in ('clip_tm', 'clip8_tm'): os.makedirs(f'{b.SITE}/{d}', exist_ok=True)
G, C, Q, rep = b.clusters()
arg = sys.argv[1]
done = f'work/c{arg}.json'
wide = len(sys.argv) > 2 and sys.argv[2] == 'wide'
if os.path.exists(done) and not wide: print(arg, 'skip'); sys.exit()
t0 = time.time()
def stack_out(bbox, top):
    top_s = rep(bbox); n = 0
    for s in Q[bbox]:
        if s['scan'] == top_s['scan']: continue
        e = b.load_lab(s); b.save(s, t.gamut_map(t.ink_guard(e, b.match_edition(e, top), 6))); n += 1
    return n
if arg == 'rest':
    # Sheets with no neighbours have no seams, so they keep their colour; their other editions still follow them.
    inmulti = {tuple(C[c]) for g in G if len(g) > 1 for c in g}
    k = 0; n = 0
    for bbox in Q:
        if bbox in inmulti: continue
        top = b.load_lab(rep(bbox)); b.save(rep(bbox), top); n += stack_out(bbox, top); k += 1
    json.dump(dict(quads=k, editions=n, sec=round(time.time()-t0)), open(done, 'w')); print('rest', k, 'quads', n, 'editions', flush=True); sys.exit()
g = G[int(arg)]
T, grid, rows, cols = b.load_block(g, C, Q, rep); base = [x['lab'] for x in T]
raw = t.visibility(T, grid, base, off=12); rm = t.metrics(T, grid, base, base)
L = b.match_wide(T, grid, rows, cols) if wide else b.match(T, grid, rows, cols)
F = b.finish(base, L, 20 if wide else None)
v = t.visibility(T, grid, F, off=12); m = t.metrics(T, grid, F, base)
n = 0
for x, f in zip(T, F):
    b.save(x['s'], f); n += stack_out(tuple(x['s']['bbox']), f)
A = t.mosaic(T, base, rows, cols, 2); B = t.mosaic(T, F, rows, cols, 2)
S = np.full((A.shape[0], 2*A.shape[1]+24, 3), 255, np.uint8); S[:, :A.shape[1]] = A; S[:, -A.shape[1]:] = B
w = 1900 if len(g) > 8 else 1000
Image.fromarray(S).resize((w, max(1, int(w*S.shape[0]/S.shape[1]))), Image.LANCZOS).save(f'qa/c{arg}.png')
if len(t.edges(grid)) and len(g) >= 8: t.seam_crops(T, grid, F, rows, cols, f'qa/c{arg}_seams.png', size=280)
st = sorted({x['s']['st'] for x in T})
r = dict(i=int(arg), wide=wide, sheets=len(g), editions=n, states=st, raw=round(raw['ratio'], 2), raw_worst=round(raw['ratio_worst'], 2), vis=round(v['ratio'], 2), worst=round(v['ratio_worst'], 2), land=[round(rm['land_spread'], 2), round(m['land_spread'], 2)], water=[round(rm['water_spread'], 2), round(m['water_spread'], 2)], chroma=round(m['chroma'], 3), detail=round(m['detail'], 3), sec=round(time.time()-t0))
json.dump(r, open(done, 'w')); print(r, flush=True)
```

### 6_site_tone/stage_deploy.py

Builds the deploy folder from finished clusters.

```python
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
```
