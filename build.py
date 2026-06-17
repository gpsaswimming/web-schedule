#!/usr/bin/env python3
"""
Build script for GPSA Meet Schedule site.
Reads SwimTopia CSV exports from data/, renders HTML schedule pages, outputs to dist/.

Expected files in data/:
  - red.csv, white.csv, blue.csv  (division dual meet schedules)
  - invitationals.csv              (league-wide invitationals)

Division rosters are derived automatically from the schedule CSVs.
Team metadata (display names, roster URL slugs) lives in TEAM_MAP below.

Run: python build.py
"""

import csv
import shutil
from datetime import datetime
from pathlib import Path

import jinja2

# Team abbreviation → display name, roster URL slug, and teams page anchor
# Roster URLs follow the pattern: https://www.gpsaswimming.org/{roster}
# Anchors match the SwimTopia teams page section IDs
TEAM_MAP = {
    "BLMAR": {"name": "Beaconsdale",   "roster": "roster-beaconsdale-blue-marlins",              "anchor": "Beaconsdale"},
    "BLMR":  {"name": "Beaconsdale",   "roster": "roster-beaconsdale-blue-marlins",              "anchor": "Beaconsdale"},
    "COL":   {"name": "Colony",         "roster": "roster-colony-cudas",                          "anchor": "Colony"},
    "CV":    {"name": "Coventry",       "roster": "roster-coventry-sailfish",                     "anchor": "Coventry"},
    "EL":    {"name": "Elizabeth Lake", "roster": "roster-elizabeth-lake-tideriders",              "anchor": "Elizabeth_Lake"},
    "GWRA":  {"name": "Wythe",          "roster": "roster-george-wythe-recreation-association",   "anchor": "Wythe"},
    "GG":    {"name": "Glendale",       "roster": "roster-glendale-gators",                       "anchor": "Glendale"},
    "HW":    {"name": "Hidenwood",      "roster": "roster-hidenwood-tarpons",                     "anchor": "Hidenwood"},
    "JRCC":  {"name": "James River",    "roster": "roster-james-river-river-ratz",                "anchor": "James_River"},
    "KCD":   {"name": "Kiln Creek",     "roster": "roster-kiln-creek-dolphins",                   "anchor": "Kiln_Creek"},
    "MBKMT": {"name": "Marlbank",       "roster": "roster-marlbank-mudtoads",                     "anchor": "Marlbank"},
    "NHM":   {"name": "Northampton",    "roster": "roster-northampton",                           "anchor": "Northampton"},
    "POQ":   {"name": "Poquoson",       "roster": "roster-poquoson-barracudas",                   "anchor": "Poquoson"},
    "RRST":  {"name": "Riverdale",      "roster": "roster-riverdale-rays",                        "anchor": "Riverdale"},
    "RMMR":  {"name": "Running Man",    "roster": "roster-running-man-manta-rays",                "anchor": "Running_Man"},
    "VG":    {"name": "Village Green",  "roster": "roster-village-green-patriots",                 "anchor": "Village_Green"},
    "WW":    {"name": "Wendwood",       "roster": "roster-wendwood-wahoos",                       "anchor": "Wendwood"},
    "WO":    {"name": "Willow Oaks",    "roster": "roster-willow-oaks-sting-rays",                "anchor": "Willow_Oaks"},
    "WPPIR": {"name": "Windy Point",    "roster": "roster-windy-point-piranhas",                  "anchor": "Windy_Point"},
    "WYCC":  {"name": "Warwick Yacht",  "roster": "roster-warwick-yacht-sea-turtles",             "anchor": "Warwick_Yacht"},
    "WYTHE": {"name": "Wythe",          "roster": "roster-wythe-wahoos",                          "anchor": "Wythe"},
}

ROSTER_BASE_URL = "https://www.gpsaswimming.org"

DIVISIONS = ["red", "white", "blue"]


def parse_date(date_str):
    """Parse SwimTopia date format (M/D/YYYY) into a datetime object."""
    return datetime.strptime(date_str.strip(), "%m/%d/%Y")


def format_date_header(dt):
    """Format datetime as 'MONDAY JUNE 16'."""
    return f"{dt.strftime('%A').upper()} {dt.strftime('%B').upper()} {dt.day}"


def team_name(abbr):
    """Resolve team abbreviation to display name."""
    entry = TEAM_MAP.get(abbr.strip())
    return entry["name"] if entry else abbr.strip()


def team_roster_url(abbr):
    """Resolve team abbreviation to full roster URL."""
    entry = TEAM_MAP.get(abbr.strip())
    if entry:
        return f"{ROSTER_BASE_URL}/{entry['roster']}"
    return None


def team_anchor(abbr):
    """Resolve team abbreviation to teams page anchor slug."""
    entry = TEAM_MAP.get(abbr.strip())
    return entry["anchor"] if entry else abbr.strip()


def extract_teams_from_csv(path):
    """Extract unique team abbreviations from a division CSV, deduplicated by name."""
    abbrs = set()
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            abbrs.add(row["HomeTeam"].strip())
            abbrs.add(row["VisitingTeam"].strip())
    # Deduplicate aliases (e.g. BLMAR and BLMR both → Beaconsdale)
    seen_names = {}
    for a in abbrs:
        name = team_name(a)
        if name not in seen_names:
            seen_names[name] = a
    return sorted(seen_names.values(), key=lambda a: team_name(a))


def load_division_meets(path, division):
    """Load a division CSV into a flat, chronological list of meet dicts.

    Each meet carries its division (for the "All Divisions" badge) and an ISO date
    (the join key for the client-side scores feed — see schedule.html.j2).
    """
    meets = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = parse_date(row["MeetDate"])
            meets.append({
                "division": division,
                "sort_key": dt,
                "iso_date": dt.strftime("%Y-%m-%d"),
                "date": format_date_header(dt),
                "home": team_name(row["HomeTeam"]),
                "visitor": team_name(row["VisitingTeam"]),
            })
    meets.sort(key=lambda m: m["sort_key"])
    return meets


def group_by_date(meets):
    """Group a flat chronological meet list into per-date groups.

    The template shows the date once per group on desktop (via loop.first) and on
    every card on mobile.
    """
    by_date = {}
    for m in meets:
        by_date.setdefault(m["sort_key"], []).append(m)
    return [
        {"date": format_date_header(dt), "meets": by_date[dt]}
        for dt in sorted(by_date)
    ]


def load_invitationals_csv(path):
    """Load invitationals CSV and return events sorted by date."""
    events = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = parse_date(row["MeetDate"])
            events.append({
                "date": format_date_header(dt),
                "name": row["MeetName"].strip(),
                "location": row.get("Location", "").strip(),
                "sort_key": dt,
            })

    events.sort(key=lambda e: e["sort_key"])
    return events


def detect_year(data_dir):
    """Detect season year from the first date found in any CSV."""
    for path in sorted(data_dir.glob("*.csv")):
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                return parse_date(row["MeetDate"]).year
    return datetime.now().year


def build():
    dist = Path("dist")
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir()

    data_dir = Path("data")

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader("templates"),
        autoescape=jinja2.select_autoescape(["html"]),
    )

    year = detect_year(data_dir)

    # Load each division's meets and collect rosters (rosters feed divisions.html / teams.html)
    division_schedules = []   # per-division tab data for the schedule page
    all_meets = []            # every dual meet, for the "All Divisions" tab
    division_rosters = {}

    for division in DIVISIONS:
        csv_path = data_dir / f"{division}.csv"
        if not csv_path.exists():
            print(f"  Skipping {division} (no {csv_path})")
            continue

        # Extract teams for roster pages (divisions.html / teams.html)
        team_abbrs = extract_teams_from_csv(csv_path)
        division_rosters[division] = [
            {"name": team_name(a), "url": team_roster_url(a), "anchor": team_anchor(a)}
            for a in team_abbrs
        ]

        meets = load_division_meets(csv_path, division)
        all_meets.extend(meets)
        division_schedules.append({
            "key": division,
            "title": division.capitalize(),
            "date_groups": group_by_date(meets),
        })

    # Invitationals data (its own tab; rendered inline on the schedule page)
    inv_path = data_dir / "invitationals.csv"
    events = load_invitationals_csv(inv_path) if inv_path.exists() else []

    # Combined "All Divisions" view: chronological, then by division order, then home team
    div_order = {d: i for i, d in enumerate(DIVISIONS)}
    all_meets.sort(key=lambda m: (m["sort_key"], div_order.get(m["division"], 99), m["home"]))
    all_groups = group_by_date(all_meets)

    # Team filter options for the "All Divisions" tab — unique display names, sorted
    teams = sorted({m["home"] for m in all_meets} | {m["visitor"] for m in all_meets})

    # Build the single tabbed schedule page
    schedule_template = env.get_template("schedule.html.j2")
    output = schedule_template.render(
        year=year,
        all_groups=all_groups,
        division_schedules=division_schedules,
        events=events,
        teams=teams,
    )
    (dist / "schedule.html").write_text(output)
    print(f"  Built schedule.html ({len(all_meets)} meets, {len(division_schedules)} divisions, "
          f"{len(events)} invitationals, {len(teams)} teams)")

    # Build divisions (rosters) page from CSV-derived teams
    if division_rosters:
        divisions_template = env.get_template("divisions.html.j2")
        output = divisions_template.render(
            divisions=[division_rosters.get(d, []) for d in DIVISIONS],
            year=year,
        )
        out_path = dist / "divisions.html"
        out_path.write_text(output)
        print(f"  Built {out_path.name}")

    # Build teams page (quick access anchors) from CSV-derived teams
    if division_rosters:
        teams_template = env.get_template("teams.html.j2")
        output = teams_template.render(
            divisions=[division_rosters.get(d, []) for d in DIVISIONS],
            year=year,
        )
        out_path = dist / "teams.html"
        out_path.write_text(output)
        print(f"  Built {out_path.name}")

    # Copy CNAME if present
    if Path("CNAME").exists():
        shutil.copy2("CNAME", dist / "CNAME")

    print(f"\nDone — output in {dist}/")


if __name__ == "__main__":
    build()
