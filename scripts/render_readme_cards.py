#!/usr/bin/env python3
"""
Render the full stack of high-tech dark animated SVG profile cards into cards/.

Palette: Deep space cyan & wolf-eye neon (#0A1128, #4FC3F7, #1B3A6B, #0E1830)
Cards produced:
  • hero.svg: System header, name, skills, wolf emblem with glowing cyan eyes
  • tile-linkedin.svg, tile-github.svg, tile-email.svg: 3 linked tiles in a row (32.5%)
  • profile.svg: Terminal whoami, certifications, detailed tech stack, status
  • signal.svg: 6 metric tiles + animated most used languages breakdown
  • chart.svg: 12-month contribution bar pulse + stats sidebar
  • repo-*.svg: 6 individual featured repository cards (32.5% wide each)
  • trail.svg: 53-week contribution calendar in glowing cyan heat ramp
  • footer.svg: Wolf mark, system readout, real-time generation timestamp

Supports STATIC=1 mode for static screenshot capture.
All animations respect prefers-reduced-motion: reduce.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import math
import os
import re
import urllib.request
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DATA = os.path.join(ROOT, "data", "contributions.json")
OUT = os.path.join(ROOT, "cards")
WOLF_ART = os.path.join(ROOT, "wolf_art.png")

STATIC = os.environ.get("STATIC", "") == "1"

# ------------------------------------------------------------ brand palette
INK = "#05070D"      # deepest background
BASE = "#0A1128"     # primary card background
PANEL = "#0E1830"    # raised panel & empty heat cell
GRID = "#14213D"     # grid rules
LINE = "#1B3A6B"     # dividers & borders
CYAN = "#4FC3F7"     # primary glowing accent (wolf eye cyan)
DIM = "#2C6E9E"      # secondary accent
ICE = "#A8E4FF"      # highlight
TEXT = "#E8F1FA"     # primary text
SUB = "#9DB4CE"      # secondary labels & bio
MUTED = "#5F7796"    # muted captions & metadata

HEAT = [PANEL, "#17415F", "#216E96", "#2C9BCB", CYAN]

MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

LANG_COLOURS = {
    "Java": "#b07219",
    "Python": "#3572A5",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "C++": "#f34b7d",
    "C": "#555555",
    "Dockerfile": "#384d54",
    "Shell": "#89e051",
}


def esc(t) -> str:
    return escape(str(t))


def card_shell(w: int, h: int, label: str, body: str, card_id: str, delay: float = 0.0) -> str:
    """Shared cyberpunk dark card frame with grid, scan beam, and glowing borders."""
    beam_anim = "" if STATIC else (
        f'<animate attributeName="x" values="-220;{w}" dur="9s" begin="{delay:.1f}s" repeatCount="indefinite"/>'
    )

    style_block = f"""<style>
    #{card_id} .beam-rect {{
      animation: beam-sweep-{card_id} 9s {delay:.1f}s infinite linear;
    }}
    @keyframes beam-sweep-{card_id} {{
      from {{ transform: translateX(-220px); }}
      to   {{ transform: translateX({w}px); }}
    }}
    #{card_id} .fade-in {{
      opacity: {"1" if STATIC else "0"};
      animation: fadein-{card_id} 0.8s {delay + 0.2:.1f}s ease-out forwards;
    }}
    @keyframes fadein-{card_id} {{
      to {{ opacity: 1; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      #{card_id} * {{
        animation: none !important;
        opacity: 1 !important;
        transform: none !important;
      }}
      #{card_id} animate, #{card_id} animateTransform {{
        fill: freeze;
        begin: 0s;
        dur: 0.001s;
        repeatCount: 1;
      }}
    }}
  </style>"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(label)}">
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
    <stop offset="0.5" stop-color="{ICE}" stop-opacity="0.14"/>
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
    <feGaussianBlur stdDeviation="2.4" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <clipPath id="{card_id}-clip"><rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14"/></clipPath>
</defs>
<g id="{card_id}" clip-path="url(#{card_id}-clip)">
  <rect width="{w}" height="{h}" fill="{BASE}"/>
  <rect width="{w}" height="{h}" fill="url(#{card_id}-grid)" opacity="0.45"/>
  <ellipse cx="140" cy="0" rx="360" ry="200" fill="url(#{card_id}-halo)"/>
  <rect x="-220" y="0" width="220" height="{h}" fill="url(#{card_id}-beam)">
    {beam_anim}
  </rect>
{body}
</g>
<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14" fill="none" stroke="url(#{card_id}-edge)" stroke-width="1.4"/>
</svg>
"""


def wolf_emblem(x: float, y: float, size: float, opacity: float = 1.0, glow_id: str = "glow") -> str:
    """Iconic geometric wolf mark with neon glowing cyan eyes."""
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


def eyebrow(x: int, y: int, text: str) -> str:
    return (
        f'    <rect x="{x}" y="{y}" width="34" height="2" fill="{CYAN}"/>\n'
        f'    <text x="{x}" y="{y + 28}" font-family="{MONO}" font-size="12.5" '
        f'letter-spacing="3.2" fill="{SUB}">{esc(text)}</text>'
    )


def write_card(filename: str, content: str) -> None:
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"wrote cards/{filename} ({len(content) // 1024} KB)")


# ================================================================ CARDS
# ---------------------------------------------------------------- 1. HERO
def build_hero(data: dict) -> str:
    w, h = 1000, 360
    b = [f'  <g font-family="{SANS}" class="fade-in">']
    b.append(wolf_emblem(770, 55, 175, 0.95, "hero-glow"))
    b.append(eyebrow(60, 48, "SYSTEM ONLINE // PROFILE 025"))

    # Name
    b.append(
        f'    <text x="60" y="136" font-size="50" font-weight="800" '
        f'fill="{TEXT}" letter-spacing="1.2">KRITAGYA YADAV</text>'
    )

    # Title
    b.append(
        f'    <text x="60" y="174" font-family="{MONO}" font-size="18" font-weight="600" '
        f'fill="{CYAN}" letter-spacing="0.6">Java  ·  Spring Boot  ·  Backend Engineering</text>'
    )

    # Subtitle
    b.append(
        f'    <text x="60" y="204" font-family="{MONO}" font-size="13.5" '
        f'fill="{SUB}">Architecting resilient backend systems, distributed services &amp; DevOps tooling</text>'
    )

    # Skill Badges
    chips = ("JAVA", "SPRING BOOT", "DOCKER", "CI/CD", "LINUX", "AWS", "AZURE", "SYSTEM DESIGN")
    cx = 60
    for chip in chips:
        cw = 14 + len(chip) * 7.8
        b.append(
            f'    <g><rect x="{cx:.1f}" y="234" width="{cw:.1f}" height="26" rx="6" '
            f'fill="{PANEL}" stroke="{LINE}" stroke-width="1"/>'
            f'<text x="{cx + 7:.1f}" y="251" font-family="{MONO}" font-size="11" '
            f'letter-spacing="1.2" fill="{ICE}">{chip}</text></g>'
        )
        cx += cw + 9

    # Glowing tagline
    pulse = "" if STATIC else (
        '<animate attributeName="opacity" values="0.72;1;0.72" dur="4.5s" repeatCount="indefinite"/>'
    )
    b.append(
        f'    <text x="60" y="306" font-family="{MONO}" font-size="12.5" '
        f'letter-spacing="2.8" fill="{SUB}">'
        f'QUIET IN APPROACH.  PRECISE IN EXECUTION.{pulse}</text>'
    )

    b.append("  </g>")
    return card_shell(w, h, "Kritagya Yadav — Java & Spring Boot Developer", "\n".join(b), "hero", 0.0)


# ------------------------------------------------ 2. THREE LINKED ACTION TILES
def build_linked_tile(name: str, title: str, subtitle: str, action: str, icon_d: str, color: str, index: int) -> str:
    w, h = 320, 100
    b = [f'  <g font-family="{MONO}">']

    # Platform Icon
    b.append(f"""
    <g transform="translate(24, 28) scale(1.1)">
      <path d="{icon_d}" fill="{color}"/>
    </g>
    <text x="70" y="44" font-size="16" font-weight="700" fill="{TEXT}">{esc(title)}</text>
    <text x="70" y="66" font-size="11" fill="{MUTED}">{esc(subtitle)}</text>
    <rect x="236" y="34" width="62" height="24" rx="12" fill="{PANEL}" stroke="{LINE}" stroke-width="1"/>
    <text x="267" y="50" text-anchor="middle" font-size="10.5" font-weight="600" fill="{CYAN}">{esc(action)}</text>
    """)
    b.append("  </g>")
    return card_shell(w, h, f"{title}: {subtitle}", "\n".join(b), f"tile-{name}", 0.2 + index * 0.15)


# ---------------------------------------------------- 3. TERMINAL PROFILE CARD
def build_profile_card(data: dict) -> str:
    w, h = 1000, 480
    b = [f'  <g font-family="{MONO}">']

    # Title Bar
    b.append(f'    <rect x="1" y="1" width="{w - 2}" height="38" fill="{PANEL}"/>')
    b.append(f'    <line x1="0" y1="39" x2="{w}" y2="39" stroke="{GRID}" stroke-width="1"/>')
    b.append(f'    <circle cx="28" cy="20" r="5" fill="#ff5f56"/>')
    b.append(f'    <circle cx="44" cy="20" r="5" fill="#ffbd2e"/>')
    b.append(f'    <circle cx="60" cy="20" r="5" fill="#27c93f"/>')
    b.append(
        f'    <text x="96" y="24" font-size="12" letter-spacing="1.5" fill="{MUTED}">'
        f'kritagya025@system:~ (bash)</text>'
    )

    y = 74
    # $ whoami
    b.append(f'    <text x="44" y="{y}" font-size="14" fill="{CYAN}">$ <tspan fill="{TEXT}">whoami</tspan></text>')
    y += 26
    fields = [
        ("role", "Java & Spring Boot Developer"),
        ("focus", "Distributed Systems  ·  Backend Architecture  ·  Problem Solving"),
        ("education", "B.Tech CSE (5th Sem) — KCC Institute of Technology (AKTU)"),
        ("location", "Noida, Uttar Pradesh, India"),
        ("contact", "kritagyay2006@gmail.com  ·  +91 8368099806"),
    ]
    for k, v in fields:
        b.append(f'    <text x="64" y="{y}" font-size="13" fill="{MUTED}">{esc(k)}</text>')
        b.append(f'    <text x="170" y="{y}" font-size="13" fill="{SUB}">{esc(v)}</text>')
        y += 24

    y += 12
    # $ cat certifications.json
    b.append(f'    <text x="44" y="{y}" font-size="14" fill="{CYAN}">$ <tspan fill="{TEXT}">cat certifications.json</tspan></text>')
    y += 24
    certs = [
        ("Claude Code in Action", "Anthropic  ·  Mar 2026"),
        ("Cyber Job Simulation", "Deloitte Australia (Forage)"),
    ]
    cx = 64
    for c_title, c_meta in certs:
        cw = 22 + len(c_title + c_meta) * 6.8
        b.append(
            f'    <g><rect x="{cx:.1f}" y="{y - 17}" width="{cw:.1f}" height="24" rx="5" '
            f'fill="{PANEL}" stroke="{LINE}" stroke-width="1"/>'
            f'<text x="{cx + 10:.1f}" y="{y}" font-size="12" fill="{ICE}">'
            f'✓ {esc(c_title)} <tspan fill="{MUTED}">({esc(c_meta)})</tspan></text></g>'
        )
        cx += cw + 14
    y += 34

    # $ cat tech_stack.txt
    b.append(f'    <text x="44" y="{y}" font-size="14" fill="{CYAN}">$ <tspan fill="{TEXT}">cat tech_stack.txt</tspan></text>')
    y += 24
    stacks = [
        ("Languages", ["Java", "Python", "C++", "C", "JavaScript", "HTML/CSS"]),
        ("Backend & Web", ["Spring Boot", "Spring Security", "Node.js", "Express", "Tailwind"]),
        ("Cloud & Tools", ["Docker", "CI/CD", "Linux", "AWS", "Git", "Postman"]),
        ("Databases", ["MySQL", "MongoDB"]),
    ]
    for category, items in stacks:
        b.append(f'    <text x="64" y="{y}" font-size="12.5" fill="{CYAN}">{esc(category)}:</text>')
        ix = 200
        for item in items:
            iw = 14 + len(item) * 7.2
            b.append(
                f'    <g><rect x="{ix:.1f}" y="{y - 15}" width="{iw:.1f}" height="20" rx="4" '
                f'fill="{PANEL}" stroke="{GRID}" stroke-width="1"/>'
                f'<text x="{ix + 7:.1f}" y="{y - 1}" font-size="11" fill="{TEXT}">{esc(item)}</text></g>'
            )
            ix += iw + 8
        y += 26

    y += 10
    # $ status
    b.append(f'    <text x="44" y="{y}" font-size="14" fill="{CYAN}">$ <tspan fill="{TEXT}">status</tspan></text>')
    y += 26
    status_txt = "BUILDING — one commit at a time"
    b.append(f'    <text x="64" y="{y}" font-size="13.5" font-weight="600" fill="{CYAN}">{status_txt}</text>')
    cursor_x = 64 + int(len(status_txt) * 8.0) + 8
    blink = "" if STATIC else '<animate attributeName="opacity" values="1;1;0;0" dur="1.1s" repeatCount="indefinite"/>'
    b.append(f'    <rect x="{cursor_x}" y="{y - 13}" width="8" height="16" fill="{CYAN}">{blink}</rect>')

    b.append("  </g>")
    return card_shell(w, h, "System profile: whoami, certifications and tech stack", "\n".join(b), "profile", 0.4)


# ---------------------------------------------------- 4. SIGNAL & STATS CARD
def build_signal_card(data: dict) -> str:
    w, h = 1000, 340
    p = data.get("profile", {})
    c = data

    total = c.get("total_contributions", 615)
    repos = p.get("repos_count", 27)
    stars = p.get("stars_count", 5)
    followers = p.get("followers_count", 2)
    cur_streak = c.get("current_streak", {}).get("length", 19)
    long_streak = c.get("longest_streak", {}).get("length", 19)

    tiles = [
        (str(total), "contributions / year"),
        (str(repos), "public repositories"),
        (str(stars), "stars earned"),
        (str(followers), "followers"),
        (str(cur_streak), "current streak (days)"),
        (str(long_streak), "longest streak (days)"),
    ]

    b = [f'  <g font-family="{MONO}">']
    b.append(eyebrow(60, 44, "GITHUB SIGNAL // REAL-TIME METRICS"))
    b.append(
        f'    <text x="60" y="96" font-size="11.5" fill="{MUTED}">'
        f'live telemetries · auto-refreshed daily via GitHub Actions</text>'
    )

    # 6 Stat Boxes (2 rows x 3 columns)
    for i, (val, label) in enumerate(tiles):
        col, row = i % 3, i // 3
        bx, by = 60 + col * 154, 126 + row * 84
        b.append(
            f'    <g><rect x="{bx}" y="{by}" width="140" height="68" rx="8" '
            f'fill="{PANEL}" stroke="{GRID}" stroke-width="1"/>'
            f'<text x="{bx + 16}" y="{by + 34}" font-size="26" font-weight="700" fill="{CYAN}">{esc(val)}</text>'
            f'<text x="{bx + 16}" y="{by + 53}" font-size="9.5" fill="{MUTED}">{esc(label)}</text></g>'
        )

    # Divider
    b.append(f'    <line x1="550" y1="112" x2="550" y2="306" stroke="{GRID}" stroke-width="1"/>')

    # Languages Section
    b.append(
        f'    <text x="590" y="132" font-size="12" letter-spacing="2.5" fill="{SUB}">'
        f'MOST USED LANGUAGES</text>'
    )
    b.append(
        f'    <text x="590" y="152" font-size="10.5" fill="{MUTED}">'
        f'by bytes across {repos} public repositories</text>'
    )

    langs = p.get("languages", {})
    sorted_langs = sorted(langs.items(), key=lambda kv: -kv[1])[:5]
    total_bytes = sum(v for _, v in sorted_langs) or 1

    for i, (lname, lbytes) in enumerate(sorted_langs):
        ly = 184 + i * 26
        share = lbytes / total_bytes
        bar_w = max(6, round(180 * share))
        color = LANG_COLOURS.get(lname, CYAN if i == 0 else DIM)

        grow = "" if STATIC else (
            f'<animate attributeName="width" values="0;{bar_w}" dur="1s" begin="{0.5 + i * 0.1:.2f}s" fill="freeze"/>'
        )

        b.append(f'    <text x="590" y="{ly + 4}" font-size="12" fill="{SUB}">{esc(lname)}</text>')
        b.append(f'    <rect x="720" y="{ly - 4}" width="180" height="8" rx="4" fill="{GRID}"/>')
        b.append(
            f'    <rect x="720" y="{ly - 4}" width="{bar_w if STATIC else 0}" height="8" rx="4" fill="{color}">'
            f'{grow}</rect>'
        )
        b.append(f'    <text x="914" y="{ly + 4}" font-size="10.5" fill="{MUTED}">{share * 100:.1f}%</text>')

    b.append("  </g>")
    return card_shell(w, h, "GitHub signal metrics and most used languages", "\n".join(b), "signal", 0.6)


# ---------------------------------------------------- 5. MONTHLY PULSE CHART
def build_chart_card(data: dict) -> str:
    w, h = 1000, 320
    monthly = data.get("monthly", [])[-12:]
    if not monthly:
        monthly = [{"month": "2026-01", "total": 10}]

    max_val = max(m.get("total", 0) for m in monthly) or 1
    total = data.get("total_contributions", 615)
    cur_streak = data.get("current_streak", {}).get("length", 19)
    long_streak = data.get("longest_streak", {}).get("length", 19)
    active_days = data.get("active_days", 120)
    best_day = data.get("best_day", {})

    b = [f'  <g font-family="{MONO}">']
    b.append(eyebrow(60, 44, "CONTRIBUTION PULSE // LAST 12 MONTHS"))

    # Stats sidebar
    stats = [
        (f"{total:,}", "total contributions"),
        (f"{cur_streak} days", "current streak"),
        (f"{long_streak} days", "longest streak"),
        (f"{active_days} days", "active commit days"),
        (f"{best_day.get('count', 23)} commits", f"peak day · {best_day.get('date', 'Aug 27')}"),
    ]
    sx = 730
    for si, (s_val, s_lbl) in enumerate(stats):
        sy = 96 + si * 42
        b.append(
            f'    <text x="{sx}" y="{sy}" font-size="19" font-weight="700" fill="{CYAN}">{esc(s_val)}</text>'
            f'    <text x="{sx}" y="{sy + 15}" font-size="9.5" fill="{MUTED}">{esc(s_lbl)}</text>'
        )

    b.append(f'    <line x1="695" y1="84" x2="695" y2="286" stroke="{GRID}" stroke-width="1"/>')

    # Bars
    chart_x, chart_y = 60, 110
    chart_w, chart_h = 600, 140
    gap = 8
    bw = (chart_w - gap * (len(monthly) - 1)) / len(monthly)

    months_short = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    for i, m in enumerate(monthly):
        bx = chart_x + i * (bw + gap)
        val = m.get("total", 0)
        is_peak = val == max_val and val > 0
        bh = max(6, round((val / max_val) * chart_h))
        by = chart_y + chart_h - bh

        b.append(
            f'    <rect x="{bx:.1f}" y="{chart_y}" width="{bw:.1f}" height="{chart_h}" rx="4" fill="{PANEL}"/>'
        )

        bar_color = CYAN if is_peak else ("#2C9BCB" if i == len(monthly) - 1 else DIM)
        grow = "" if STATIC else (
            f'<animate attributeName="height" values="0;{bh}" dur="0.8s" begin="{0.8 + i * 0.05:.2f}s" fill="freeze"/>'
            f'<animate attributeName="y" values="{chart_y + chart_h};{by}" dur="0.8s" begin="{0.8 + i * 0.05:.2f}s" fill="freeze"/>'
        )

        b.append(
            f'    <rect x="{bx:.1f}" y="{by if STATIC else chart_y + chart_h}" width="{bw:.1f}" '
            f'height="{bh if STATIC else 0}" rx="4" fill="{bar_color}">{grow}</rect>'
        )

        # Month label
        try:
            mi = int(m["month"][5:7]) - 1
            lbl = months_short[mi]
        except Exception:
            lbl = ""
        b.append(
            f'    <text x="{bx + bw / 2:.1f}" y="{chart_y + chart_h + 18}" text-anchor="middle" '
            f'font-size="9.5" fill="{MUTED}">{lbl}</text>'
        )

        # Count above bar
        if val > 0:
            b.append(
                f'    <text x="{bx + bw / 2:.1f}" y="{by - 6}" text-anchor="middle" '
                f'font-size="9" fill="{ICE if is_peak else SUB}">{val}</text>'
            )

    b.append("  </g>")
    return card_shell(w, h, "Monthly contribution activity pulse chart", "\n".join(b), "chart", 0.8)


# ------------------------------------------------ 6. FEATURED REPO CARD (32.5%)
def build_featured_repo_card(repo: dict, index: int) -> str:
    w, h = 320, 170
    name = repo.get("name", "Repository")
    desc = repo.get("description", "Backend service")
    lang = repo.get("language", "Java")
    stars = repo.get("stars", 0)
    forks = repo.get("forks", 0)

    # Wrap description to 2-3 lines
    lines = []
    words = desc.split()
    curr = ""
    for word in words:
        if len(curr) + len(word) + 1 > 32:
            lines.append(curr)
            curr = word
            if len(lines) >= 2:
                break
        else:
            curr = f"{curr} {word}".strip()
    if curr and len(lines) < 2:
        lines.append(curr)
    elif curr:
        lines[-1] = lines[-1][:28] + "..."

    color = LANG_COLOURS.get(lang, CYAN)

    b = [f'  <g font-family="{MONO}">']
    # Background watermark
    b.append(wolf_emblem(240, 20, 70, 0.12, f"repo-{index}-glow"))

    # Top: Language dot + Language Name
    b.append(
        f'    <circle cx="24" cy="28" r="4.5" fill="{color}"/>'
        f'    <text x="36" y="32" font-size="11" fill="{MUTED}">{esc(lang)}</text>'
    )

    # Repo Title
    b.append(
        f'    <text x="24" y="60" font-size="16" font-weight="700" fill="{CYAN}">{esc(name)}</text>'
    )

    # Description lines
    for li, line in enumerate(lines):
        b.append(f'    <text x="24" y="{86 + li * 18}" font-size="11.5" fill="{SUB}">{esc(line)}</text>')

    # Footer metrics
    b.append(
        f'    <line x1="20" y1="134" x2="300" y2="134" stroke="{GRID}" stroke-width="1"/>'
        f'    <text x="24" y="152" font-size="11" fill="{MUTED}">★ {stars}  ·  ⑂ {forks}</text>'
        f'    <text x="296" y="152" text-anchor="end" font-size="11" fill="{CYAN}">view ↗</text>'
    )

    b.append("  </g>")
    return card_shell(w, h, f"Repository: {name}", "\n".join(b), f"repo-{index}", 1.0 + index * 0.15)


# ---------------------------------------------------- 7. CONTRIBUTION TRAIL
def build_trail_card(data: dict) -> str:
    w, h = 1000, 290
    days = data.get("days", [])
    if len(days) > 371:
        days = days[-371:]

    total = data.get("total_contributions", 615)
    active = data.get("active_days", 120)

    cell, pitch = 12, 15
    x0, y0 = 76, 118

    first = dt.date.fromisoformat(days[0]["date"]) if days else dt.date.today()
    lead = (first.weekday() + 1) % 7

    b = [f'  <g font-family="{MONO}">']
    b.append(eyebrow(60, 44, "CONTRIBUTION TRAIL // 53-WEEK CALENDAR"))
    b.append(
        f'    <text x="60" y="94" font-size="11.5" fill="{MUTED}">'
        f'consistency leaves tracks · {total:,} contributions, {active} active days recorded</text>'
    )

    # Day labels
    for di, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        b.append(f'    <text x="{x0 - 36}" y="{y0 + di * pitch + cell - 2}" font-size="10" fill="{MUTED}">{name}</text>')

    # Month labels
    months_short = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    seen_months = set()
    for i, d in enumerate(days):
        k = i + lead
        col, row = divmod(k, 7)
        d_obj = dt.date.fromisoformat(d["date"])
        if d_obj.day <= 7 and (d_obj.year, d_obj.month) not in seen_months and row == 0:
            seen_months.add((d_obj.year, d_obj.month))
            b.append(
                f'    <text x="{x0 + col * pitch}" y="{y0 - 12}" font-size="10.5" fill="{MUTED}">'
                f'{months_short[d_obj.month - 1]}</text>'
            )

    # Cells
    for i, d in enumerate(days):
        k = i + lead
        col, row = divmod(k, 7)
        lvl = min(d.get("level", 0), 4)
        c_fill = HEAT[lvl]
        b.append(
            f'    <rect x="{x0 + col * pitch}" y="{y0 + row * pitch}" width="{cell}" height="{cell}" '
            f'rx="2.5" fill="{c_fill}">'
            f'<title>{d["date"]}: {d["count"]} contribution{"s" if d["count"] != 1 else ""}</title></rect>'
        )

    # Legend
    ly = y0 + 7 * pitch + 28
    b.append(f'    <text x="{x0}" y="{ly}" font-size="10.5" fill="{MUTED}">less</text>')
    for i, colour in enumerate(HEAT):
        b.append(
            f'    <rect x="{x0 + 38 + i * 16}" y="{ly - 10}" width="{cell}" height="{cell}" rx="2.5" fill="{colour}"/>'
        )
    b.append(f'    <text x="{x0 + 38 + len(HEAT) * 16 + 8}" y="{ly}" font-size="10.5" fill="{MUTED}">more</text>')

    # Wolf watermark
    b.append(wolf_emblem(900, ly - 56, 60, 0.35, "trail-glow"))

    b.append("  </g>")
    return card_shell(w, h, "53-week contribution calendar heatmap", "\n".join(b), "trail", 1.2)


# ---------------------------------------------------- 8. FOOTER CARD
def build_footer_card(data: dict) -> str:
    w, h = 1000, 292
    b = [f'  <g font-family="{MONO}">']
    b.append(wolf_emblem(462, 34, 76, 0.95, "footer-glow"))
    b.append(
        f'    <text x="{w // 2}" y="148" text-anchor="middle" font-size="17" letter-spacing="4" fill="{TEXT}">'
        f'QUIET IN APPROACH.  PRECISE IN EXECUTION.</text>'
    )
    b.append(f'    <line x1="330" y1="170" x2="670" y2="170" stroke="{LINE}" stroke-width="1"/>')

    cols = [
        ("STATUS", "BUILDING"),
        ("MODE", "PRECISE EXECUTION"),
        ("NEXT", "CLOUD & INFRASTRUCTURE"),
    ]
    for ci, (ckey, cval) in enumerate(cols):
        cx = 210 + ci * 290
        b.append(
            f'    <text x="{cx}" y="204" text-anchor="middle" font-size="10" letter-spacing="2" fill="{MUTED}">{ckey}</text>'
            f'    <text x="{cx}" y="226" text-anchor="middle" font-size="12.5" letter-spacing="1" fill="{CYAN}">{cval}</text>'
        )

    today_str = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    b.append(
        f'    <text x="{w // 2}" y="262" text-anchor="middle" font-size="10.5" fill="{MUTED}">'
        f'cards auto-refreshed daily via GitHub Actions · {today_str}</text>'
    )

    b.append("  </g>")
    return card_shell(w, h, "Quiet in approach. Precise in execution.", "\n".join(b), "footer", 1.4)


# ================================================================ MAIN
def main():
    if not os.path.exists(DATA):
        print(f"Error: {DATA} not found! Run fetch_contributions.py first.")
        return 1

    with open(DATA, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Hero
    write_card("hero.svg", build_hero(data))

    # 2. Three Linked Action Tiles (width="32.5%")
    icons = {
        "linkedin": "M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.32 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.79M6.88 8.56a1.68 1.68 0 0 0 1.68-1.68c0-.93-.75-1.69-1.68-1.69a1.69 1.69 0 0 0-1.69 1.69c0 .93.76 1.68 1.69 1.68m1.39 9.94v-8.37H5.5v8.37h2.77z",
        "github": "M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0 0 22 12.017C22 6.484 17.522 2 12 2z",
        "email": "M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4-8 5-8-5V6l8 5 8-5v2z"
    }
    write_card("tile-linkedin.svg", build_linked_tile("linkedin", "LINKEDIN", "in/kritagya-yadav", "Connect", icons["linkedin"], "#0A66C2", 0))
    write_card("tile-github.svg", build_linked_tile("github", "GITHUB", "@kritagya025  ·  27 repos", "Follow", icons["github"], TEXT, 1))
    write_card("tile-email.svg", build_linked_tile("email", "EMAIL", "kritagyay2006@gmail.com", "Contact", icons["email"], "#EA4335", 2))

    # 3. Profile Terminal Card ($ whoami, certifications, tech stack)
    write_card("profile.svg", build_profile_card(data))

    # 4. Signal & Metrics Card
    write_card("signal.svg", build_signal_card(data))

    # 5. Monthly Contribution Pulse Chart
    write_card("chart.svg", build_chart_card(data))

    # 6. Featured Repositories (6 individual cards)
    featured = data.get("profile", {}).get("featured", [])
    for idx, repo in enumerate(featured):
        write_card(f"repo-{repo['name']}.svg", build_featured_repo_card(repo, idx))

    # 7. Contribution Trail
    write_card("trail.svg", build_trail_card(data))

    # 8. Footer Card
    write_card("footer.svg", build_footer_card(data))

    print("All rich dark cyberpunk cards rendered successfully!")
    return 0


if __name__ == "__main__":
    main()
