# Israel Airspace

A live airspace map for pilots in Israel: your GPS position, CTRs/TMAs, prohibited/restricted/danger areas,
NOTAMs with their real active times, the sport-aviation bubbles and routes (weekday vs weekend), CVFR routes,
paraglider launch sites, a side view of what is ahead of you, and export to KML / KMZ / OpenAir / GeoJSON.

**Informational only — always check the official AIP and NOTAMs before flight.**

## Run it on your computer
```
pip install -r requirements.txt     # PyMuPDF, for the domestic AIP PDF
python3 serve.py                    # http://localhost:8765, refreshes NOTAMs every 10 min
```
The first run downloads the domestic AIP (~95 MB) and parses it (~2 min). Later runs take a few seconds.

* `python3 serve.py --lan` — also open it from a phone on the same Wi-Fi. Phones only give GPS to HTTPS pages,
  so for GPS use `--cert/--key` (e.g. certificates from `mkcert`) or the hosted option below.
* `python3 update.py` — just rebuild `web/data.json` (`--force` re-parses everything).
* Your own airspace: drop OpenAir / GeoJSON / KML files in `data/custom/`, or import them in the app (Export tab).

## Use it on your phone, anywhere (GitHub Pages)
The site is published from the `gh-pages` branch. Open it on the phone and "Add to Home Screen"; it works offline
with the last data it loaded (the app shows how old the data is).

* Publish fresh data from your computer: `python3 publish.py`
* Fully automatic updates every 30 minutes (no computer needed): copy `deploy/github-pages.yml` to
  `.github/workflows/pages.yml` (GitHub web UI → Add file, or push with a token that has the `workflow` scope),
  then set **Settings → Pages → Source: GitHub Actions**.

If the IAA site ever blocks GitHub's servers, the Data section in the app shows the NOTAM source as failed and keeps
the last good data; run `serve.py` at home instead.

## Live traffic
The **Live traffic** layer shows aircraft in the air near you, filtered to your profile heights (or all altitudes):
* ADS-B (airliners, GA, helicopters, some ultralights) from community receivers — adsb.fi, fallback adsb.lol.
* FLARM / OGN / FANET trackers (gliders, paragliders, hang gliders, tow planes) from the Open Glider Network.
* Drones: no public live source exists (Remote ID is local radio only). Drone activity shows through NOTAMs and drone areas.

These services do not allow direct use from a web page, so the app reads them through a relay:
* **On your computer:** `python3 serve.py` already includes it (ADS-B + OGN).
* **On the phone (hosted site):** deploy `deploy/traffic-worker.js` as a free Cloudflare Worker (instructions at the top of the
  file) and paste its URL into the app: More → Live traffic → Traffic relay URL. This relays ADS-B; OGN needs `serve.py`.

Coverage is partial and positions can lag; never use it for separation.

## Where the data comes from
| Data | Source | Refresh |
|---|---|---|
| NOTAMs (shape, heights, active times, schedule) | brin.iaa.gov.il NOTAM list + per-NOTAM ICAO detail | every run; each NOTAM downloaded once |
| CTR, TMA, P/R/D areas | eAIP Israel (e-aip.azurefd.net): ENR 2.1, ENR 5.1, AD 2.17 | when a new AIRAC cycle is published |
| LLD danger areas, LLU no-fly circles, balloons, VFR reporting points | Domestic AIP (gov.il "פמ"ת מלא" PDF) tables | when a new amendment is published (checked daily) |
| Sport bubbles & routes (midweek / weekend), CVFR routes, CTRs / ATZs of IAF bases and aerodromes | Domestic AIP charts B-08 and B-03, read from the vector drawing and georeferenced | same |
| Paragliding takeoffs (with wind directions), landing fields | OpenStreetMap via Overpass (© OpenStreetMap contributors, ODbL) | weekly |

Chart-derived shapes are accurate to roughly 100–400 m (1:250,000 chart). NOTAMs without an exact shape are drawn
from their Q-line reference circle and marked "approximate"; ultralight-bubble closures are re-drawn on the actual
bubbles they name.

## Using the map
* Profiles (Paraglider, PPG, Ultralight, GA, Drone) pick the layers and height band; adjust heights under Layers.
* Clutter control: routes, small no-fly circles and points appear only as you zoom in; NOTAMs without an exact
  shape show as small **N** pins (switch them to circles under Layers).
* Tap a zone for details, double-click / long-press to zoom to it. The ☰ / chevron buttons hide and show the panel;
  the layers button switches Day / Night / Satellite / Auto.
* Takeoffs show a wind rose: the blue sectors are the wind directions the site works in.

## Files
```
update.py            data pipeline -> web/data.json
serve.py             local server + periodic refresh
sources/             notam.py, eaip.py, domestic.py, charts.py, osm_sites.py, custom.py, geometry.py
web/                 the app (index.html, app.js, style.css, sw.js, manifest)
```
