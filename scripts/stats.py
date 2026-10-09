#!/usr/bin/env python3
"""Builds stats.svg for the profile README. Standard library only.

Data sources
  * contribution calendar: public page github.com/users/<user>/contributions (no token needed)
  * repos / stars / followers / languages: GitHub REST API (uses GH_TOKEN when present)
If something is unavailable the card simply shows what it has - it never renders blanks.
"""
import os, re, sys, json, html, datetime, urllib.request

USER = os.environ.get('GH_USER') or os.environ.get('GITHUB_REPOSITORY_OWNER') or 'waseeqshah'
TOKEN = os.environ.get('GH_TOKEN', '')
OUT = os.environ.get('STATS_OUT', 'stats.svg')

def http(url, headers=None):
    req = urllib.request.Request(url, headers={'User-Agent': 'profile-stats', **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')

def api(path):
    h = {'Accept': 'application/vnd.github+json'}
    if TOKEN:
        h['Authorization'] = f'Bearer {TOKEN}'
    return json.loads(http('https://api.github.com' + path, h))

# ---------------------------------------------------------------- data
def contributions():
    h = http(f'https://github.com/users/{USER}/contributions')
    tips = {m.group(1): m.group(2) for m in re.finditer(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', h)}
    days = []
    for m in re.finditer(r'<td\b[^>]*>', h):
        tag = m.group(0)
        d = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', tag)
        if not d:
            continue
        lv = re.search(r'data-level="(\d)"', tag)
        i = re.search(r'\bid="([^"]+)"', tag)
        tip = tips.get(i.group(1), '') if i else ''
        n = re.match(r'(\d[\d,]*)\s+contribution', tip)
        cnt = int(n.group(1).replace(',', '')) if n else 0
        level = int(lv.group(1)) if lv else (1 if cnt else 0)
        if cnt == 0 and level > 0 and not tip:
            cnt = level
        days.append((datetime.date.fromisoformat(d.group(1)), cnt, level))
    days.sort()
    if not days:
        raise RuntimeError('contribution calendar not found')
    t = re.search(r'(\d[\d,]*)\s+contributions?\s+in\s+the\s+last\s+year', h)
    total = int(t.group(1).replace(',', '')) if t else sum(c for _, c, _ in days)

    cur = 0
    seq = [c for _, c, _ in days]
    k = len(seq) - 1
    if k >= 0 and seq[k] == 0:      # today may still be empty without breaking the streak
        k -= 1
    while k >= 0 and seq[k] > 0:
        cur += 1; k -= 1
    best = run = 0
    for c in seq:
        run = run + 1 if c > 0 else 0
        best = max(best, run)
    active = sum(1 for c in seq if c > 0)
    top = max(days, key=lambda x: x[1])
    return dict(days=days, total=total, current=cur, longest=best, active=active, top=top)

def rest():
    u = api(f'/users/{USER}')
    repos, page = [], 1
    while page <= 3:
        part = api(f'/users/{USER}/repos?per_page=100&type=owner&page={page}')
        repos += part
        if len(part) < 100:
            break
        page += 1
    own = [r for r in repos if not r.get('fork')]
    langs = {}
    for r in own[:40]:
        try:
            for k, v in api(f"/repos/{USER}/{r['name']}/languages").items():
                langs[k] = langs.get(k, 0) + v
        except Exception:
            pass
    return dict(repos=u.get('public_repos', len(repos)), followers=u.get('followers'),
                stars=sum(r.get('stargazers_count', 0) for r in own), langs=langs)

def repos_from_profile():
    p = http(f'https://github.com/{USER}')
    m = re.search(r'Repositories\s*<span[^>]*title="(\d+)"', p)
    return int(m.group(1)) if m else None

# ---------------------------------------------------------------- render
CYAN, PURPLE, GREEN = '#22D3EE', '#A78BFA', '#10B981'
LV = ['#161B22', '#164E63', '#0891B2', '#22D3EE', '#A5F3FC']
LANG_COLORS = {'Python': '#A78BFA', 'JavaScript': '#FBBF24', 'TypeScript': '#38BDF8', 'C++': '#22D3EE', 'C': '#94A3B8',
               'HTML': '#FB7185', 'CSS': '#818CF8', 'Shell': '#10B981', 'Java': '#F59E0B', 'Go': '#2DD4BF', 'PHP': '#A78BFA',
               'Rust': '#FDBA74', 'Jupyter Notebook': '#FB923C', 'Dockerfile': '#38BDF8', 'Batchfile': '#10B981'}
FALLBACK = [CYAN, PURPLE, GREEN, '#FBBF24', '#FB7185']
FONT = "'JetBrains Mono','SF Mono',Consolas,'Courier New',monospace"
esc = lambda s: html.escape(str(s), quote=False)

def render(c, r):
    W, H = 1180, 318
    days = c['days']
    first = days[0][0]
    start = first - datetime.timedelta(days=(first.weekday() + 1) % 7)   # Sunday of first week
    cols = (days[-1][0] - start).days // 7 + 1
    PITCH, CELL, HX, HY = 14, 11, 34, 160
    hm_w = cols * PITCH

    # tiles
    tiles = []
    if r.get('repos') is not None: tiles.append(('REPOS', r['repos'], ''))
    if r.get('stars') is not None: tiles.append(('STARS', r['stars'], ''))
    if r.get('followers') is not None: tiles.append(('FOLLOWERS', r['followers'], ''))
    tiles.append(('CONTRIBUTIONS · 12M', c['total'], ''))
    tiles.append(('CURRENT STREAK', c['current'], 'day' if c['current'] == 1 else 'days'))
    tiles.append(('LONGEST STREAK', c['longest'], 'day' if c['longest'] == 1 else 'days'))
    span = (W - 68) / len(tiles)
    tl = []
    for i, (lab, val, unit) in enumerate(tiles):
        x = 34 + i * span
        u = f'<tspan font-size="12" fill="#64748B" dx="6">{unit}</tspan>' if unit else ''
        tl.append(f'<g class="tile" style="animation-delay:{0.15*i+0.2:.2f}s">'
                  f'<rect x="{x:.1f}" y="66" width="22" height="2" fill="{CYAN if i % 2 == 0 else PURPLE}"/>'
                  f'<text x="{x:.1f}" y="88" font-size="10" fill="#64748B" letter-spacing="1.5">{lab}</text>'
                  f'<text x="{x:.1f}" y="122" font-size="32" font-weight="700" fill="#F8FAFC">{esc(val)}{u}</text></g>')

    # heatmap
    cells, months, last_x = [], [], -99
    for d, n, lvl in days:
        col, row = (d - start).days // 7, (d.weekday() + 1) % 7
        x, y = HX + col * PITCH, HY + row * PITCH
        cells.append(f'<rect class="cell" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" fill="{LV[min(lvl, 4)]}" style="animation-delay:{0.35 + col*0.02:.2f}s"/>')
        if row == 0 and d.day <= 7 and x - last_x > 44:
            months.append(f'<text x="{x}" y="{HY-8}" font-size="10" fill="#64748B">{d.strftime("%b")}</text>')
            last_x = x
    ld = days[-1][0]
    tcol, trow = (ld - start).days // 7, (ld.weekday() + 1) % 7
    today = f'<rect class="today" x="{HX+tcol*PITCH-2}" y="{HY+trow*PITCH-2}" width="{CELL+4}" height="{CELL+4}" rx="4" fill="none" stroke="{CYAN}" stroke-width="1.2"/>'
    legend = ''.join(f'<rect x="{HX+34+i*16}" y="{HY+7*PITCH+12}" width="11" height="11" rx="2.5" fill="{LV[i]}"/>' for i in range(5))
    legend = (f'<text x="{HX}" y="{HY+7*PITCH+21}" font-size="10" fill="#64748B">less</text>{legend}'
              f'<text x="{HX+34+5*16+4}" y="{HY+7*PITCH+21}" font-size="10" fill="#64748B">more</text>')

    # right panel
    px, pw = HX + hm_w + 44, W - 34 - (HX + hm_w + 44)
    langs = sorted((r.get('langs') or {}).items(), key=lambda kv: -kv[1])[:5]
    if langs:
        tot = sum(r['langs'].values())
        rows = [f'<text x="{px}" y="{HY-8}" font-size="10" fill="#64748B" letter-spacing="1.5">TOP LANGUAGES</text>']
        for i, (name, v) in enumerate(langs):
            y = HY + 14 + i * 26
            pct = v * 100 / tot
            col = LANG_COLORS.get(name, FALLBACK[i % 5])
            rows.append(f'<text x="{px}" y="{y}" font-size="12" fill="#E2E8F0">{esc(name)}</text>'
                        f'<text x="{px+pw}" y="{y}" font-size="12" fill="#94A3B8" text-anchor="end">{pct:.1f}%</text>'
                        f'<rect x="{px}" y="{y+7}" width="{pw}" height="5" rx="2.5" fill="#161B22"/>'
                        f'<rect class="bar" x="{px}" y="{y+7}" width="{max(pw*pct/100, 5):.1f}" height="5" rx="2.5" fill="{col}" style="animation-delay:{0.6+i*0.15:.2f}s"/>')
        right = ''.join(rows)
    else:
        top = c['top']
        items = [('active days', c['active']),
                 ('best day', f"{top[1]} · {top[0].strftime('%b')} {top[0].day}" if top[1] else '—'),
                 ('per active day', f"{c['total']/c['active']:.1f}" if c['active'] else '—')]
        rows = [f'<text x="{px}" y="{HY-8}" font-size="10" fill="#64748B" letter-spacing="1.5">ACTIVITY</text>']
        for i, (k, v) in enumerate(items):
            y = HY + 20 + i * 34
            rows.append(f'<g class="tile" style="animation-delay:{0.7+i*0.15:.2f}s"><text x="{px}" y="{y}" font-size="12" fill="#94A3B8">{k}</text>'
                        f'<text x="{px+pw}" y="{y}" font-size="14" font-weight="700" fill="{CYAN}" text-anchor="end">{esc(v)}</text>'
                        f'<rect x="{px}" y="{y+9}" width="{pw}" height="1" fill="#1E2D45"/></g>')
        right = ''.join(rows)

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="GitHub stats for {esc(USER)}">
<title>GitHub stats - {esc(USER)}</title>
<defs><linearGradient id="bar" x1="0" x2="1"><stop offset="0" stop-color="#162035"/><stop offset="1" stop-color="#101827"/></linearGradient>
<linearGradient id="ln" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}" stop-opacity=".6"/><stop offset=".6" stop-color="{PURPLE}" stop-opacity=".3"/><stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></linearGradient></defs>
<style>
text{{font-family:{FONT}}}
.cell{{transform-box:fill-box;transform-origin:center;animation:pop .45s ease-out backwards}}
@keyframes pop{{from{{opacity:0;transform:scale(.3)}}}}
.tile{{animation:rise .7s cubic-bezier(.2,.7,.2,1) backwards}}
@keyframes rise{{from{{opacity:0;transform:translateY(10px)}}}}
.bar{{transform-box:fill-box;transform-origin:left center;animation:grow 1.1s cubic-bezier(.2,.7,.2,1) backwards}}
@keyframes grow{{from{{transform:scaleX(0)}}}}
.today{{animation:ring 2s ease-in-out infinite}}
@keyframes ring{{50%{{opacity:.15}}}}
.dot{{animation:ring 2.4s ease-in-out infinite}}
</style>
<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="12" fill="#0D1117" stroke="{CYAN}" stroke-opacity=".35"/>
<path d="M.5 12.5a12 12 0 0 1 12-12H{W-12.5}a12 12 0 0 1 12 12V46H.5Z" fill="url(#bar)"/>
<rect x=".5" y="46" width="{W-1}" height="1" fill="{CYAN}" fill-opacity=".25"/>
<circle cx="28" cy="24" r="6.5" fill="#FF5F57"/><circle cx="50" cy="24" r="6.5" fill="#FFBD2E"/><circle cx="72" cy="24" r="6.5" fill="#28CA41"/>
<text x="{W/2}" y="29" font-size="12" fill="#64748B" text-anchor="middle" letter-spacing="1">visitor@github: ~/stats --live</text>
<circle class="dot" cx="{W-34}" cy="24" r="4" fill="{GREEN}"/>
{''.join(tl)}
<rect x="34" y="134" width="{W-68}" height="1" fill="url(#ln)"/>
{''.join(months)}
{''.join(cells)}
{today}
{legend}
{right}
<text x="{W-34}" y="{H-14}" font-size="10" fill="#334155" text-anchor="end">auto-updated · {stamp}</text>
</svg>'''

def main():
    c = contributions()
    try:
        r = rest()
    except Exception as e:
        print('REST unavailable, using page data only:', e, file=sys.stderr)
        r = {'repos': None, 'followers': None, 'stars': None, 'langs': {}}
        try:
            r['repos'] = repos_from_profile()
        except Exception:
            pass
    svg = render(c, r)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(svg)
    print(f'wrote {OUT} ({len(svg)//1024} KB): total={c["total"]} current={c["current"]} longest={c["longest"]} repos={r.get("repos")}')

if __name__ == '__main__':
    main()
