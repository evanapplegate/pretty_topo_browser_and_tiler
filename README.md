# Pretty topo browser and tiler

Tools for finding, stitching and color matching USGS orthophoto-topos: 1:24k maps from the '70s and early '80s that overlay green ink for land and blue for water on aerial imagery.

- **Browser:** [`topo_finder/site`](topo_finder/site) is a static site with a globe of 880 sheets stitched into place, a contact sheet, and a drag-a-box tool that downloads a list of GeoTIFF URLs to `curl`.
- **Tiler:** [`scripts`](scripts/README.md) clips sheets at their printed neatlines, stitches them to BigTIFF and matches color across sheets.

## Docs

- [NEATLINE_CROP_AND_STITCH.md](NEATLINE_CROP_AND_STITCH.md): the full method, results, iteration log and learnings, with the key scripts in full.
- [scripts/README.md](scripts/README.md): setup and run order.

## Layout

| Path | What's there |
|---|---|
| `topo_finder/site/` | The site: `index.html`, `app.js`, `sheets.js` |
| `topo_finder/` | The sheet list as CSV and a list of GeoTIFF URLs |
| `scripts/1_clip_and_stitch/` | Neatline measuring, clipping, seam checks |
| `scripts/2_psd_and_tone/` | Layered PSD/PSB building and Selective Color matching |
| `scripts/3_finder_and_site/` | The thumbnail color scan and the site's data and images |
| `scripts/4_st_marys/` | The 9-sheet BigTIFF stitch and the tone-mapping library |
| `scripts/5_canaveral/` | The same tone mapping on a water-heavy block, and the template for new blocks |

## What isn't here

Everything heavy is left out by [`.gitignore`](.gitignore), about 21 GB in all: source sheets, clips, mosaics, PSD/PSB files, QA images, caches and the site's map images.

The source sheets are public USGS downloads, and their URLs are in `topo_finder/blue_green_image_topos.csv`. To run the site, rebuild its images first with `clip_thumbs.py` and `hires.py` from `scripts/3_finder_and_site/`, which write `clip/` and `clip8/` from data already in this repo.

Paths in the scripts are hard-coded to one machine, so expect to change them.

## Run the site locally

```bash
cd topo_finder/site && python3 -m http.server 8642
```

The map uses Mapbox GL JS with a public token in `app.js`. Swap in your own token and style if you fork this.
