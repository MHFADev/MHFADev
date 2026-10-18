#!/usr/bin/env python3
"""Generate animated, data-backed SVG panels for the MHFADev profile README."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

USER = os.getenv("GITHUB_USERNAME", "MHFADev")
TOKEN = os.getenv("GITHUB_TOKEN", "")
OUT = Path(os.getenv("OUTPUT_DIR", "dist"))
API = "https://api.github.com"
NOW = datetime.now(timezone.utc)


def request_json(url: str, method: str = "GET", payload: dict | None = None) -> dict | list:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "MHFADev-profile-animations"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def safe_request(url: str, fallback):
    try:
        return request_json(url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return fallback


def graphql_contributions() -> dict:
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalRepositoryContributions
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
        }
      }
    }
    """
    try:
        result = request_json(
            "https://api.github.com/graphql",
            method="POST",
            payload={"query": query, "variables": {"login": USER}},
        )
        return result.get("data", {}).get("user", {}).get("contributionsCollection", {})
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return {}


def load_data() -> dict:
    user = safe_request(f"{API}/users/{urllib.parse.quote(USER)}", {})
    repos = safe_request(
        f"{API}/users/{urllib.parse.quote(USER)}/repos?per_page=100&sort=updated&type=owner",
        [],
    )
    repos = [r for r in repos if not r.get("fork")]
    languages = Counter()
    for repo in repos[:30]:
        lang = safe_request(repo.get("languages_url", ""), {})
        if isinstance(lang, dict):
            languages.update(lang)
    contributions = graphql_contributions()
    calendar = contributions.get("contributionCalendar", {})
    days = [day for week in calendar.get("weeks", []) for day in week.get("contributionDays", [])]
    recent_days = [d for d in days if d.get("date", "") >= (NOW - timedelta(days=29)).date().isoformat()]
    recent_total = sum(d.get("contributionCount", 0) for d in recent_days)
    recent_events = safe_request(f"{API}/users/{urllib.parse.quote(USER)}/events/public?per_page=100", [])
    event_counts = Counter(e.get("type", "Event") for e in recent_events if isinstance(e, dict))
    stars = sum(int(r.get("stargazers_count", 0)) for r in repos)
    forks = sum(int(r.get("forks_count", 0)) for r in repos)
    top_repos = sorted(repos, key=lambda r: (r.get("stargazers_count", 0), r.get("updated_at", "")), reverse=True)[:6]
    top_languages = languages.most_common(7)
    total_bytes = sum(languages.values()) or 1
    return {
        "login": user.get("login", USER),
        "name": user.get("name") or USER,
        "avatar": user.get("avatar_url", ""),
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "public_repos": user.get("public_repos", len(repos)),
        "created": (user.get("created_at", "")[:10] or "unknown"),
        "stars": stars,
        "forks": forks,
        "total_contributions": calendar.get("totalContributions", sum(d.get("contributionCount", 0) for d in days)),
        "recent_total": recent_total,
        "days": recent_days[-30:],
        "languages": [(name, value, round(value / total_bytes * 100)) for name, value in top_languages],
        "repos": top_repos,
        "events": event_counts,
        "updated": NOW.strftime("%Y-%m-%d %H:%M UTC"),
    }


def esc(value) -> str:
    return escape(str(value), quote=True)


def common_defs() -> str:
    return """<defs>
      <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#070d1b"/><stop offset=".55" stop-color="#0b1530"/><stop offset="1" stop-color="#151238"/></linearGradient>
      <linearGradient id="cyan" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#67e8f9"/><stop offset=".55" stop-color="#22d3ee"/><stop offset="1" stop-color="#818cf8"/></linearGradient>
      <linearGradient id="pink" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#f9a8d4"/><stop offset="1" stop-color="#fbbf24"/></linearGradient>
      <pattern id="grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="#94a3b8" stroke-opacity=".045"/></pattern>
      <filter id="glow"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      <filter id="soft"><feGaussianBlur stdDeviation="10"/></filter>
      <style>text{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.muted{fill:#94a3b8}.label{fill:#dbeafe;font-size:11px;letter-spacing:.3px}.value{fill:#f8fafc;font-size:25px;font-weight:700;letter-spacing:-.8px}.tiny{fill:#64748b;font-size:9px;letter-spacing:.35px}.eyebrow{fill:#67e8f9;font-size:10px;letter-spacing:2.2px;font-weight:700}</style>
    </defs>"""


def shell(title: str, subtitle: str, body: str, height: int = 220, link: str = "https://github.com/MHFADev") -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="900" height="{height}" viewBox="0 0 900 {height}">
  <title>{esc(title)} — {esc(subtitle)}</title>{common_defs()}
  <a href="{link}"><rect width="900" height="{height}" rx="18" fill="url(#bg)" stroke="#2b3b67"/><rect width="900" height="{height}" rx="18" fill="url(#grid)"/><rect x="1" y="1" width="898" height="{height-2}" rx="17" fill="none" stroke="#67e8f9" stroke-opacity=".16"/><path d="M28 72H872" stroke="#334155" stroke-opacity=".48"/><circle cx="28" cy="34" r="3" fill="#67e8f9"/><circle cx="38" cy="34" r="3" fill="#a78bfa" opacity=".7"/><circle cx="48" cy="34" r="3" fill="#f9a8d4" opacity=".7"/></a>
  <text x="64" y="38" class="eyebrow">MHFADEV // {esc(title.upper())}</text>
  <text x="28" y="56" class="muted" font-size="11">{esc(subtitle)}</text>
  {body}
  <text x="872" y="{height-18}" text-anchor="end" class="tiny">LIVE SNAPSHOT · {esc(NOW.strftime('%Y-%m-%d %H:%M UTC'))}</text>
</svg>'''


def command_center(d: dict) -> str:
    cards = [("REPOSITORIES", d["public_repos"], "#22d3ee"), ("FOLLOWERS", d["followers"], "#8b5cf6"), ("STARS", d["stars"], "#fbbf24"), ("30D OUTPUT", d["recent_total"], "#f472b6")]
    body = []
    for i, (label, value, color) in enumerate(cards):
        x = 28 + i * 214
        body.append(f'''<g transform="translate({x},86)"><rect width="194" height="82" rx="14" fill="#0b1630" fill-opacity=".84" stroke="{color}" stroke-opacity=".34"/><circle cx="18" cy="20" r="4" fill="{color}" filter="url(#glow)"><animate attributeName="r" values="3;5;3" dur="3.6s" repeatCount="indefinite"/></circle><text x="32" y="24" class="label">{esc(label)}</text><text x="16" y="60" class="value">{esc(value)}</text><path d="M16 70h162" stroke="{color}" stroke-opacity=".22" stroke-dasharray="2 9"><animate attributeName="stroke-dashoffset" from="0" to="-22" dur="1.8s" repeatCount="indefinite"/></path></g>''')
    return shell("COMMAND CENTER", f"{d['name']} // profile telemetry is synced from GitHub API", "".join(body), 220)


def contribution_pulse(d: dict) -> str:
    days = d["days"] or [{"contributionCount": 0} for _ in range(30)]
    max_count = max([day.get("contributionCount", 0) for day in days] + [1])
    bars = []
    for i, day in enumerate(days[-30:]):
        count = day.get("contributionCount", 0)
        h = max(4, round(count / max_count * 92))
        x = 28 + i * 28
        bars.append(f'''<rect x="{x}" y="{174-h}" width="15" height="{h}" rx="4" fill="url(#cyan)" opacity="{0.35 + count/max_count*.65:.2f}"><title>{esc(day.get('date',''))}: {count} contributions</title><animate attributeName="y" values="{174-h};{174-h-3};{174-h}" dur="{1.6 + i/20:.2f}s" repeatCount="indefinite"/><animate attributeName="opacity" values=".45;1;.45" dur="2.8s" repeatCount="indefinite"/></rect>''')
    line = "M28 174 " + " ".join(f"L{28+i*28+7} {174-max(4, round(day.get('contributionCount',0)/max_count*92))}" for i, day in enumerate(days[-30:]))
    body = f'''<text x="28" y="84" class="label">LAST 30 DAYS · <tspan fill="#22d3ee" font-weight="700">{d['recent_total']} contributions</tspan></text><path d="M28 174H850" stroke="#334155"/><path d="{line}" fill="none" stroke="#fbbf24" stroke-width="2" stroke-dasharray="5 8"><animate attributeName="stroke-dashoffset" from="0" to="-26" dur="1.2s" repeatCount="indefinite"/></path>{''.join(bars)}<circle cx="840" cy="102" r="5" fill="#f472b6" filter="url(#glow)"><animate attributeName="r" values="4;10;4" dur="1.5s" repeatCount="indefinite"/></circle>'''
    return shell("CONTRIBUTION PULSE", "A living 30-day activity waveform · hover any bar for the exact day", body, 220, "https://github.com/MHFADev?tab=overview")


def language_orbit(d: dict) -> str:
    colors = ["#22d3ee", "#f472b6", "#fbbf24", "#8b5cf6", "#34d399", "#fb7185", "#a78bfa"]
    nodes = []
    cx, cy = 450, 125
    for i, (name, _, pct) in enumerate(d["languages"] or [("Code", 1, 100)]):
        angle = i / max(1, len(d["languages"])) * 6.283
        x, y = round(cx + 170 * math.cos(angle), 1), round(cy + 70 * math.sin(angle), 1)
        color = colors[i % len(colors)]
        nodes.append(f'''<g><ellipse cx="{cx}" cy="{cy}" rx="{90+i*16}" ry="{37+i*6}" fill="none" stroke="{color}" stroke-opacity=".15" stroke-dasharray="3 11" transform="rotate({i*17} {cx} {cy})"><animateTransform attributeName="transform" type="rotate" from="{i*17} {cx} {cy}" to="{360+i*17} {cx} {cy}" dur="{26+i*3}s" repeatCount="indefinite"/></ellipse><circle cx="{x}" cy="{y}" r="8" fill="{color}" filter="url(#glow)"><animate attributeName="r" values="7;9;7" dur="{3+i*.3}s" repeatCount="indefinite"/></circle><text x="{x+15}" y="{y+4}" class="label">{esc(name)} <tspan fill="#94a3b8">{pct}%</tspan></text></g>''')
    body = f'''<circle cx="{cx}" cy="{cy}" r="34" fill="#0b1630" stroke="#22d3ee" stroke-opacity=".5"/><text x="{cx}" y="{cy-2}" text-anchor="middle" fill="#f8fafc" font-size="12" font-weight="700">STACK</text><text x="{cx}" y="{cy+14}" text-anchor="middle" class="tiny">IN MOTION</text>{''.join(nodes)}'''
    return shell("LANGUAGE ORBIT", "Repository language mix · each orbit is proportional to your current stack", body, 220, "https://github.com/MHFADev?tab=repositories")


def commit_velocity(d: dict) -> str:
    events = d["events"]
    rows = [("PushEvent", events.get("PushEvent", 0), "COMMITS / PUSHES", "#22d3ee"), ("PullRequestEvent", events.get("PullRequestEvent", 0), "PULL REQUESTS", "#8b5cf6"), ("IssuesEvent", events.get("IssuesEvent", 0), "ISSUE EVENTS", "#f472b6")]
    body = []
    for i, (_, value, label, color) in enumerate(rows):
        y = 94 + i*38
        width = min(690, 20 + value * 45)
        body.append(f'''<text x="28" y="{y}" class="label">{label}</text><rect x="184" y="{y-12}" width="690" height="14" rx="7" fill="#17233f"/><rect x="184" y="{y-12}" width="{width}" height="14" rx="7" fill="{color}" opacity=".82"><animate attributeName="width" from="0" to="{width}" dur="1.4s" fill="freeze"/><animate attributeName="opacity" values=".55;1;.55" dur="2.5s" repeatCount="indefinite"/></rect><text x="{min(850, 194+width)}" y="{y+1}" class="label">{value}</text>''')
    body.append('<path d="M30 190H870" stroke="#334155" stroke-dasharray="2 9"><animate attributeName="stroke-dashoffset" from="0" to="-22" dur="1s" repeatCount="indefinite"/></path>')
    return shell("COMMIT VELOCITY", "Public event telemetry from the latest GitHub activity stream", "".join(body), 220, "https://github.com/MHFADev?tab=activity")


def project_constellation(d: dict) -> str:
    colors = ["#22d3ee", "#8b5cf6", "#f472b6", "#fbbf24", "#34d399", "#fb7185"]
    repos = d["repos"] or [{"name": "MHFADev", "stargazers_count": 0, "html_url": "https://github.com/MHFADev"}]
    nodes = []
    for i, repo in enumerate(repos):
        x = 34 + (i % 2) * 432
        y = 94 + (i // 2) * 39
        color = colors[i % len(colors)]
        name = repo.get("name", "project")[:24]
        stars = repo.get("stargazers_count", 0)
        nodes.append(f'''<a href="{esc(repo.get('html_url', 'https://github.com/MHFADev'))}"><g><rect x="{x}" y="{y-18}" width="400" height="30" rx="10" fill="#0b1630" fill-opacity=".72" stroke="{color}" stroke-opacity=".2"/><circle cx="{x+16}" cy="{y-3}" r="5" fill="{color}" filter="url(#glow)"><animate attributeName="r" values="4;6;4" dur="{3+i*.25}s" repeatCount="indefinite"/></circle><text x="{x+30}" y="{y+1}" class="label">{esc(name)}</text><text x="{x+380}" y="{y+1}" text-anchor="end" class="tiny">★ {stars} · OPEN</text></g></a>''')
    body = f'''<text x="28" y="84" class="label">TOP PROJECTS BY STARS · <tspan fill="#fbbf24">{d['stars']} total stars across owned repos</tspan></text>{''.join(nodes)}'''
    return shell("PROJECT CONSTELLATION", "Your most visible repositories, connected as a living project map", body, 220, "https://github.com/MHFADev?tab=repositories")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = load_data()
    panels = {
        "profile-command-center.svg": command_center(data),
        "profile-contribution-pulse.svg": contribution_pulse(data),
        "profile-language-orbit.svg": language_orbit(data),
        "profile-commit-velocity.svg": commit_velocity(data),
        "profile-project-constellation.svg": project_constellation(data),
    }
    for name, svg in panels.items():
        (OUT / name).write_text(svg, encoding="utf-8")
    print(f"Generated {len(panels)} animated panels for {USER} at {data['updated']}")


if __name__ == "__main__":
    main()
