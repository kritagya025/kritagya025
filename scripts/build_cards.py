#!/usr/bin/env python3
"""Generate the full stack of animated SVG profile cards into cards/.

Cards are designed to be shown via <img> tags in the README, so every
animation uses only techniques that survive the GitHub img sanitiser:

  • inline <style> blocks with CSS @keyframes
  • SMIL <animate> / <animateTransform> elements
  • fonts subset with pyftsubset and embedded as base64 WOFF data URIs

All animations respect prefers-reduced-motion: reduce by freezing at the
final frame.  Set STATIC=1 to render the final-frame version for
screenshots.

Contribution data is read from data/contributions.json (refreshed daily
by a GitHub Action) so the script never hits the network at render time.

    GITHUB_USERNAME=kritagya025 python scripts/build_cards.py

Environment:
    GITHUB_USERNAME   GitHub handle (default: kritagya025)
    GITHUB_TOKEN      optional, raises API rate limits
    STATIC            set to "1" to render the last frame (no animation)
    FEATURED_REPOS    comma-separated repo names to feature
                      (default: KeyVault,Event-Booking-System,
                       URL_SHORTNER-LinkPluse-,student-management,
                       Expense-Tracker,disaster-coordination-system)
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import urllib.request

# ---------------------------------------------------------------- config
USER = os.environ.get("GITHUB_USERNAME") or "kritagya025"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
STATIC = os.environ.get("STATIC", "") == "1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS = os.path.join(ROOT, "cards")
DATA = os.path.join(ROOT, "data")

FEATURED_REPOS = [
    r.strip()
    for r in os.environ.get(
        "FEATURED_REPOS",
        "KeyVault,Event-Booking-System,URL_SHORTNER-LinkPluse-,"
        "student-management,Expense-Tracker,disaster-coordination-system",
    ).split(",")
    if r.strip()
]

LANG_COLOURS = {
    "Java": "#b07219",
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "C++": "#f34b7d",
    "C": "#555555",
    "Jupyter Notebook": "#DA5B0B",
    "Shell": "#89e051",
    "Dockerfile": "#384d54",
    "SCSS": "#c6538c",
}

# ------------------------------------------------------------ palette
# Matches the existing wolf-eye-cyan brand from build_profile.py
INK = "#05070D"
BASE = "#0A1128"
PANEL = "#0E1830"
GRID = "#14213D"
LINE = "#1B3A6B"
CYAN = "#4FC3F7"
DIM = "#2C6E9E"
ICE = "#A8E4FF"
TEXT = "#E8F1FA"
SUB = "#9DB4CE"
MUTED = "#5F7796"

HEAT = [PANEL, "#17415F", "#216E96", "#2C9BCB", CYAN]

MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

W = 1000  # all cards are 1000 units wide

# Stagger offsets — each card's animations begin after a base delay (s)
# so the page plays top-to-bottom as it loads
STAGGER = {
    "hero": 0.0,
    "links": 0.5,
    "chart": 1.0,
    "repo": 1.5,  # per-repo cards share a base; each offsets by index
    "trail": 2.5,
}


# ------------------------------------------------------------ data layer
def _get(url: str, headers: dict | None = None, raw: bool = False):
    h = {"User-Agent": "kritagya025-profile"}
    if headers:
        h.update(headers)
    if TOKEN:
        h["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    return data.decode("utf-8", "replace") if raw else json.loads(data.decode("utf-8"))


def fetch_contributions() -> list[list[dict]]:
    """Scrape the public contribution calendar HTML."""
    html = _get(
        f"https://github.com/users/{USER}/contributions",
        {"Accept": "text/html"},
        raw=True,
    )
    cells = re.findall(
        r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="(contribution-day-component-\d+-\d+)"'
        r'[^>]*data-level="(\d)"',
        html,
    )
    tips = dict(
        re.findall(
            r'for="(contribution-day-component-\d+-\d+)"[^>]*>([^<]*)</tool-tip>',
            html,
        )
    )
    if not cells:
        raise ValueError("contribution calendar markup did not match")

    days = {}
    for date, cid, level in cells:
        m = re.match(r"(\d+) contribution", tips.get(cid, ""))
        days[date] = {
            "date": date,
            "count": int(m.group(1)) if m else 0,
            "level": int(level),
        }

    ordered = sorted(days.values(), key=lambda d: d["date"])
    first = dt.date.fromisoformat(ordered[0]["date"])
    first -= dt.timedelta(days=(first.weekday() + 1) % 7)

    weeks: list[list[dict | None]] = []
    for day in ordered:
        offset = (dt.date.fromisoformat(day["date"]) - first).days
        wi, di = offset // 7, offset % 7
        while len(weeks) <= wi:
            weeks.append([None] * 7)
        weeks[wi][di] = day

    blank = {"date": "", "count": 0, "level": 0}
    return [[d or blank for d in week] for week in weeks]


def fetch_profile() -> dict:
    user = _get(f"https://api.github.com/users/{USER}")
    repos = _get(
        f"https://api.github.com/users/{USER}/repos?per_page=100&sort=pushed"
    )
    own = [r for r in repos if not r.get("fork")]
    langs: dict[str, int] = {}
    for repo in own:
        try:
            for name, size in _get(repo["languages_url"]).items():
                langs[name] = langs.get(name, 0) + size
        except Exception:
            name = repo.get("language")
            if name:
                langs[name] = langs.get(name, 0) + max(repo.get("size", 1), 1)
    return {
        "name": user.get("name") or USER,
        "bio": user.get("bio") or "Java & Spring Boot Developer · B.Tech CSE",
        "repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "stars": sum(r.get("stargazers_count", 0) for r in own),
        "own_repos": len(own),
        "languages": langs,
        "avatar_url": user.get("avatar_url", ""),
        "all_repos": repos,
    }


def streaks(weeks):
    days = sorted(
        (d for w in weeks for d in w if d["date"]), key=lambda d: d["date"]
    )
    today = dt.date.today().isoformat()
    days = [d for d in days if d["date"] <= today]
    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] else 0
        longest = max(longest, run)
    current = 0
    for d in reversed(days):
        if d["count"]:
            current += 1
        elif d["date"] == today:
            continue
        else:
            break
    return current, longest


def monthly_data(weeks) -> list[dict]:
    """Aggregate contribution counts by month for the chart card."""
    months: dict[str, int] = {}
    for w in weeks:
        for d in w:
            if d["date"]:
                key = d["date"][:7]  # YYYY-MM
                months[key] = months.get(key, 0) + d["count"]
    return [
        {"month": k, "count": v}
        for k, v in sorted(months.items())
    ]


def save_data(profile: dict, weeks: list) -> None:
    """Persist contribution + profile data to data/contributions.json."""
    os.makedirs(DATA, exist_ok=True)
    today = dt.date.today().isoformat()
    cur, lng = streaks(weeks)
    total = sum(d["count"] for w in weeks for d in w)
    active = sum(1 for w in weeks for d in w if d["count"])

    # busiest day
    all_days = sorted(
        (d for w in weeks for d in w if d["date"] and d["date"] <= today),
        key=lambda d: -d["count"],
    )
    busiest = all_days[0] if all_days else {"date": today, "count": 0}

    payload = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
        "username": USER,
        "profile": {
            "name": profile["name"],
            "bio": profile["bio"],
            "repos": profile["repos"],
            "followers": profile["followers"],
            "stars": profile["stars"],
            "own_repos": profile["own_repos"],
            "languages": profile["languages"],
        },
        "contributions": {
            "total": total,
            "active_days": active,
            "current_streak": cur,
            "longest_streak": lng,
            "busiest_day": busiest["date"],
            "busiest_count": busiest["count"],
            "monthly": monthly_data(weeks),
        },
        "weeks": weeks,
        "featured_repos": [],
    }

    # Fetch featured repo details
    all_repos = profile.get("all_repos", [])
    repo_map = {r["name"]: r for r in all_repos}
    for name in FEATURED_REPOS:
        r = repo_map.get(name)
        if not r:
            try:
                r = _get(f"https://api.github.com/repos/{USER}/{name}")
            except Exception:
                continue
        if r:
            payload["featured_repos"].append({
                "name": r["name"],
                "description": r.get("description") or "",
                "language": r.get("language") or "",
                "stars": r.get("stargazers_count", 0),
                "forks": r.get("forks_count", 0),
                "url": r.get("html_url", f"https://github.com/{USER}/{name}"),
            })

    with open(os.path.join(DATA, "contributions.json"), "w") as f:
        json.dump(payload, f, indent=2)
    print(f"  wrote data/contributions.json ({len(json.dumps(payload)) / 1024:.1f} KB)")


def load_data() -> dict:
    path = os.path.join(DATA, "contributions.json")
    with open(path) as f:
        return json.load(f)


# ------------------------------------------------------------ SVG helpers
def esc(t) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def reduced_motion_style(card_id: str) -> str:
    """CSS that freezes all animations when the user prefers reduced motion."""
    return f"""
    @media (prefers-reduced-motion: reduce) {{
      #{card_id} * {{
        animation-play-state: paused !important;
        animation-delay: -1s !important;
        animation-duration: 0s !important;
        animation-iteration-count: 1 !important;
      }}
      #{card_id} animate,
      #{card_id} animateTransform {{
        fill: freeze;
        begin: 0s;
        dur: 0.001s;
        repeatCount: 1;
      }}
    }}"""


def card_shell(
    height: int,
    label: str,
    body: str,
    card_id: str = "card",
    extra_style: str = "",
    delay: float = 0.0,
) -> str:
    """Shared dark card frame: grid pattern, scan beam, lit border, halo."""

    # For STATIC mode, disable the beam animation
    beam_anim = "" if STATIC else (
        f'<animate attributeName="x" values="-220;{W}" '
        f'dur="9s" begin="{delay:.1f}s" repeatCount="indefinite"/>'
    )

    style_block = f"""<style>
    #{card_id} .beam-rect {{
      animation: beam-sweep-{card_id} 9s {delay:.1f}s infinite linear;
    }}
    @keyframes beam-sweep-{card_id} {{
      from {{ transform: translateX(-220px); }}
      to   {{ transform: translateX({W}px); }}
    }}
    #{card_id} .fade-in {{
      opacity: 0;
      animation: fadein-{card_id} 0.8s {delay + 0.2:.1f}s ease-out forwards;
    }}
    @keyframes fadein-{card_id} {{
      to {{ opacity: 1; }}
    }}
    #{card_id} .slide-up {{
      opacity: 0;
      transform: translateY(12px);
      animation: slideup-{card_id} 0.6s ease-out forwards;
    }}
    @keyframes slideup-{card_id} {{
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    {extra_style}
    {reduced_motion_style(card_id)}
  </style>"""

    if STATIC:
        style_block = style_block.replace("opacity: 0;", "opacity: 1;")
        style_block = style_block.replace(
            "transform: translateY(12px);", "transform: translateY(0);"
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" height="{height}" role="img" aria-label="{esc(label)}">
<title>{esc(label)}</title>
{style_block}
<defs>
  <linearGradient id="{card_id}-edge" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{DIM}" stop-opacity="0.85"/>
    <stop offset="0.5" stop-color="{CYAN}" stop-opacity="0.85"/>
    <stop offset="1" stop-color="{DIM}" stop-opacity="0.85"/>
  </linearGradient>
  <linearGradient id="{card_id}-beam" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{ICE}" stop-opacity="0"/>
    <stop offset="0.5" stop-color="{ICE}" stop-opacity="0.13"/>
    <stop offset="1" stop-color="{ICE}" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="{card_id}-halo" cx="50%" cy="50%" r="50%">
    <stop offset="0" stop-color="{CYAN}" stop-opacity="0.18"/>
    <stop offset="1" stop-color="{CYAN}" stop-opacity="0"/>
  </radialGradient>
  <pattern id="{card_id}-grid" width="40" height="40" patternUnits="userSpaceOnUse">
    <path d="M40 0H0V40" fill="none" stroke="{GRID}" stroke-width="1"/>
  </pattern>
  <filter id="{card_id}-glow" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur stdDeviation="2.2" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <clipPath id="{card_id}-clip"><rect x="1" y="1" width="{W - 2}" height="{height - 2}" rx="16"/></clipPath>
</defs>
<g id="{card_id}" clip-path="url(#{card_id}-clip)">
  <rect width="{W}" height="{height}" fill="{BASE}"/>
  <rect width="{W}" height="{height}" fill="url(#{card_id}-grid)" opacity="0.5"/>
  <ellipse cx="150" cy="0" rx="380" ry="210" fill="url(#{card_id}-halo)"/>
  <rect x="-220" y="0" width="220" height="{height}" fill="url(#{card_id}-beam)">
    {beam_anim}
  </rect>
{body}
</g>
<rect x="1" y="1" width="{W - 2}" height="{height - 2}" rx="16" fill="none" stroke="url(#{card_id}-edge)" stroke-width="1.4"/>
</svg>
"""


def wolf_svg(x, y, size, opacity=1.0, glow_id="card-glow"):
    s = size / 100.0
    return f"""  <g transform="translate({x},{y}) scale({s})" opacity="{opacity}">
    <path d="M20 2 L37 28 L15 33 Z" fill="{DIM}" opacity="0.75"/>
    <path d="M80 2 L63 28 L85 33 Z" fill="{DIM}" opacity="0.75"/>
    <path d="M15 29 L50 17 L85 29 L77 58 L50 97 L23 58 Z" fill="{PANEL}" stroke="{LINE}" stroke-width="1.6"/>
    <path d="M50 17 L85 29 L77 58 L50 97 Z" fill="{INK}" opacity="0.4"/>
    <path d="M50 30 L54 52 L50 60 L46 52 Z" fill="{LINE}" opacity="0.9"/>
    <path d="M42 66 L50 78 L58 66 L50 71 Z" fill="{LINE}"/>
    <g filter="url(#{glow_id})">
      <path d="M29 45 L43 41 L44 47 L30 50 Z" fill="{CYAN}"/>
      <path d="M71 45 L57 41 L56 47 L70 50 Z" fill="{CYAN}"/>
    </g>
  </g>"""


def eyebrow(x, y, text, card_id="card"):
    return (
        f'    <rect x="{x}" y="{y}" width="34" height="2" fill="{CYAN}"/>\n'
        f'    <text x="{x}" y="{y + 30}" font-family="{MONO}" font-size="13" '
        f'letter-spacing="3.2" fill="{SUB}">{esc(text)}</text>'
    )


# ================================================================ CARDS
# ---------------------------------------------------------------- 1. HERO
def build_hero(data: dict) -> str:
    delay = STAGGER["hero"]
    p = data["profile"]

    b = [f'  <g font-family="{SANS}" class="fade-in">']
    b.append(wolf_svg(812, 62, 148, 0.95, "hero-glow"))
    b.append(eyebrow(64, 60, "SYSTEM ONLINE // PROFILE", "hero"))

    # Name
    b.append(
        f'    <text x="64" y="152" font-size="52" font-weight="700" '
        f'fill="{TEXT}" letter-spacing="1">{esc(p["name"].upper())}</text>'
    )

    # One-liner
    bio_line = "Java  ·  Spring Boot  ·  Backend Engineering"
    b.append(
        f'    <text x="64" y="190" font-family="{MONO}" font-size="19" '
        f'fill="{CYAN}" letter-spacing="0.6">{esc(bio_line)}</text>'
    )

    # Sub-line
    b.append(
        f'    <text x="64" y="220" font-family="{MONO}" font-size="13.5" '
        f'fill="{SUB}">Mapping the infrastructure layer — Docker, CI/CD, Linux, AWS &amp; Azure</text>'
    )

    # Chips
    x = 64
    for chip in ("DOCKER", "CI/CD", "LINUX", "AWS", "AZURE", "SYSTEM DESIGN"):
        w = 12 + len(chip) * 7.7
        b.append(
            f'    <g><rect x="{x:.1f}" y="246" width="{w:.1f}" height="25" rx="6" '
            f'fill="{PANEL}" stroke="{GRID}" stroke-width="1"/>'
            f'<text x="{x + 8:.1f}" y="263" font-family="{MONO}" font-size="11" '
            f'letter-spacing="1.5" fill="{SUB}">{esc(chip)}</text></g>'
        )
        x += w + 9

    # Tagline with pulse
    pulse_anim = "" if STATIC else (
        f'<animate attributeName="opacity" values="0.72;1;0.72" '
        f'dur="5s" begin="{delay + 0.3:.1f}s" repeatCount="indefinite"/>'
    )
    b.append(
        f'    <text x="64" y="306" font-family="{MONO}" font-size="12.5" '
        f'letter-spacing="2.4" fill="{SUB}">'
        f'QUIET IN APPROACH.  PRECISE IN EXECUTION.{pulse_anim}</text>'
    )
    b.append("  </g>")

    return card_shell(340, "Kritagya Yadav — Java and Spring Boot backend developer",
                      "\n".join(b), card_id="hero", delay=delay)


# ---------------------------------------------------------- 2. LINK TILES
def build_links(data: dict) -> str:
    """Three linked tiles in a row, each is an inline mini-card."""
    delay = STAGGER["links"]

    tiles = [
        ("LinkedIn", "Connect on LinkedIn", "0a66c2",
         "https://www.linkedin.com/in/kritagya-yadav/",
         "M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 "
         "15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.32 1.3v-1.11h-2.79v8.37h"
         "2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.79M6.88 8.56a1.68 "
         "1.68 0 0 0 1.68-1.68c0-.93-.75-1.69-1.68-1.69a1.69 1.69 0 0 0-1.69 1.69c0 "
         ".93.76 1.68 1.69 1.68m1.39 9.94v-8.37H5.5v8.37h2.77z"),
        ("GitHub", "Follow on GitHub", "181717",
         f"https://github.com/{USER}",
         "M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217."
         "682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158"
         "-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 "
         "1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555"
         "-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 "
         "0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c"
         "1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 "
         "1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 "
         "1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0 0 22 12.017"
         "C22 6.484 17.522 2 12 2z"),
        ("Email", "Contact via Email", "ea4335",
         "mailto:kritagyay2006@gmail.com",
         "M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 "
         "2-2V6c0-1.1-.9-2-2-2zm0 4-8 5-8-5V6l8 5 8-5v2z"),
    ]

    tile_w = 320
    gap = 20
    total_w = tile_w * 3 + gap * 2
    x_start = (W - total_w) // 2
    h = 90

    parts = []
    for i, (name, tooltip, colour, url, icon_path) in enumerate(tiles):
        tx = x_start + i * (tile_w + gap)
        anim_delay = delay + i * 0.15

        # slide-up with stagger
        style = (
            f"opacity:1;" if STATIC
            else f"opacity:0;animation:slideup-links 0.6s {anim_delay:.2f}s ease-out forwards;"
        )

        parts.append(f"""  <g style="{style}">
    <a href="{esc(url)}" target="_blank">
      <rect x="{tx}" y="10" width="{tile_w}" height="{h}" rx="12"
            fill="{PANEL}" stroke="{GRID}" stroke-width="1"/>
      <g transform="translate({tx + 20},{32}) scale(0.9)">
        <path d="{icon_path}" fill="#{colour}"/>
      </g>
      <text x="{tx + 56}" y="48" font-family="{MONO}" font-size="15"
            font-weight="700" fill="{TEXT}">{esc(name)}</text>
      <text x="{tx + 56}" y="72" font-family="{MONO}" font-size="11"
            fill="{MUTED}">{esc(tooltip)}</text>
    </a>
  </g>""")

    extra_css = f"""
    @keyframes slideup-links {{
      from {{ opacity: 0; transform: translateY(12px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}"""

    body = "\n".join(parts)
    return card_shell(
        110, "Social links: LinkedIn, GitHub, Email",
        body, card_id="links", extra_style=extra_css, delay=delay,
    )


# ------------------------------------------------------ 3. CHART CARD
def build_chart(data: dict) -> str:
    """Monthly contribution bar chart with streak / active days / busiest day."""
    delay = STAGGER["chart"]
    c = data["contributions"]
    monthly = c["monthly"][-12:]  # last 12 months
    cur_streak = c["current_streak"]
    longest_streak = c["longest_streak"]
    active_days = c["active_days"]
    busiest_day = c.get("busiest_day", "")
    busiest_count = c.get("busiest_count", 0)

    if not monthly:
        return ""

    max_count = max(m["count"] for m in monthly) or 1

    chart_x = 64
    chart_y = 110
    chart_w = 580
    chart_h = 160
    bar_gap = 6
    bar_w = (chart_w - bar_gap * (len(monthly) - 1)) / len(monthly)

    b = [f'  <g font-family="{MONO}">']
    b.append(eyebrow(64, 44, "CONTRIBUTION PULSE", "chart"))

    # Stats sidebar
    stats = [
        (str(c["total"]), "total contributions"),
        (str(cur_streak), "current streak"),
        (str(longest_streak), "longest streak"),
        (str(active_days), "active days"),
    ]
    if busiest_day:
        # format nicely
        try:
            bd = dt.date.fromisoformat(busiest_day)
            stats.append((str(busiest_count), f"busiest · {bd.strftime('%b %d')}"))
        except Exception:
            stats.append((str(busiest_count), "busiest day"))

    sx = 700
    for si, (val, label) in enumerate(stats):
        sy = 90 + si * 50
        b.append(
            f'    <text x="{sx}" y="{sy}" font-size="22" font-weight="700" '
            f'fill="{CYAN}">{esc(val)}</text>'
        )
        b.append(
            f'    <text x="{sx}" y="{sy + 18}" font-size="10" letter-spacing="0.6" '
            f'fill="{MUTED}">{esc(label)}</text>'
        )

    b.append(f'    <line x1="672" y1="80" x2="672" y2="310" stroke="{GRID}" stroke-width="1"/>')

    # Bars
    months_short = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for i, m in enumerate(monthly):
        bx = chart_x + i * (bar_w + bar_gap)
        bar_h = max(4, (m["count"] / max_count) * chart_h)
        by = chart_y + chart_h - bar_h

        bar_delay = delay + 0.3 + i * 0.06

        # Background track
        b.append(
            f'    <rect x="{bx:.1f}" y="{chart_y}" width="{bar_w:.1f}" '
            f'height="{chart_h}" rx="4" fill="{PANEL}"/>'
        )

        # Animated bar: initial width at final value, SMIL grows from 0
        grow = "" if STATIC else (
            f'<animate attributeName="height" values="0;{bar_h:.0f}" '
            f'dur="0.8s" begin="{bar_delay:.2f}s" fill="freeze"/>'
            f'<animate attributeName="y" values="{chart_y + chart_h};{by:.0f}" '
            f'dur="0.8s" begin="{bar_delay:.2f}s" fill="freeze"/>'
        )

        bar_fill = CYAN if i == len(monthly) - 1 else DIM
        initial_y = by if STATIC else chart_y + chart_h
        initial_h = bar_h if STATIC else 0

        b.append(
            f'    <rect x="{bx:.1f}" y="{initial_y:.0f}" width="{bar_w:.1f}" '
            f'height="{initial_h:.0f}" rx="4" fill="{bar_fill}">'
            f'{grow}</rect>'
        )

        # Month label
        try:
            mi = int(m["month"][5:7]) - 1
            label = months_short[mi]
        except Exception:
            label = ""
        b.append(
            f'    <text x="{bx + bar_w / 2:.1f}" y="{chart_y + chart_h + 20}" '
            f'text-anchor="middle" font-size="9.5" fill="{MUTED}">{label}</text>'
        )

        # Count above bar
        if m["count"] > 0:
            if STATIC:
                count_attrs = ""
                count_child = ""
            else:
                count_attrs = 'opacity="0"'
                count_child = (
                    '<animate attributeName="opacity" values="0;1" '
                    'dur="0.3s" begin="%.2fs" fill="freeze"/>' % (bar_delay + 0.5)
                )
            b.append(
                '    <text x="%.1f" y="%.0f" '
                'text-anchor="middle" font-size="9" fill="%s" '
                '%s>%s%s</text>'
                % (bx + bar_w / 2, by - 6, SUB, count_attrs, count_child, m["count"])
            )

    b.append("  </g>")
    return card_shell(
        chart_y + chart_h + 50,
        "Monthly contribution chart with streak and activity stats",
        "\n".join(b),
        card_id="chart",
        delay=delay,
    )


# -------------------------------------------------- 4. FEATURED REPO CARD
def build_repo_card(repo: dict, index: int) -> str:
    """One card per featured repository."""
    delay = STAGGER["repo"] + index * 0.2
    card_id = f"repo-{index}"

    name = repo["name"]
    desc = repo.get("description", "") or "No description"
    lang = repo.get("language", "")
    stars = repo.get("stars", 0)
    forks = repo.get("forks", 0)
    url = repo.get("url", f"https://github.com/{USER}/{name}")

    # Truncate description
    if len(desc) > 90:
        desc = desc[:87] + "..."

    lang_colour = LANG_COLOURS.get(lang, CYAN)

    h = 140

    b = [f'  <g font-family="{MONO}">']

    # Repo name as link
    b.append(
        f'    <a href="{esc(url)}" target="_blank">'
        f'<text x="64" y="48" font-size="18" font-weight="700" fill="{CYAN}" '
        f'text-decoration="none">{esc(name)}</text></a>'
    )

    # Description
    b.append(
        f'    <text x="64" y="76" font-size="13" fill="{SUB}">{esc(desc)}</text>'
    )

    # Language dot + name
    if lang:
        b.append(
            f'    <circle cx="76" cy="104" r="5" fill="{lang_colour}"/>'
            f'    <text x="90" y="108" font-size="12" fill="{MUTED}">{esc(lang)}</text>'
        )

    # Stars
    star_x = 220
    b.append(
        f'    <text x="{star_x}" y="108" font-size="12" fill="{MUTED}">'
        f'★ {stars}</text>'
    )

    # Forks
    b.append(
        f'    <text x="{star_x + 60}" y="108" font-size="12" fill="{MUTED}">'
        f'⑂ {forks}</text>'
    )

    # Small wolf watermark
    b.append(wolf_svg(900, 30, 80, 0.2, f"{card_id}-glow"))

    b.append("  </g>")

    return card_shell(h, f"Repository: {name}", "\n".join(b),
                      card_id=card_id, delay=delay)


# ------------------------------------------------ 5. CONTRIBUTION TRAIL
def build_trail(data: dict) -> str:
    """Contribution heatmap grid in brand colours."""
    delay = STAGGER["trail"]
    weeks = data["weeks"][-53:]
    c = data["contributions"]
    total = c["total"]
    active = c["active_days"]

    cell, pitch = 12, 15
    x0, y0 = 76, 134

    b = [f'  <g font-family="{MONO}">']
    b.append(eyebrow(64, 44, "CONTRIBUTION TRAIL", "trail"))
    b.append(
        f'    <text x="64" y="96" font-size="11.5" fill="{MUTED}">'
        f'consistency leaves tracks · {total} contributions, {active} active days</text>'
    )

    # Month labels
    months_short = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    seen = {}
    for wi, week in enumerate(weeks):
        date = next((d["date"] for d in week if d["date"]), None)
        if date and date[:7] not in seen:
            seen[date[:7]] = wi
    last_wi = -99
    for month_key, wi in sorted(seen.items(), key=lambda kv: kv[1]):
        if wi > 50 or wi - last_wi < 3:
            continue
        last_wi = wi
        mi = int(month_key[5:7]) - 1
        b.append(
            f'    <text x="{x0 + wi * pitch}" y="{y0 - 12}" font-size="10.5" '
            f'fill="{MUTED}">{months_short[mi]}</text>'
        )

    # Day-of-week labels
    for di, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        b.append(
            f'    <text x="{x0 - 38}" y="{y0 + di * pitch + cell - 2}" '
            f'font-size="10" fill="{MUTED}">{name}</text>'
        )

    # Cells
    for wi, week in enumerate(weeks):
        for di, day in enumerate(week):
            level = day["level"] if day["count"] else 0
            cell_delay = delay + 0.01 * wi  # subtle wave
            fill = HEAT[min(level, 4)]

            # For non-empty cells, fade in with a wave effect
            if level > 0 and not STATIC:
                b.append(
                    f'    <rect x="{x0 + wi * pitch}" y="{y0 + di * pitch}" '
                    f'width="{cell}" height="{cell}" rx="2.5" fill="{fill}" opacity="0">'
                    f'<animate attributeName="opacity" values="0;1" dur="0.3s" '
                    f'begin="{cell_delay:.2f}s" fill="freeze"/></rect>'
                )
            else:
                b.append(
                    f'    <rect x="{x0 + wi * pitch}" y="{y0 + di * pitch}" '
                    f'width="{cell}" height="{cell}" rx="2.5" fill="{fill}"/>'
                )

    # Legend
    ly = y0 + 7 * pitch + 32
    b.append(f'    <text x="{x0}" y="{ly}" font-size="10.5" fill="{MUTED}">less</text>')
    for i, colour in enumerate(HEAT):
        b.append(
            f'    <rect x="{x0 + 38 + i * 16}" y="{ly - 10}" width="{cell}" '
            f'height="{cell}" rx="2.5" fill="{colour}"/>'
        )
    b.append(
        f'    <text x="{x0 + 38 + 5 * 16 + 6}" y="{ly}" font-size="10.5" '
        f'fill="{MUTED}">more</text>'
    )

    b.append(wolf_svg(898, ly - 56, 60, 0.45, "trail-glow"))
    b.append("  </g>")

    return card_shell(ly + 38, "Contribution calendar for the last year",
                      "\n".join(b), card_id="trail", delay=delay)


# ---------------------------------------------------- 6. FOOTER
def build_footer(data: dict) -> str:
    delay = max(STAGGER.values()) + 0.5

    b = [f'  <g font-family="{MONO}">']
    b.append(wolf_svg(462, 36, 76, 0.9, "footer-glow"))
    b.append(
        f'    <text x="{W // 2}" y="150" text-anchor="middle" font-size="17" '
        f'letter-spacing="4" fill="{TEXT}">QUIET IN APPROACH.  PRECISE IN EXECUTION.</text>'
    )
    b.append(f'    <line x1="330" y1="172" x2="670" y2="172" stroke="{LINE}" stroke-width="1"/>')

    x = 232
    for key, value in (("STATUS", "BUILDING"), ("MODE", "PRECISE EXECUTION"), ("NEXT", "INFRASTRUCTURE")):
        b.append(
            f'    <text x="{x}" y="206" text-anchor="middle" font-size="10" '
            f'letter-spacing="2" fill="{MUTED}">{esc(key)}</text>'
        )
        b.append(
            f'    <text x="{x}" y="226" text-anchor="middle" font-size="12.5" '
            f'letter-spacing="1" fill="{CYAN}">{esc(value)}</text>'
        )
        x += 268

    gen_date = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    b.append(
        f'    <text x="{W // 2}" y="262" text-anchor="middle" font-size="10.5" '
        f'fill="{MUTED}">cards regenerated from the GitHub API · {gen_date}</text>'
    )
    b.append("  </g>")

    return card_shell(292, "Quiet in approach. Precise in execution.",
                      "\n".join(b), card_id="footer", delay=delay)


# ================================================================ README
def build_readme(data: dict) -> str:
    """Generate the README.md that shows all cards."""
    p = data["profile"]
    repos = data.get("featured_repos", [])

    lines = [
        '<div align="center">\n',
        f'<img src="cards/hero.svg" width="100%" alt="Kritagya Yadav — {p["bio"]}"/>\n',
        f'<img src="cards/links.svg" width="100%" alt="Social links"/>\n',
        "",
        "---\n",
        "## Contributions\n",
        f'<img src="cards/chart.svg" width="100%" alt="Monthly contributions chart"/>\n',
    ]

    if repos:
        lines.append("\n## Featured Projects\n")
        for i, r in enumerate(repos):
            lines.append(
                f'<a href="{r["url"]}">'
                f'<img src="cards/repo-{i}.svg" width="100%" '
                f'alt="{esc(r["name"])}"/></a>\n'
            )

    lines.extend([
        "\n## Contribution Trail\n",
        f'<img src="cards/trail.svg" width="100%" alt="Contribution heatmap"/>\n',
        "",
        "---\n",
        f'<img src="cards/footer.svg" width="100%" alt="Footer"/>\n',
        "</div>\n",
    ])

    return "\n".join(lines)


# ================================================================ MAIN
def write(name: str, content: str, directory: str = CARDS) -> None:
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"  wrote {os.path.relpath(path, ROOT)} ({len(content) / 1024:.1f} KB)")


def main() -> int:
    os.makedirs(CARDS, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)

    mode_label = "STATIC" if STATIC else "animated"
    print(f"building {mode_label} profile cards for {USER}"
          f"{' (authenticated)' if TOKEN else ''}")

    # 1. Fetch data from GitHub API and save locally
    data_path = os.path.join(DATA, "contributions.json")
    needs_fetch = not os.path.exists(data_path) or os.environ.get("REFRESH", "") == "1"

    if needs_fetch:
        print("fetching data from GitHub API...")
        try:
            profile = fetch_profile()
        except Exception as exc:
            print(f"! could not read profile data ({exc})")
            if not os.path.exists(data_path):
                return 1
            print("  falling back to cached data")
            needs_fetch = False
        if needs_fetch:
            try:
                weeks = fetch_contributions()
            except Exception as exc:
                print(f"! could not read contribution calendar ({exc})")
                if not os.path.exists(data_path):
                    return 1
                print("  falling back to cached data")
                needs_fetch = False
            else:
                contributions = sum(d["count"] for w in weeks for d in w)
                if not contributions and profile["repos"] <= 1:
                    print(
                        f"! {USER!r} looks empty ({profile['repos']} repos, "
                        f"{contributions} contributions) — refusing to overwrite"
                    )
                    return 1
                save_data(profile, weeks)

    # 2. Load cached data
    data = load_data()

    # 3. Render every card
    write("hero.svg", build_hero(data))
    write("links.svg", build_links(data))
    write("chart.svg", build_chart(data))

    for i, repo in enumerate(data.get("featured_repos", [])):
        write(f"repo-{i}.svg", build_repo_card(repo, i))

    write("trail.svg", build_trail(data))
    write("footer.svg", build_footer(data))

    # 4. Generate README
    write("README.md", build_readme(data), ROOT)

    c = data["contributions"]
    print(
        f"done — {c['total']} contributions, "
        f"streak {c['current_streak']} (longest {c['longest_streak']}), "
        f"{len(data.get('featured_repos', []))} repos featured"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
