# web-schedule

Season schedule generator for the Greater Peninsula Swimming Association.

Reads SwimTopia CSV exports, renders static HTML fragments, and deploys them to
**`meet-schedule.gpsaswimming.org`** (Cloudflare Pages project `gpsa-schedule`).
The published pages are embedded as iframes inside the SwimTopia **Meet Schedule**
page at `www.gpsaswimming.org/meet-schedule`.

## How it works

```
data/*.csv  ──►  build.py  ──►  dist/*.html  ──►  Cloudflare Pages  ──►  SwimTopia iframes
 (SwimTopia      (Jinja2)       (static                                  (snippets/)
  exports)                       fragments)
```

`build.py` is the entry point. It:

1. Detects the season **year** from the first date in any CSV.
2. Reads the division schedule CSVs and renders the single tabbed `schedule.html`
   (All Divisions / Red / White / Blue / Invitationals).
3. Derives the division **rosters** automatically from the teams appearing in the
   schedule CSVs (no separate roster list to maintain).
4. Renders the rosters and teams quick-access pages.
5. Writes everything to `dist/` (git-ignored; rebuilt on each deploy).

Team display names and roster-link slugs live in the `TEAM_MAP` dictionary at the
top of `build.py` — update it there when a team's name or SwimTopia roster URL
changes. Aliased abbreviations (e.g. `BLMAR`/`BLMR`) are deduplicated by name.

## Layout

| Path | Purpose |
|---|---|
| `build.py` | Build script — CSV → HTML. Run `python build.py`. |
| `data/` | SwimTopia CSV exports: `red.csv`, `white.csv`, `blue.csv`, `invitationals.csv`. |
| `templates/` | Jinja2 templates, one per output page (see below). |
| `snippets/` | The iframe embed code pasted into SwimTopia (see below). |
| `legacy/` | Prior/reference material, not part of the build. |
| `dist/` | Build output (git-ignored). |
| `.github/workflows/` | CI: builds and deploys to Cloudflare Pages on push to `main`. |

### Templates → output pages

| Template | Output | Embedded as |
|---|---|---|
| `schedule.html.j2` | `schedule.html` | Tabbed schedule: All Divisions / Red / White / Blue / Invitationals (with live scores + result links) |
| `divisions.html.j2` | `divisions.html` | Rosters grid (Red/White/Blue + Roster Formatting Tool link) |
| `teams.html.j2` | `teams.html` | Teams quick-access anchors |

Each template pulls shared styling from the CSS CDN
(`css.gpsaswimming.org`) and loads the iframe-resizer content-window script so the
embedding page can auto-size each frame.

## Live scores on the schedule

The division schedule tables show each dual meet's final **score** and a **link to
the results**, fetched live from the results site. This is a cross-repo integration:

- **Source of data:** the `web-results` repo publishes a per-season feed at
  `https://results.gpsaswimming.org/<year>/scores.json` (one record per swum meet:
  date, team display names, scores, and the result-page URL).
- **How it's joined:** `schedule.html.j2` stamps each meet row with
  `data-date` / `data-home` / `data-visitor`, then a small inline script fetches the
  feed and matches on `date` + the (unordered) pair of **display names**. Scores are
  placed by name, so a flipped home/away orientation still renders correctly. The
  winner's score is bold + GPSA navy, the loser's muted gray.
- **Click a team name** to highlight all of that team's rows on the page (toggle off
  by clicking again).
- Meets with no entry in the feed (not yet swum) simply render blank score/result
  cells; a missing or unreachable feed fails silently, so the schedule always renders.

No build-time coupling — `build.py` needs no access to the results repo; the join
happens client-side in the browser. CORS is permitted by a `_headers` file in
`web-results` scoped to this site's origin.

## The tabbed schedule page

`schedule.html` is a **single page** with a tabbed view:
**All Divisions** (default) · Red · White · Blue · Invitationals. It uses Tailwind
(matching the results-archive pages), renders a **desktop table / mobile cards**, fills
in each meet's score + result link from the scores feed (see above), offers a
**team filter** (current-season teams only) on the All Divisions tab, and lets you
**click a team name** to highlight its rows. Tabs are deep-linkable:
`schedule.html#blue` opens the Blue tab.

## Build & deploy

Local build:

```bash
pip install -r requirements.txt
python build.py          # output in dist/
```

Deploy is automatic: pushing to `main` triggers
`.github/workflows/` → builds `dist/` → `cloudflare/pages-action@v1` publishes to
the `gpsa-schedule` Cloudflare Pages project. To update the live site, drop fresh
CSV exports in `data/`, commit, and push.

## Updating for a new season

1. Export the division and invitationals schedules from SwimTopia as CSVs.
2. Replace the files in `data/` (`red.csv`, `white.csv`, `blue.csv`, `invitationals.csv`).
3. If any team names or roster URLs changed, update `TEAM_MAP` in `build.py`.
4. Commit and push to `main` — the year auto-updates from the CSV dates.

## SwimTopia embed code

The published pages are surfaced on the SwimTopia Meet Schedule page via iframes.
This block lives in SwimTopia's page HTML (not in this repo's build output) — it is
kept here in `snippets/swimtopia-embed.html` as the source of truth. Paste it into
the SwimTopia content editor. The `<div>` anchors (`#top`, `#schedule`) are the targets
for the in-page jump links; the per-division navigation is handled by the tabs inside
`schedule.html` (deep-linkable as `schedule.html#red` etc.).

```html
<!-- iframe-resizer (load once) -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/iframe-resizer/4.3.9/iframeResizer.min.js"></script>

<!-- ROSTERS / DIVISIONS -->
<div id="top"></div>
<iframe
    src="https://meet-schedule.gpsaswimming.org/divisions.html"
    style="width: 100%; border: none; overflow: hidden;"
    scrolling="no"
    id="gpsa-divisions">
</iframe>

<!-- MEET SCHEDULE (tabbed: All Divisions / Red / White / Blue / Invitationals) -->
<div id="schedule"></div>
<iframe
    src="https://meet-schedule.gpsaswimming.org/schedule.html"
    style="width: 100%; border: none; overflow: hidden;"
    scrolling="no"
    id="gpsa-schedule">
</iframe>

<!-- Initialize all iframes -->
<script>
iFrameResize({
    log: false,
    checkOrigin: false,
    heightCalculationMethod: 'lowestElement',
    resizeFrom: 'child'
}, 'iframe[id^="gpsa-"]');
</script>
```

### Teams quick-access (optional, separate page)

The `teams.html` page is embedded on its own via `snippets/teams-snippet.html`:

```html
<!-- TEAMS QUICK ACCESS -->
<iframe
    src="https://meet-schedule.gpsaswimming.org/teams.html"
    style="width: 100%; border: none; overflow: hidden;"
    scrolling="no"
    id="gpsa-teams">
</iframe>
<script src="https://cdnjs.cloudflare.com/ajax/libs/iframe-resizer/4.3.9/iframeResizer.min.js"></script>
<script>iFrameResize({ log: false, checkOrigin: false, heightCalculationMethod: 'lowestElement', resizeFrom: 'child' }, '#gpsa-teams');</script>
```
