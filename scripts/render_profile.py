from pathlib import Path
from html import escape
import datetime
import json
import math
from urllib.parse import urlparse
from string import Template

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'profile/assets'
DATA = json.loads((ROOT / 'profile/momentum.json').read_text())
CONTENT = json.loads((ROOT / 'profile/content.json').read_text())
ROWS = DATA['weeks']
if len(ROWS) != 12:
    raise ValueError('Expected twelve complete weeks')
for i, row in enumerate(ROWS):
    start = datetime.date.fromisoformat(row['start'])
    end = datetime.date.fromisoformat(row['end'])
    if start.weekday() != 0 or end - start != datetime.timedelta(days=6):
        raise ValueError('Weeks must run Monday through Sunday')
    if i and start != datetime.date.fromisoformat(ROWS[i-1]['end']) + datetime.timedelta(days=1):
        raise ValueError('Weeks must be consecutive')
    if type(row['merged']) is not int or row['merged'] < 0:
        raise ValueError('Counts must be nonnegative integers')
if DATA['timezone'] != 'America/Toronto':
    raise ValueError('Expected America/Toronto time')
captured = datetime.date.fromisoformat(DATA['asOf'])
if datetime.date.fromisoformat(ROWS[-1]['end']) >= captured:
    raise ValueError('Snapshot must exclude the current incomplete week')
for link in [*CONTENT['links'], CONTENT['footerLink']]:
    if urlparse(link['url']).scheme not in ('https', 'mailto'):
        raise ValueError('Use https or mailto links')
for item in CONTENT['highlights']:
    datetime.date.fromisoformat(item['mergedOn'])
FONT = '-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif'
ceiling = max(300, math.ceil(max(r['merged'] for r in ROWS) * 1.12 / 300) * 300)
summary = escape('Weekly merged pull requests, ' + ROWS[0]['start'] + ' to ' + ROWS[-1]['end'] + '.')
def wrap(width, height, content, description):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img"><title>{description}</title><g font-family="{FONT}">{content}</g></svg>\n'
for theme in ['light', 'dark']:
    dark = theme == 'dark'
    bg, fg, muted = ('#0d1117', '#e6edf3', '#9da7b3') if dark else ('#ffffff', '#1f2328', '#59636e')
    green, bar, border = ('#63d9a4', '#204f3b', '#30363d') if dark else ('#156a46', '#c9e3d6', '#d1d9e0')
    for compact in [False, True]:
        width, height = (360, 285) if compact else (960, 340)
        left, right, top, bottom = (34, 12, 37, 86) if compact else (45, 16, 40, 84)
        step = (width-left-right)/len(ROWS)
        plot_height = height-top-bottom
        x = lambda i: left + step*(i+.5)
        y = lambda value: top + plot_height*(1-value/ceiling)
        size = 12 if compact else 16
        content = f'<rect width="{width}" height="{height}" fill="{bg}"/>'
        content += f'<text x="{left}" y="18" fill="{muted}" font-size="{size}">Merged PRs / week</text>'
        for tick in range(0, ceiling+1, ceiling//3):
            content += f'<path d="M{left} {y(tick)} H{width-right}" stroke="{border}" stroke-width="1"/>'
            content += f'<text x="{left-8}" y="{y(tick)+4}" text-anchor="end" fill="{muted}" font-size="{size}">{tick}</text>'
        for i,row in enumerate(ROWS):
            content += f'<rect x="{x(i)-step*.29:.2f}" y="{y(row["merged"]):.2f}" width="{step*.58:.2f}" height="{y(0)-y(row["merged"]):.2f}" rx="2" fill="{green if i==11 else bar}"><title>{row["start"]} to {row["end"]}: {row["merged"]} merged PRs</title></rect>'
        points = [(x(i), y(sum(r['merged'] for r in ROWS[i-3:i+1])/4)) for i in range(3,12)]
        path = ' '.join(f'{"M" if i==0 else "L"}{a:.2f},{b:.2f}' for i,(a,b) in enumerate(points))
        content += f'<path d="{path}" fill="none" stroke="{green}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
        content += f'<text x="{x(11):.2f}" y="{y(ROWS[-1]["merged"])-10:.2f}" text-anchor="middle" fill="{fg}" font-size="{size+2}" font-weight="600">{ROWS[-1]["merged"]}</text>'
        for i in ([0,5,11] if compact else [0,3,6,9,11]):
            label = datetime.date.fromisoformat(ROWS[i]['start']).strftime('%b %-d')
            content += f'<text x="{x(i):.2f}" y="{height-bottom+25}" text-anchor="middle" fill="{muted}" font-size="{size}">{label}</text>'
        content += f'<text x="{width-right}" y="{height-bottom+45}" text-anchor="end" fill="{muted}" font-size="{size}">Week starting</text>'
        content += f'<rect x="{left}" y="{height-17}" width="9" height="9" fill="{bar}"/><text x="{left+16}" y="{height-8}" fill="{muted}" font-size="{size}">Merged PRs</text>'
        lx = 180 if compact else 300
        content += f'<path d="M{lx} {height-12} h20" stroke="{green}" stroke-width="2.5"/><text x="{lx+27}" y="{height-8}" fill="{muted}" font-size="{size}">4-week average</text>'
        suffix = '-compact' if compact else ''
        (ASSETS / f'momentum-{theme}{suffix}.svg').write_text(wrap(width,height,content,summary))

def date_label(value):
    return datetime.date.fromisoformat(value).strftime('%b %-d, %Y')

def markdown(value):
    value = escape(value)
    for char in '\\`*_{}[]()#+!|':
        value = value.replace(char, '\\' + char)
    return value.replace('\n', ' ')

def link(item):
    url = item['url'].replace(' ', '%20').replace('(', '%28').replace(')', '%29')
    return '[' + markdown(item['label']) + '](<' + escape(url) + '>)'

average = (sum(r['merged'] for r in ROWS[-4:]) + 2) // 4
fields = {
    'description': markdown(CONTENT['description']),
    'links': ' &nbsp; · &nbsp; '.join(link(item) for item in CONTENT['links']),
    'range': date_label(ROWS[0]['start']) + ' – ' + date_label(ROWS[-1]['end']),
    'chart_alt': 'Weekly merged PRs: ' + ', '.join(str(r['merged']) for r in ROWS) + f'. The four-week rolling average ends at {average}.',
    'stats': f"| **{sum(r['merged'] for r in ROWS):,}** | **{ROWS[-1]['merged']:,}** | **{average:,}** |",
    'as_of': date_label(DATA['asOf']),
    'highlights': '\n\n'.join('### ' + markdown(h['title']) + '\n\n' + markdown(h['description']) + '\n\n<sub>Merged ' + date_label(h['mergedOn']) + '</sub>' for h in CONTENT['highlights']),
    'footer': markdown(CONTENT['footer']) + ' ' + link(CONTENT['footerLink']) + '.',
}
template = (ROOT / 'profile/README.template.md').read_text()
(ROOT / 'profile/README.md').write_text(Template(template).substitute(fields))
print('Rendered README and four chart images from JSON.')
