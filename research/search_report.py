"""Search performance report: research/search-log.csv + tracker.csv -> research/search-performance.md.

Run from the project folder: python research/search_report.py
Prints a one-line summary at the end.
"""
import csv, re, collections, datetime as dt

LOG, TRACKER, OUT = 'research/search-log.csv', 'tracker.csv', 'research/search-performance.md'
# Each period is one search setup, so the numbers compare setups rather than calendar weeks.
# Add a new line (and close the previous one) whenever you change how you search.
PERIODS = [
    ('First setup', '2000-01-01', '9999-12-31'),
]
SOURCES = ['LinkedIn', 'VDAB', 'Jobat', 'StepStone']
REP = None  # optional: re.compile(r'<terms>', re.I) to count one family of searches separately


def num(x):
    m = re.search(r'\d+', x or '')
    return int(m.group()) if m else 0


def source(s):
    return next((k for k in SOURCES + ['Indeed'] if s.startswith(k)), s.split(' ')[0])


log = [r for r in csv.DictReader(open(LOG, encoding='utf-8-sig')) if r.get('Date')]
rows = list(csv.DictReader(open(TRACKER, encoding='utf-8-sig')))
today = dt.date.today().isoformat()
current = next(p for p in reversed(PERIODS) if p[1] <= today)


def in_period(d, p):
    return p[1] <= d <= p[2]


def source_table(p):
    agg = collections.defaultdict(lambda: {'runs': set(), 'q': 0, 'res': 0, 'six': 0, 'zero': 0})
    for r in log:
        if in_period(r['Date'], p):
            a = agg[source(r['Source'])]
            a['runs'].add(r['Date']); a['q'] += 1; a['res'] += num(r['Results'])
            a['six'] += num(r['Logged 6+']); a['zero'] += num(r['Results']) == 0
    out = ['| Site | Runs | Searches | Results | Leads 6+ | Leads per 10 searches | Empty searches |', '|---|---|---|---|---|---|---|']
    for s, a in sorted(agg.items(), key=lambda x: -x[1]['six']):
        rate = f"{10 * a['six'] / a['q']:.1f}" if a['q'] else '–'
        out.append(f"| {s} | {len(a['runs'])} | {a['q']} | {a['res']} | **{a['six']}** | {rate} | {a['zero']} |")
    tot_q = sum(a['q'] for a in agg.values()); tot_six = sum(a['six'] for a in agg.values())
    return out, agg, tot_q, tot_six


def query_stats(p):
    q = collections.defaultdict(lambda: [0, 0])
    for r in log:
        if in_period(r['Date'], p):
            k = (source(r['Source']), r['Query'].strip().lower())
            q[k][0] += 1; q[k][1] += num(r['Logged 6+'])
    return q


def leads(p):
    """Tracker rows (with a Found via) whose earliest dated note falls in the period."""
    out = []
    for x in rows:
        if not x['#'].isdigit() or not x.get('Found via'):
            continue
        try:
            note = open(x['Note'], encoding='utf-8').read()
        except OSError:
            continue
        dates = re.findall(r'\*\*(20\d\d-\d\d-\d\d)', note)
        if dates and in_period(min(dates), p):
            out.append(x)
    return out


md = ['# Search performance', '',
      '[Tracker](../tracker.md) · [Search strategy](search-strategy.md) · [Search log](search-log.csv)', '',
      f'Generated {dt.datetime.now():%Y-%m-%d %H:%M} by `research/search_report.py` after each search session. '
      'Each block is one search setup, so the numbers compare setups. "Leads 6+" counts rows logged at 6/10 or higher.', '']

summary = ''
for p in reversed(PERIODS):
    if p[1] > today:
        continue
    table, agg, tq, tsix = source_table(p)
    end = min(p[2], today)
    md += [f'## {p[0]}: {p[1]} to {end}', '']
    if not tq:
        md += ['No searches logged yet in this setup.', '']
        if p is current:
            summary = 'New search mix: no runs logged yet.'
        continue
    md += table + ['', f'**Total: {tsix} leads of 6+ from {tq} searches.**', '']

    q = query_stats(p)
    best = sorted(((k, v) for k, v in q.items() if v[1]), key=lambda x: (-x[1][1], x[1][0]))[:10]
    if best:
        md += ['**Searches that found leads**', '', '| Site | Search | Times run | Leads 6+ |', '|---|---|---|---|']
        md += [f'| {k[0]} | {k[1]} | {v[0]} | {v[1]} |' for k, v in best] + ['']
    dead = sorted(((k, v) for k, v in q.items() if not v[1] and v[0] >= 3), key=lambda x: -x[1][0])[:10]
    if dead:
        md += ['**Run 3+ times without a lead** (candidates to swap out)', '', '| Site | Search | Times run |', '|---|---|---|']
        md += [f'| {k[0]} | {k[1]} | {v[0]} |' for k, v in dead] + ['']
    rep = [(k, v) for k, v in q.items() if REP and REP.search(k[1])]
    if rep:
        md += [f"**Searches matching REP:** {sum(v[0] for _, v in rep)} run, {sum(v[1] for _, v in rep)} leads of 6+.", '']

    ls = leads(p)
    if ls:
        sc = [num(x['Score']) for x in ls]
        hi = sum(s >= 8 for s in sc)
        applied = [x for x in ls if x.get('Stage')]
        md += [f"**Leads logged:** {len(ls)} rows, average score {sum(sc) / len(sc):.1f}, {hi} at 8+. "
               f"Applied to so far: {len(applied)}" + (' (' + ', '.join(f"#{x['#']} {x['Stage']}" for x in applied) + ')' if applied else '') + '.', '']
        by = collections.Counter(source(x['Found via']) for x in ls)
        md += ['Found via: ' + ', '.join(f'{k} {v}' for k, v in by.most_common()) + '.', '']

    if p is current:
        li = agg.get('LinkedIn', {'six': 0, 'q': 0}); runs = len(set().union(*(a['runs'] for a in agg.values())))
        summary = f"Search mix since {p[1]}: {tsix} leads 6+ from {tq} searches over {runs} run(s); LinkedIn {li['six']}/{li['q']}."

open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(md) + '\n---\n[Tracker](../tracker.md) - [Shortlist](../SHORTLIST.md)\n')
print(summary)
