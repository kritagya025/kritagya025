#!/usr/bin/env python3
"""Generate the profile SVG assets in ./assets from real GitHub data.

Every card in the README is produced here, so the whole profile shares one
palette and never depends on a third-party stats service staying online.

    GITHUB_USERNAME=kritagya025 python scripts/build_profile.py

A token is optional. Without one the script uses the public REST API and the
public contribution calendar, so it runs fine on a laptop; with one
(GITHUB_TOKEN in Actions) the same requests just get a higher rate limit.

The account is read from GITHUB_USERNAME rather than USERNAME: on Windows,
USERNAME is a built-in holding the logged-in OS account, which silently
overrides the default and builds the wrong person's profile.
"""

import datetime as dt
import json
import os
import re
import sys
import urllib.request

USER = os.environ.get("GITHUB_USERNAME") or "kritagya025"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")

# Languages left out of the "most used" chart. Empty by default, so the chart
# shows exactly what GitHub reports. Worth knowing: .ipynb files embed their
# own base64 output, so "Jupyter Notebook" byte counts run far ahead of the
# code actually written. Set EXCLUDE_LANGUAGES="Jupyter Notebook" if you would
# rather the chart tracked source code.
EXCLUDE_LANGUAGES = {
    n.strip() for n in os.environ.get("EXCLUDE_LANGUAGES", "").split(",") if n.strip()
}

# ---------------------------------------------------------------- palette
INK = "#05070D"    # deepest background
BASE = "#0A1128"   # card background
PANEL = "#0E1830"  # raised panel, and the empty heat cell
GRID = "#14213D"   # grid rules
LINE = "#1B3A6B"   # dividers
CYAN = "#4FC3F7"   # primary accent, matched to the wolf's eyes
DIM = "#2C6E9E"    # secondary accent
ICE = "#A8E4FF"    # highlight
TEXT = "#E8F1FA"
SUB = "#9DB4CE"
MUTED = "#5F7796"

HEAT = [PANEL, "#17415F", "#216E96", "#2C9BCB", CYAN]

MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
CH = 8.05  # approximate advance width of MONO at 13.5px, used for cursor placement

W = 1000  # every card is 1000 units wide so they stack flush in the README


# ------------------------------------------------------------------- data
def _get(url, headers=None, raw=False):
    h = {"User-Agent": "kritagya025-profile"}
    if headers:
        h.update(headers)
    if TOKEN:
        h["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    return data.decode("utf-8", "replace") if raw else json.loads(data.decode("utf-8"))


def fetch_contributions():
    """Real contribution calendar from the public profile endpoint.

    Needs no authentication, which is what lets this run outside Actions.
    GitHub ids each cell "contribution-day-component-<weekday>-<week>" and
    emits the table row by row, so the document order is weekday-major. The
    grid is rebuilt from the dates themselves rather than from that order.
    """
    html = _get(
        "https://github.com/users/%s/contributions" % USER,
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
            r'for="(contribution-day-component-\d+-\d+)"[^>]*>([^<]*)</tool-tip>', html
        )
    )
    if not cells:
        raise ValueError("contribution calendar markup did not match")

    days = {}
    for date, cid, level in cells:
        m = re.match(r"(\d+) contribution", tips.get(cid, ""))
        days[date] = {"date": date, "count": int(m.group(1)) if m else 0, "level": int(level)}

    ordered = sorted(days.values(), key=lambda d: d["date"])
    first = dt.date.fromisoformat(ordered[0]["date"])
    # GitHub starts the calendar on a Sunday; align to it so rows read Sun..Sat.
    first -= dt.timedelta(days=(first.weekday() + 1) % 7)

    weeks = []
    for day in ordered:
        offset = (dt.date.fromisoformat(day["date"]) - first).days
        wi, di = offset // 7, offset % 7
        while len(weeks) <= wi:
            weeks.append([None] * 7)
        weeks[wi][di] = day

    blank = {"date": "", "count": 0, "level": 0}
    return [[d or blank for d in week] for week in weeks]


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
            continue  # nothing committed yet today; that does not end a streak
        else:
            break
    return current, longest


def fetch_profile():
    user = _get("https://api.github.com/users/%s" % USER)
    repos = _get(
        "https://api.github.com/users/%s/repos?per_page=100&sort=pushed" % USER
    )
    own = [r for r in repos if not r.get("fork")]

    langs = {}
    for repo in own:
        try:
            for name, size in _get(repo["languages_url"]).items():
                langs[name] = langs.get(name, 0) + size
        except Exception:
            # Fall back to the repo's primary language if that call is refused.
            name = repo.get("language")
            if name:
                langs[name] = langs.get(name, 0) + max(repo.get("size", 1), 1)

    return {
        "name": user.get("name") or USER,
        "repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "stars": sum(r.get("stargazers_count", 0) for r in own),
        "own_repos": len(own),
        "languages": {k: v for k, v in langs.items() if k not in EXCLUDE_LANGUAGES},
    }


# ---------------------------------------------------------------- helpers
def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def top_languages(langs, limit=5):
    ranked = sorted(langs.items(), key=lambda kv: -kv[1])[:limit]
    total = sum(langs.values()) or 1
    return [(n, s / total) for n, s in ranked]


def card(height, label, body):
    """Shared shell: dark card, technical grid, slow scan beam, lit border."""
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{label}">
<title>{label}</title>
<defs>
  <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{dim}" stop-opacity="0.85"/>
    <stop offset="0.5" stop-color="{cyan}" stop-opacity="0.85"/>
    <stop offset="1" stop-color="{dim}" stop-opacity="0.85"/>
  </linearGradient>
  <linearGradient id="beam" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{ice}" stop-opacity="0"/>
    <stop offset="0.5" stop-color="{ice}" stop-opacity="0.13"/>
    <stop offset="1" stop-color="{ice}" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="halo" cx="50%" cy="50%" r="50%">
    <stop offset="0" stop-color="{cyan}" stop-opacity="0.18"/>
    <stop offset="1" stop-color="{cyan}" stop-opacity="0"/>
  </radialGradient>
  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
    <path d="M40 0H0V40" fill="none" stroke="{grid}" stroke-width="1"/>
  </pattern>
  <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur stdDeviation="2.2" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <clipPath id="clip"><rect x="1" y="1" width="{iw}" height="{ih}" rx="16"/></clipPath>
</defs>
<g clip-path="url(#clip)">
  <rect width="{w}" height="{h}" fill="{base}"/>
  <rect width="{w}" height="{h}" fill="url(#grid)" opacity="0.5"/>
  <ellipse cx="150" cy="0" rx="380" ry="210" fill="url(#halo)"/>
  <rect x="-220" y="0" width="220" height="{h}" fill="url(#beam)">
    <animate attributeName="x" values="-220;{w}" dur="9s" repeatCount="indefinite"/>
  </rect>
{body}
</g>
<rect x="1" y="1" width="{iw}" height="{ih}" rx="16" fill="none" stroke="url(#edge)" stroke-width="1.4"/>
</svg>
""".format(
        w=W, h=height, iw=W - 2, ih=height - 2, label=esc(label), body=body,
        base=BASE, grid=GRID, cyan=CYAN, dim=DIM, ice=ICE,
    )


def wolf(x, y, size, opacity=1.0):
    """Original geometric wolf mark, drawn inside a 100x100 box."""
    return """  <g transform="translate({x},{y}) scale({s})" opacity="{o}">
    <path d="M20 2 L37 28 L15 33 Z" fill="{dim}" opacity="0.75"/>
    <path d="M80 2 L63 28 L85 33 Z" fill="{dim}" opacity="0.75"/>
    <path d="M15 29 L50 17 L85 29 L77 58 L50 97 L23 58 Z" fill="{panel}" stroke="{line}" stroke-width="1.6"/>
    <path d="M50 17 L85 29 L77 58 L50 97 Z" fill="{ink}" opacity="0.4"/>
    <path d="M50 30 L54 52 L50 60 L46 52 Z" fill="{line}" opacity="0.9"/>
    <path d="M42 66 L50 78 L58 66 L50 71 Z" fill="{line}"/>
    <g filter="url(#glow)">
      <path d="M29 45 L43 41 L44 47 L30 50 Z" fill="{cyan}"/>
      <path d="M71 45 L57 41 L56 47 L70 50 Z" fill="{cyan}"/>
    </g>
  </g>""".format(
        x=x, y=y, s=size / 100.0, o=opacity,
        dim=DIM, panel=PANEL, line=LINE, ink=INK, cyan=CYAN,
    )


def eyebrow(x, y, text):
    """Small cyan tick plus a spaced label; the heading style shared by cards."""
    return (
        '    <rect x="%d" y="%d" width="34" height="2" fill="%s"/>\n'
        '    <text x="%d" y="%d" font-family="%s" font-size="13" letter-spacing="3.2" fill="%s">%s</text>'
        % (x, y, CYAN, x, y + 30, MONO, SUB, esc(text))
    )


# ------------------------------------------------------------------ cards
def build_hero(p):
    b = ['  <g font-family="%s">' % SANS]
    b.append(wolf(812, 62, 148, 0.95))
    b.append(eyebrow(64, 60, "SYSTEM ONLINE // PROFILE"))
    b.append(
        '    <text x="64" y="152" font-size="52" font-weight="700" fill="%s" letter-spacing="1">%s</text>'
        % (TEXT, esc("KRITAGYA YADAV"))
    )
    b.append(
        '    <text x="64" y="190" font-family="%s" font-size="19" fill="%s" letter-spacing="0.6">%s</text>'
        % (MONO, CYAN, esc("Java  ·  Spring Boot  ·  Backend Engineering"))
    )
    b.append(
        '    <text x="64" y="220" font-family="%s" font-size="13.5" fill="%s">%s</text>'
        % (MONO, SUB, esc("Mapping the infrastructure layer — Docker, CI/CD, Linux, AWS & Azure"))
    )

    x = 64
    for chip in ("DOCKER", "CI/CD", "LINUX", "AWS", "AZURE", "SYSTEM DESIGN"):
        w = 12 + len(chip) * 7.7
        b.append(
            '    <g><rect x="%.1f" y="246" width="%.1f" height="25" rx="6" fill="%s" stroke="%s" stroke-width="1"/>'
            '<text x="%.1f" y="263" font-family="%s" font-size="11" letter-spacing="1.5" fill="%s">%s</text></g>'
            % (x, w, PANEL, GRID, x + 8, MONO, SUB, esc(chip))
        )
        x += w + 9
    b.append(
        '    <text x="64" y="306" font-family="%s" font-size="12.5" letter-spacing="2.4" fill="%s">%s'
        '<animate attributeName="opacity" values="0.72;1;0.72" dur="5s" repeatCount="indefinite"/></text>'
        % (MONO, SUB, esc("QUIET IN APPROACH.  PRECISE IN EXECUTION."))
    )
    b.append("  </g>")
    return card(340, "Kritagya Yadav — Java and Spring Boot backend developer", "\n".join(b))


def build_profile_card(p):
    rows = [
        ("role", "Java / Spring Boot Developer"),
        ("focus", "Backend Engineering  ·  Problem Solving"),
        ("education", "B.Tech CSE — KCC Institute of Technology, AKTU"),
        ("location", "Noida, Uttar Pradesh, India"),
        ("email", "kritagyay2006@gmail.com"),
    ]
    learning = ["Docker", "CI/CD", "AWS", "Azure", "Linux", "DSA & System Design"]

    b = ['  <g font-family="%s">' % MONO]
    b.append('    <rect x="1" y="1" width="%d" height="42" fill="%s"/>' % (W - 2, PANEL))
    b.append('    <line x1="0" y1="43" x2="%d" y2="43" stroke="%s" stroke-width="1"/>' % (W, GRID))
    for i, colour in enumerate((DIM, LINE, GRID)):
        b.append('    <circle cx="%d" cy="22" r="5" fill="%s"/>' % (30 + i * 19, colour))
    b.append(
        '    <text x="104" y="27" font-size="12.5" letter-spacing="2" fill="%s">%s</text>'
        % (MUTED, esc("kritagya025 — system profile"))
    )

    y = 88
    b.append(
        '    <text x="48" y="%d" font-size="14" fill="%s">$ <tspan fill="%s">whoami</tspan></text>'
        % (y, CYAN, TEXT)
    )
    y += 34
    for key, value in rows:
        b.append('    <text x="66" y="%d" font-size="13.5" fill="%s">%s</text>' % (y, MUTED, esc(key)))
        b.append('    <text x="176" y="%d" font-size="13.5" fill="%s">%s</text>' % (y, SUB, esc(value)))
        y += 26

    y += 16
    b.append(
        '    <text x="48" y="%d" font-size="14" fill="%s">$ <tspan fill="%s">cat currently_learning.txt</tspan></text>'
        % (y, CYAN, TEXT)
    )
    y += 32
    x = 66
    for item in learning:
        w = 16 + len(item) * 7.4
        b.append(
            '    <g><rect x="%.1f" y="%d" width="%.1f" height="26" rx="6" fill="%s" stroke="%s" stroke-width="1"/>'
            '<text x="%.1f" y="%d" font-size="12" fill="%s">%s</text></g>'
            % (x, y - 18, w, PANEL, LINE, x + 10, y, ICE, esc(item))
        )
        x += w + 10
    y += 50

    b.append(
        '    <text x="48" y="%d" font-size="14" fill="%s">$ <tspan fill="%s">status</tspan></text>'
        % (y, CYAN, TEXT)
    )
    y += 28
    status = "BUILDING"
    tail = " — one commit at a time"
    b.append(
        '    <text x="66" y="%d" font-size="13.5" fill="%s">%s<tspan fill="%s">%s</tspan></text>'
        % (y, CYAN, esc(status), SUB, esc(tail))
    )
    cursor = 66 + int((len(status) + len(tail)) * CH) + 8
    b.append(
        '    <rect x="%d" y="%d" width="9" height="16" fill="%s">'
        '<animate attributeName="opacity" values="1;1;0;0" dur="1.2s" repeatCount="indefinite"/></rect>'
        % (cursor, y - 13, CYAN)
    )
    b.append("  </g>")
    return card(y + 44, "System profile: role, focus, education and current learning", "\n".join(b))


def build_signal(p, weeks):
    total = sum(d["count"] for w in weeks for d in w)
    current, longest = streaks(weeks)
    tiles = [
        (str(total), "contributions / year"),
        (str(p["repos"]), "public repositories"),
        (str(p["stars"]), "stars earned"),
        (str(p["followers"]), "followers"),
        (str(current), "current streak"),
        (str(longest), "longest streak"),
    ]

    b = ['  <g font-family="%s">' % MONO]
    b.append(eyebrow(64, 44, "GITHUB SIGNAL"))
    b.append(
        '    <text x="64" y="96" font-size="11.5" fill="%s">%s</text>'
        % (MUTED, esc("live data · regenerated daily from the GitHub API"))
    )

    for i, (value, caption) in enumerate(tiles):
        col, row = i % 3, i // 3
        x, y = 64 + col * 156, 130 + row * 84
        # Drawn fully visible: animation may enhance a card but must never be
        # what makes its content appear.
        b.append(
            '    <g><rect x="%d" y="%d" width="140" height="66" rx="9" fill="%s" stroke="%s" stroke-width="1"/>'
            '<text x="%d" y="%d" font-size="27" font-weight="700" fill="%s">%s</text>'
            '<text x="%d" y="%d" font-size="10" letter-spacing="0.6" fill="%s">%s</text></g>'
            % (
                x, y, PANEL, GRID,
                x + 16, y + 34, CYAN, esc(value),
                x + 16, y + 53, MUTED, esc(caption),
            )
        )

    b.append('    <line x1="562" y1="118" x2="562" y2="296" stroke="%s" stroke-width="1"/>' % GRID)
    b.append(
        '    <text x="600" y="138" font-size="12" letter-spacing="2.6" fill="%s">%s</text>'
        % (SUB, esc("MOST USED LANGUAGES"))
    )
    b.append(
        '    <text x="600" y="158" font-size="10.5" fill="%s">%s</text>'
        % (MUTED, esc("by bytes across %d public repos" % p["own_repos"]))
    )

    for i, (name, share) in enumerate(top_languages(p["languages"])):
        y = 190 + i * 26
        bar = max(4, round(196 * share))
        b.append('    <text x="600" y="%d" font-size="12" fill="%s">%s</text>' % (y + 4, SUB, esc(name)))
        b.append('    <rect x="740" y="%d" width="196" height="8" rx="4" fill="%s"/>' % (y - 4, GRID))
        # Base width is the real value, so the bar reads correctly even if the
        # renderer ignores SMIL; the animation only grows it into place.
        b.append(
            '    <rect x="740" y="%d" width="%d" height="8" rx="4" fill="%s">'
            '<animate attributeName="width" values="0;%d" dur="1.1s" begin="%.2fs" fill="freeze"/></rect>'
            % (y - 4, bar, CYAN if i == 0 else DIM, bar, 0.5 + i * 0.12)
        )
        b.append('    <text x="946" y="%d" font-size="10.5" fill="%s">%.1f%%</text>' % (y + 4, MUTED, share * 100))

    b.append("  </g>")
    return card(330, "GitHub statistics and most used languages", "\n".join(b))


def build_trail(p, weeks):
    weeks = weeks[-53:]
    total = sum(d["count"] for w in weeks for d in w)
    active = sum(1 for w in weeks for d in w if d["count"])
    cell, pitch = 12, 15
    x0, y0 = 76, 134

    b = ['  <g font-family="%s">' % MONO]
    b.append(eyebrow(64, 44, "CONTRIBUTION TRAIL"))
    b.append(
        '    <text x="64" y="96" font-size="11.5" fill="%s">%s</text>'
        % (MUTED, esc("consistency leaves tracks · %d contributions, %d active days" % (total, active)))
    )

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    seen = {}
    for wi, week in enumerate(weeks):
        date = next((d["date"] for d in week if d["date"]), None)
        if date and date[:7] not in seen:
            seen[date[:7]] = wi
    last = -99
    for month, wi in sorted(seen.items(), key=lambda kv: kv[1]):
        # A month that starts mid-week can land beside the previous label;
        # keep three columns of clearance so they never collide.
        if wi > 50 or wi - last < 3:
            continue
        last = wi
        b.append(
            '    <text x="%d" y="%d" font-size="10.5" fill="%s">%s</text>'
            % (x0 + wi * pitch, y0 - 12, MUTED, months[int(month[5:7]) - 1])
        )
    for di, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        b.append(
            '    <text x="%d" y="%d" font-size="10" fill="%s">%s</text>'
            % (x0 - 38, y0 + di * pitch + cell - 2, MUTED, name)
        )

    for wi, week in enumerate(weeks):
        for di, day in enumerate(week):
            level = day["level"] if day["count"] else 0
            b.append(
                '    <rect x="%d" y="%d" width="%d" height="%d" rx="2.5" fill="%s"/>'
                % (x0 + wi * pitch, y0 + di * pitch, cell, cell, HEAT[min(level, 4)])
            )

    ly = y0 + 7 * pitch + 32
    b.append('    <text x="%d" y="%d" font-size="10.5" fill="%s">less</text>' % (x0, ly, MUTED))
    for i, colour in enumerate(HEAT):
        b.append(
            '    <rect x="%d" y="%d" width="%d" height="%d" rx="2.5" fill="%s"/>'
            % (x0 + 38 + i * 16, ly - 10, cell, cell, colour)
        )
    b.append(
        '    <text x="%d" y="%d" font-size="10.5" fill="%s">more</text>'
        % (x0 + 38 + 5 * 16 + 6, ly, MUTED)
    )
    b.append(wolf(898, ly - 56, 60, 0.45))
    b.append("  </g>")
    return card(ly + 38, "Contribution calendar for the last year", "\n".join(b))


def build_footer(p):
    b = ['  <g font-family="%s">' % MONO]
    b.append(wolf(462, 36, 76, 0.9))
    b.append(
        '    <text x="%d" y="150" text-anchor="middle" font-size="17" letter-spacing="4" fill="%s">%s</text>'
        % (W // 2, TEXT, esc("QUIET IN APPROACH.  PRECISE IN EXECUTION."))
    )
    b.append('    <line x1="330" y1="172" x2="670" y2="172" stroke="%s" stroke-width="1"/>' % LINE)
    x = 232
    for key, value in (("STATUS", "BUILDING"), ("MODE", "PRECISE EXECUTION"), ("NEXT", "INFRASTRUCTURE")):
        b.append(
            '    <text x="%d" y="206" text-anchor="middle" font-size="10" letter-spacing="2" fill="%s">%s</text>'
            % (x, MUTED, esc(key))
        )
        b.append(
            '    <text x="%d" y="226" text-anchor="middle" font-size="12.5" letter-spacing="1" fill="%s">%s</text>'
            % (x, CYAN, esc(value))
        )
        x += 268
    b.append(
        '    <text x="%d" y="262" text-anchor="middle" font-size="10.5" fill="%s">%s</text>'
        % (W // 2, MUTED, esc("assets regenerated from the GitHub API · %s"
                              % dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")))
    )
    b.append("  </g>")
    return card(292, "Quiet in approach. Precise in execution.", "\n".join(b))


# -------------------------------------------------------------------- main
def write(name, svg):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        fh.write(svg)
    print("  wrote assets/%s (%.1f KB)" % (name, len(svg) / 1024.0))


def main():
    os.makedirs(OUT, exist_ok=True)
    print("building profile assets for %s%s" % (USER, " (authenticated)" if TOKEN else ""))

    try:
        profile = fetch_profile()
    except Exception as exc:
        print("! could not read profile data (%s) — keeping existing assets" % exc)
        return 1
    try:
        weeks = fetch_contributions()
    except Exception as exc:
        print("! could not read the contribution calendar (%s) — keeping existing assets" % exc)
        return 1

    # A misconfigured account still returns valid-looking empty data, so refuse
    # to overwrite good cards with it rather than silently blanking the profile.
    contributions = sum(d["count"] for w in weeks for d in w)
    if not contributions and profile["repos"] <= 1:
        print("! %r looks empty (%d repos, %d contributions) — refusing to overwrite existing assets"
              % (USER, profile["repos"], contributions))
        print("  set GITHUB_USERNAME if this is not the account you meant.")
        return 1

    write("hero.svg", build_hero(profile))
    write("profile.svg", build_profile_card(profile))
    write("signal.svg", build_signal(profile, weeks))
    write("trail.svg", build_trail(profile, weeks))
    write("footer.svg", build_footer(profile))

    current, longest = streaks(weeks)
    print(
        "done — %d contributions, %d repos, %d stars, streak %d (longest %d)"
        % (sum(d["count"] for w in weeks for d in w), profile["repos"],
           profile["stars"], current, longest)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
