"""Job-search tracker tools. tracker.csv is the source for every table row.

    python tracker.py build .                 # rebuild tracker.md (+ SHORTLIST.md), print counts
    python tracker.py dedupe . <term>...      # LinkedIn ID / company / title in tracker, notes and archive
    python tracker.py stale . [days=30]       # TO APPLY rows not re-verified within <days>
    python tracker.py render <in.html> <out.pdf>   # headless Chrome PDF + one-page check

Each row's long notes live in leads/<id>-<slug>.md (the "Note" column); the table
shows a link plus the first paragraph of that note. Prose in the .md files stays
hand-editable: only tables under <!-- rows:N --> / <!-- shortlist:T --> markers are
regenerated. Shortlist rows = Status TO APPLY with that Tier (T "-" = no tier yet),
sorted by Score.
"""
import csv, datetime, glob, html, os, re, shutil, subprocess, sys, tempfile, zipfile

SUMMARY_LEN = 160
STALE_DAYS = 30   # TO APPLY rows not re-verified this long get auto-archived
TOP_N = 10        # size of the "work from the top" list
SPARES = 10       # hidden extra cards the dashboard promotes when a lead is marked applied / not interested
BACKUPS = 'backups'  # inside the project folder, gitignored
RECRUITER_ROWS = set()  # row numbers of recruiter relationships that must never be auto-archived, e.g. {'12', '40'}
STATUSES = ['TO APPLY', 'APPLIED', 'INTERVIEWING', 'OFFER', 'REJECTED', 'WITHDRAWN', 'ACTION', 'NOT VIABLE']
CHROME_PATHS = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
]
CHROME = os.environ.get('CHROME') or next((c for c in CHROME_PATHS if os.path.exists(c)), None) or shutil.which('chrome') or 'chrome'


def load(folder):
    return list(csv.DictReader(open(os.path.join(folder, 'tracker.csv'), encoding='utf-8-sig', newline='')))


def status(r):
    s = r['Status'].replace('*', '').strip().upper()
    return next((k for k in STATUSES if s.startswith(k)), 'other')


def summary(note_path):
    text = open(note_path, encoding='utf-8').read()
    body = text.split('\n## Notes\n', 1)[-1].strip()
    first = re.sub(r'\s+', ' ', body.split('\n\n', 1)[0]).replace('**', '').replace('`', '')
    if len(first) > SUMMARY_LEN:
        first = first[:SUMMARY_LEN].rsplit(' ', 1)[0] + '…'
    return first


def cell(s):
    return s.replace('|', '\\|')  # a stray pipe used to break whole rows


def score(r):
    m = re.search(r'\d+(?:\.\d+)?', r.get('Score', ''))
    return float(m.group()) if m else -1


def fill(path, marker, render):
    """Replace the table under every <!-- marker:KEY --> line with render(KEY) -> list of lines."""
    lines = open(path, encoding='utf-8-sig').read().split('\n')
    out, i, seen = [], 0, set()
    while i < len(lines):
        m = re.match(rf'<!-- {marker}:(\S+)', lines[i])
        out.append(lines[i]); i += 1
        if m:
            seen.add(m.group(1))
            while i < len(lines) and lines[i].startswith('|'):
                i += 1  # drop the old table
            out += render(m.group(1))
    open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
    return seen


def is_stale(r, days=STALE_DAYS):
    m = re.search(r'\d{4}-\d{2}-\d{2}', r['Last Verified'])
    return not m or datetime.date.fromisoformat(m.group()) < datetime.date.today() - datetime.timedelta(days=days)


def backup(folder):
    """First build of the day zips the tracker data to backups/ (local only)."""
    backups = os.path.join(folder, BACKUPS)
    os.makedirs(backups, exist_ok=True)
    out = os.path.join(backups, f'tracker_{datetime.date.today()}.zip')
    if os.path.exists(out):
        return
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in ['tracker.csv', 'tracker.md', 'tracker-archive.md', 'SHORTLIST.md', 'control-panel.html'] + \
                 glob.glob('leads/*.md', root_dir=folder):
            if os.path.exists(os.path.join(folder, p)):
                z.write(os.path.join(folder, p), p)
    print('backup:', out)


def save(folder, rows):
    fields = [c for c in rows[0] if not c.startswith('_')]
    with open(os.path.join(folder, 'tracker.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(rows)


def top(rows, n=TOP_N):
    """Next best choices: TO APPLY, not blocked on a hard experience bar (Tier X), by score."""
    pick = [r for r in rows if status(r) == 'TO APPLY' and r.get('Tier') not in ('', 'X', None)]
    return sorted(pick, key=lambda r: (score(r), int(r['#'])), reverse=True)[:n]


def build(folder):
    backup(folder)
    rows = load(folder)
    if not rows:
        sys.exit('tracker.csv has no rows yet: add a lead first (keep the header line).')
    ids = [r['#'] for r in rows]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f'duplicate row numbers in tracker.csv: {sorted(dupes)}'
    extra = {'Section', 'Score', 'Tier', 'Why', 'Next', 'Family', 'Stage', 'Found via'}  # dashboard/shortlist-only columns stay out of tracker.md
    cols = [c for c in rows[0] if c not in extra]
    for r in rows:
        p = os.path.join(folder, r['Note'])
        assert os.path.exists(p), f"row {r['#']}: missing note {r['Note']}"
        r['_summary'] = summary(p)

    # Auto-archive, opt-in: only where tracker-archive.md carries a <!-- rows:archive --> marker.
    arch = os.path.join(folder, 'tracker-archive.md')
    if os.path.exists(arch) and '<!-- rows:archive' in open(arch, encoding='utf-8-sig').read():
        moved = [r for r in rows if status(r) == 'TO APPLY' and r['Section'] != 'archive' and is_stale(r)
                 and r['#'] not in RECRUITER_ROWS]
        for r in moved:
            r['Status'] = f'WITHDRAWN (auto-archived {datetime.date.today()}: not re-verified in {STALE_DAYS} days)'
            r['Section'] = 'archive'
        if moved:
            save(folder, rows)
            print(f'auto-archived {len(moved)} stale TO APPLY rows:', ' '.join('#' + r['#'] for r in moved))

    def row_md(r):
        return '| ' + ' | '.join(f"[notes]({r['Note']}) {cell(r['_summary'])}" if c == 'Note' else cell(r[c])
                                 for c in cols) + ' |'

    head = ['| ' + ' | '.join('Notes' if c == 'Note' else c for c in cols) + ' |', '|' + '---|' * len(cols)]
    table = lambda sec: head + [row_md(r) for r in rows if r['Section'] == sec]
    md = os.path.join(folder, 'tracker.md')
    seen = fill(md, 'rows', table)
    if os.path.exists(arch):
        seen |= fill(arch, 'rows', table)
    orphans = {r['Section'] for r in rows} - seen
    assert not orphans, f'CSV sections with no <!-- rows:N --> marker: {orphans}'
    print(f'{md}: {len(rows)} rows in {len(seen)} tables')

    sl = os.path.join(folder, 'SHORTLIST.md')
    if os.path.exists(sl) and 'Tier' in rows[0]:
        def tier_md(t):
            if t == 'top10':
                pick = top(rows)
            else:
                pick = [r for r in rows if status(r) == 'TO APPLY' and (r['Tier'] or '-') == t]
                pick.sort(key=lambda r: (score(r), int(r['#'])), reverse=True)
            return ['| Score | # | Company / role | Territory | Why | Next step |', '|---|---|---|---|---|---|'] + [
                f"| {cell(r['Score'])} | {r['#']} | **{cell(r['Company'].replace('**', ''))}** — {cell(r['Role'])} "
                f"| {cell(r['Region'])} | {cell(r['Why'])} | {cell(r['Next'])} |" for r in pick]
        fill(sl, 'shortlist', tier_md)
        print(f'{sl}: top {TOP_N} + {sum(status(r) == "TO APPLY" for r in rows)} TO APPLY rows ranked')

    counts = {}
    for r in rows:
        counts[status(r)] = counts.get(status(r), 0) + 1
    archived = len(re.findall(r'^\| \d', open(arch, encoding='utf-8').read(), re.M)) if os.path.exists(arch) else 0
    print('counts:', ', '.join(f'{k} {v}' for k, v in sorted(counts.items(), key=lambda kv: -kv[1])),
          f'| archived {archived} | highest # {max(int(i) for i in ids)}')

    panel = os.path.join(folder, 'control-panel.html')
    if os.path.exists(panel) and 'Tier' in rows[0]:
        dashboard(folder, panel, rows, counts, archived)


def html_md(s):
    """Escape, then turn **bold** into <b>."""
    return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html.escape(s.replace('`', '')))


def posting_url(note):
    """The posting a lead note points at: a LinkedIn job ID, a VDAB job number, or a job-site link."""
    li = re.search(r'LinkedIn\D{0,3}(\d{10})', note)
    if li:
        return f'https://be.linkedin.com/jobs/view/{li.group(1)}'
    vd = re.search(r'VDAB\D{0,12}(\d{8})', note)
    if vd:
        return f'https://www.vdab.be/vindeenjob/vacatures/{vd.group(1)}'
    url = re.search(r'https?://(?:www\.|be\.)?(?:vdab|jobat|stepstone|indeed)\.[^\s)>\]"`*]+', note)
    return url.group(0) if url else ''


def dashboard(folder, panel, rows, counts, archived):
    """Regenerate the number strip and the top-10 cards between <!-- gen:X --> ... <!-- /gen:X --> in the panel."""
    c = lambda k: counts.get(k, 0)
    strip = ''.join(f'\n    <div class="cell{cls}" data-k="{label}"><span class="n">{n}</span><span class="l">{label}</span></div>' for cls, n, label in [
        (' hot', c('TO APPLY'), 'To apply'), (' good', c('INTERVIEWING'), 'Interviewing'), (' good', c('APPLIED'), 'Applied'),
        ('', c('REJECTED'), 'Rejected'), ('', c('ACTION'), 'Action'), ('', c('other'), 'Blocked'),
        ('', archived, 'Archived'), ('', max(int(r['#']) for r in rows), 'Seen in total')]) + '\n  '
    cards = []
    for i, r in enumerate(top(rows, TOP_N + SPARES)):  # spares refill the ten when the page marks one
        m = re.match(r'\W*([\d.]+)[*\s]*(?:\(([^)]*)\))?', r['Score'])
        why = r['Why'] if len(r['Why']) <= 320 else r['Why'][:320].rsplit(' ', 1)[0] + '…'
        why = why if why.count('**') % 2 == 0 else why + '**'  # don't leave a bold open after cutting
        nxt = html_md(r['Next']) or 'Apply'
        nxt = nxt if '<b>' in nxt else f'<b>{nxt}</b>'
        n, parts = (m.group(1), m.group(2) or '') if m else ('?', '')
        note = open(os.path.join(folder, r['Note']), encoding='utf-8').read()
        link = posting_url(note)
        link = f'\n          <a class="go" href="{html.escape(link)}" target="_blank" rel="noopener">Open the posting &rarr;</a>' if link else ''
        cards.append(f'''
      <article class="lead{' spare' if i >= TOP_N else ''}" data-row="{r['#']}"{' hidden' if i >= TOP_N else ''}>
        <div class="lead-top">
          <h3>{html_md(r['Role'])}<span class="co">{html_md(r['Company'].replace('**', ''))} &middot; #{r['#']} &middot; {html_md(r['Region'])}</span></h3>
          <div class="score">{n}<span>{html.escape(parts)}</span></div>
        </div>
        <p>{html_md(why)}</p>
        <div class="act">{nxt}{link}</div>
        <div class="pick" hidden><button type="button" data-act="applied">Applied</button><button type="button" class="no" data-act="not_interested">Not interested</button></div>
      </article>''')
    s = open(panel, encoding='utf-8').read()
    blocks = [('strip', strip), ('top10', ''.join(cards) + '\n    ')]
    if '<!-- gen:funnel -->' in s and 'Stage' in rows[0]:
        blocks.append(('funnel', funnel(rows)))
    for key, body in blocks:
        s, k = re.subn(rf'(<!-- gen:{key} -->).*?(<!-- /gen:{key} -->)', lambda m: m.group(1) + body + m.group(2), s, flags=re.S)
        assert k == 1, f'control-panel.html needs exactly one <!-- gen:{key} --> ... <!-- /gen:{key} --> block'
    open(panel, 'w', encoding='utf-8', newline='\n').write(s)
    print(f'{panel}: strip, top {TOP_N} and funnel regenerated (live on the dashboard server).')


# Furthest point an application reached (tracker.csv "Stage"); the outcome itself lives in Status.
STAGES = ['sent', 'reply', 'test', 'interview', 'round 2', 'final', 'offer']
FUNNEL = [('Applied', 'sent'), ('Heard back', 'reply'), ('Interview', 'interview'), ('Later round', 'round 2'), ('Offer', 'offer')]


def funnel(rows):
    """Applications per role family, counted by the furthest stage they reached."""
    apps = [r for r in rows if r.get('Stage', '').strip().lower() in STAGES]
    rank = lambda r: STAGES.index(r['Stage'].strip().lower())
    groups = {}
    for r in apps:
        groups.setdefault(r.get('Family') or 'Unsorted', []).append(r)

    def line(name, rs, total=False):
        n = len(rs)
        cells = []
        for label, st in FUNNEL:
            k = sum(rank(r) >= STAGES.index(st) for r in rs)
            pct = round(100 * k / n) if n else 0
            cells.append(f'<td><span class="fn">{k}</span><span class="fb"><i style="width:{pct}%"></i></span></td>')
        closed = sum(status(r) in ('REJECTED', 'WITHDRAWN') for r in rs)
        rate = round(100 * sum(rank(r) >= STAGES.index('interview') for r in rs) / n) if n else 0
        return (f'\n        <tr{" class=\"tot\"" if total else ""}><th scope="row">{html.escape(name)}</th>{"".join(cells)}'
                f'<td class="cl">{closed}</td><td class="rt">{rate}%</td></tr>')

    order = sorted(groups.items(), key=lambda kv: (-sum(rank(r) >= 3 for r in kv[1]) / len(kv[1]), -len(kv[1])))
    head = ''.join(f'<th scope="col">{l}</th>' for l, _ in FUNNEL)
    return (f'\n    <div class="funnel-wrap"><table class="funnel">\n      <thead><tr><th scope="col">Role family</th>{head}'
            f'<th scope="col">Closed</th><th scope="col">Reached interview</th></tr></thead>\n      <tbody>'
            + line('All applications', apps, total=True) + ''.join(line(k, v) for k, v in order)
            + '\n      </tbody>\n    </table></div>\n    ')


def dedupe(folder, terms):
    rows = load(folder)
    archive = os.path.join(folder, 'tracker-archive.md')
    archive = open(archive, encoding='utf-8').read().split('\n') if os.path.exists(archive) else []
    for term in terms:
        t = term.lower(); hits = []
        for r in rows:
            note = open(os.path.join(folder, r['Note']), encoding='utf-8').read().lower()
            if t in (r['Company'] + ' ' + r['Role']).lower() or t in note:
                hits.append(f"  tracker #{r['#']} [{r['Status'][:30]}] {r['Company'][:40]} — {r['Role'][:50]}")
        for line in archive:
            if line.startswith('|') and t in line.lower():
                c = [x.strip() for x in line.split('|')[1:-1]]
                hits.append(f"  archive #{c[0]} [{c[5][:30] if len(c) > 5 else ''}] {c[1][:40]} — {c[2][:50] if len(c) > 2 else ''}")
        print(f'{term}: ' + (f'{len(hits)} hit(s)\n' + '\n'.join(hits) if hits else 'NEW, not seen before'))


def stale(folder, days=STALE_DAYS):
    for r in load(folder):
        if status(r) == 'TO APPLY' and r['Section'] != 'archive' and is_stale(r, days):
            print(f"#{r['#']:>4} {r['Last Verified'][:12]:<12} {r['Company'][:40]} — {r['Role'][:45]}")


def render(html, pdf):
    if os.path.exists(pdf) and os.path.getmtime(pdf) > os.path.getmtime(html):
        sys.exit(f'STOP: {pdf} is newer than its .html, someone may have annotated it. Ask before overwriting.')
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-pdf-header-footer', f'--user-data-dir={prof}',
                        f'--print-to-pdf={os.path.abspath(pdf)}', 'file://' + os.path.abspath(html)],
                       check=True, capture_output=True)
    pages = len(re.findall(rb'/Type\s*/Page[^s]', open(pdf, 'rb').read()))
    print(f'{pdf}: {pages} page(s)' + ('  <-- MORE THAN ONE PAGE' if pages > 1 else ''))
    # CVs and letters go out in Arial. Chrome silently substitutes another font
    # when Arial is missing, so check what actually got embedded (needs pdffonts / poppler).
    try:
        out = subprocess.run(['pdffonts', pdf], capture_output=True, text=True).stdout.splitlines()[2:]
        fonts = sorted({l.split()[0].split('+')[-1] for l in out if l.strip()})
        bad = [f for f in fonts if not f.startswith('Arial')]
        print(f'fonts: {", ".join(fonts)}' + (f'  <-- NOT ARIAL: {", ".join(bad)} (is Arial installed? fc-match Arial)' if bad else ''))
    except FileNotFoundError:
        print('fonts: not checked (pdffonts missing)')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['build'] and len(a) == 2:
        build(a[1])
    elif a[:1] == ['dedupe'] and len(a) >= 3:
        dedupe(a[1], a[2:])
    elif a[:1] == ['stale'] and len(a) in (2, 3):
        stale(a[1], int(a[2]) if len(a) == 3 else 30)
    elif a[:1] == ['render'] and len(a) == 3:
        render(a[1], a[2])
    else:
        sys.exit(__doc__)
