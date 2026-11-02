# Topo scripts

Everything used to clip, stitch and tone-match the USGS topos and to build the Orthophoto-topos site. The method is explained in [NEATLINE_CROP_AND_STITCH.md](../NEATLINE_CROP_AND_STITCH.md).

These are working scripts, kept as they ran. Paths are hard-coded to this machine (`~/Dropbox/freelance/pretty_topo_browser_and_tiler`), and several are per-dataset copies rather than one configurable tool.

File name prefixes:

- No prefix or `fl_`: Cape Canaveral
- `la_`: Louisiana
- `nw_`: NW Florida

The `la_` and `nw_` versions of a clip or measure script differ only in the sheet folder they read and the output size per quad.

## Setup

Python 3 with `numpy`, `scipy`, `rasterio`, `pyproj`, `opencv-python`, `Pillow`, `tifffile` and `psd-tools`.

The mosaic steps use QGIS's GDAL, in `/Applications/QGIS.app/Contents/MacOS`. Set these first:

```bash
export PROJ_DATA=/Applications/QGIS.app/Contents/Resources/qgis/proj
export GDAL_DATA=/Applications/QGIS.app/Contents/Resources/qgis/gdal
```

The tone step needs Adobe Photoshop 2026, driven through `osascript`.

## 1_clip_and_stitch

Run from inside the folder holding the sheet folders, for example `~/Dropbox/freelance/pretty_topo_browser_and_tiler/nw_fl_topos`.

| Order | Script | What it does |
|---|---|---|
| 1 | `nw_meta.py` | Lists each sheet's size, datum and quad cell |
| 2 | `nw_preview.py <qa dir>` | Makes a sheet layout and corner crops to check by eye |
| 3 | `nw_measure.py nw_neatline.json` | Measures the printed neatline on every edge |
| 4 | `nw_clip.py nw_neatline.json <out dir> 1.5 deflate` | Writes the lossless clips |
| 5 | `nw_clip.py nw_neatline.json clipped 1.5 jpeg` | Writes the JPEG clips |
| 6 | `gdalbuildvrt`, `gdal_translate` | Builds the mosaic; commands are in the method doc |
| 7 | `nw_qa.py <dir>` | Checks the mask and seams |

`nw_clip.py` takes an optional sheet name as a last argument, to do one sheet at a time.

The measured neatline curves are saved here as `neatline.json`, `la_neatline.json` and `nw_neatline.json`.

## 2_psd_and_tone

| Order | Script | What it does |
|---|---|---|
| 1 | `build_psd.py <clipped> "<source glob>" <out> <merged or blank> <tmp dir>` | Writes the layered PSD or PSB directly, one group per sheet with a Selective Color layer |
| 2 | `check_psd.py <file> <clipped> full` | Reads it back and compares pixels with the clips |
| 3 | `segment.py`, `segment_la.py`, `segment_nw.py` | Builds the water and land masks for each set |
| 4 | `fit.py`, `fit_la.py`, `fit_nw.py` | Fits slider values toward the median of the tiles |
| 5 | `ps_apply.py <sliders> <doc> <tif> <jsx>` | Generates the Photoshop script that sets the sliders |
| 6 | `verify.py` | Measures Photoshop's real render against the targets |
| 7 | `ps_save.jsx`, `la_save.jsx`, `nw_save.jsx` | Saves the document through Photoshop |
| 8 | `la_rgba.py`, `nw_rgba.py` | Georeferences the render for the matched mosaic |
| 9 | `*_final*.py` | Reads the finished files back |

`sc.py` holds the Selective Color model the fit and verify steps share. The final slider values are saved as `fl_sliders.json`, `la_sliders.json` and `nw_sliders.json`.

The segmentation masks (`seg_*.pkl`) aren't included because they total about 800 MB. Rerun step 3 to rebuild them.

`fit_nw.py` weights water 3× and clearings at half, which is what stopped land from pulling water colors off target.

## 3_finder_and_site

| Order | Script | What it does |
|---|---|---|
| 1 | `scan.py` | Lists candidate sheets from the TNM API and scores every thumbnail |
| 2 | `rank.py` | Applies the color filter and writes the CSV |
| 3 | `site_data.py` | Adds topoView IDs and colors |
| 4 | `georef.py`, `clip_thumbs.py` | Reads GeoTIFF headers and clips the small map images |
| 5 | `holes.py`, `holes2.py`, `add_map.py` | Finds enclosed blanks and adds matching sheets |
| 6 | `hires.py 6` | Reads the 1/8 overviews; safe to rerun, it skips finished sheets |
| 7 | `hires_check.py` | Verifies them against the thumbnails and flags them for the site |

`tnm.py` and `hue.py` are shared helpers: the TNM API client and the thumbnail color score.

To change the sheet list later:

```bash
python3 strike.py 'Cleveland|OK|1966' 705634
```

That removes sheets by `Name|ST|Year` or scan ID, deletes their map images, updates the CSV and URL list, and bumps the site's version tags. Running it with no arguments just rebuilds those files.

To add reviewed sheets, put their GeoTIFF URLs in a JSON list, then run:

```bash
python3 add_urls.py list.json && python3 hires.py 6 && python3 hires_check.py && python3 strike.py
```

Both of these rely on `site_rows.json`, the master list of sheets. `scan.pkl` keeps the scored thumbnails, and `add_urls.py` needs a URL to be in it. `strike.py` doesn't rebuild the contact sheet PNG.

The `ORTHOPHOTO` flag can't be read by script. topoView only answers from its own pages, so `flags.txt` holds the results copied out of a browser tab.

## 4_st_marys

The 9-sheet St Marys block: neatline stitch to BigTIFF, then tone mapping. The method, iteration log and known limits are in [the St Marys section](../NEATLINE_CROP_AND_STITCH.md#st-marys-block-stitch-and-tone-match).

| Order | Script | What it does |
|---|---|---|
| 1 | `measure.py neatline.json` | Measures the printed neatlines |
| 2 | `clip.py neatline.json <out dir> 1.5 <deflate or jpeg> 5886 6820` | Writes the clips |
| 3 | `gdalbuildvrt`, `gdal_translate` | Builds the raw BigTIFF |
| 4 | `run9.py` | The color build; writes `work/final_q.npz` |
| 5 | `render.py` | Applies it at full resolution to `matched/` |
| 6 | `gdalbuildvrt`, `gdal_translate` | Builds the matched BigTIFF |
| 7 | `verify.py`, `seamqa.py` | Checks the delivered files |

Run steps 4 to 7 from inside this folder, because `work/` and `qa/` are relative paths.

`tone.py` is the shared library. `sheets.json` holds the sheet list, including the quad bounds. `run1.py` to `run8.py`, `diag.py` and `diag2.py` are the iteration history and were written against earlier states of `tone.py`, so they may not reproduce those results.

## 5_canaveral

The 6 Cape Canaveral sheets, tone mapped with the library in `4_st_marys`. The log is in [its section](../NEATLINE_CROP_AND_STITCH.md#cape-canaveral-tone-match).

| Order | Script | What it does |
|---|---|---|
| 1 | `cfg.py` | Not run directly: points the library at this block's clips, reading bounds from the files |
| 2 | `run1.py` | The St Marys settings, unchanged; writes `work/final_q.npz` |
| 3 | `run2.py` | Adds the water-only seam pass; writes `work/final2_q.npz` |
| 4 | `render_block.py` | Full-resolution render from `work/final2_q.npz` |
| 5 | `gdalbuildvrt`, `gdal_translate` | Builds the two mosaics |
| 6 | `verify.py` | Checks the delivered files |

Run from inside this folder.

## Tone mapping a new block

1. Save lossless clips first, in a permanent folder.
2. Copy `5_canaveral`, and change `DATA` in `cfg.py`.
3. Run `run1.py` unchanged and look at the seam crops in `qa/`.
4. If water steps remain at seams, run `run2.py`. If not, point `render_block.py` at `work/final_q.npz`.
5. Render, build the BigTIFFs, and set `CW`, `CH` and the file names in `verify.py`.
6. Check the native-pixel crops in `qa/final_native.png` by eye. Numbers have passed real defects here.

Run the color build and render as separate processes. Forking after OpenCV has run threads crashes on macOS. Lessons behind these steps are under [Learnings](../NEATLINE_CROP_AND_STITCH.md#learnings).

## 6_site_tone

Tone maps the site's map images one connected cluster at a time. The log is in [its section](../NEATLINE_CROP_AND_STITCH.md#site-images-cluster-matching).

| Order | Script | What it does |
|---|---|---|
| 1 | `blocks.py` | Not run directly: clusters, `match`, `match_wide`, stacked editions |
| 2 | `cluster.py <n>` | Matches cluster `n` and writes its images; finished clusters are skipped |
| 3 | `cluster.py rest` | Handles lone sheets and their other editions |
| 4 | `cluster.py <n> wide` | Reruns one cluster with `match_wide` |
| 5 | `stage_deploy.py <folder>` | Builds the deploy folder from finished clusters |

`all.sh` runs everything in order, and `rerun.sh` shows a wide rerun. Each cluster runs in its own process. `test.py <n>` tries one cluster without writing images, `test_fl.py` tries part of Florida, `stage.py` scores a cluster after each step, and `og_image.py` cuts the social preview.

Run from inside this folder. After changing the sheet list, delete the marker in `work/` for any cluster it affects and rerun that cluster.

**Deploy through `stage_deploy.py`, not from `topo_finder/site`.** Deploying that folder directly publishes the original images plus both `_tm` folders.

```bash
python3 -W ignore stage_deploy.py /tmp/prettytopos
npx wrangler pages deploy /tmp/prettytopos --project-name prettytopos --branch main --force
```

## Site

The site itself is in `../topo_finder/site`. To run it locally:

```bash
cd ~/Dropbox/freelance/pretty_topo_browser_and_tiler/topo_finder/site && python3 -m http.server 8642
```
