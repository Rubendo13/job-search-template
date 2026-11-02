#!/usr/bin/env python3
"""Live job-search dashboard on your own computer.

    python dashboard_server.py            # then open http://localhost:8090

Serves control-panel.html (kept current by `tracker.py build`) and makes the
Applied / Not interested buttons work: a click updates tracker.csv and the lead note,
then rebuilds, using the same mapping as the "Dashboard buttons" rule in CLAUDE.md.
No Claude needed. Only reachable from this computer (localhost).
"""
import datetime, http.server, json, os, re, threading

import tracker

HERE = os.path.dirname(os.path.abspath(__file__))
HOST, PORT = os.environ.get('DASH_HOST', '127.0.0.1'), int(os.environ.get('DASH_PORT', '8090'))
LOCK = threading.Lock()  # one tracker write at a time

LOCAL_JS = '''
<script>
/* Local mode (dashboard_server.py): the buttons write straight to tracker.csv. */
(() => {
  if (window.claude && window.claude.use) return;  // inside the claude.ai artifact the original script handles it
  document.querySelectorAll('.lead[data-row] .pick').forEach(p => { p.hidden = false; });
  document.addEventListener('click', async ev => {
    const b = ev.target.closest('.pick button[data-act]');
    if (!b) return;
    const card = b.closest('[data-row]'), row = card.dataset.row;
    const co = card.querySelector('.co').textContent.split(' · ')[0].trim();
    const what = b.dataset.act === 'applied' ? 'APPLIED' : 'NOT INTERESTED (withdrawn)';
    if (!confirm(`Mark #${row} ${co} as ${what}?\\nThis writes to the tracker straight away.`)) return;
    card.style.opacity = .4;
    const r = await fetch('/decision', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                        body: JSON.stringify({row, action: b.dataset.act})});
    if (r.ok) location.reload();
    else { card.style.opacity = 1; alert('Not saved: ' + await r.text()); }
  });
})();
</script>
'''


def page():
    s = open(os.path.join(HERE, 'control-panel.html'), encoding='utf-8').read()
    return s.replace('</body>', LOCAL_JS + '</body>', 1) if '</body>' in s else s + LOCAL_JS


def prepend_note(path, para):
    text = open(path, encoding='utf-8').read()
    head, sep, body = text.partition('\n## Notes\n')
    text = head + sep + '\n' + para + '\n' + body if sep else text.rstrip('\n') + '\n\n## Notes\n\n' + para + '\n'
    open(path, 'w', encoding='utf-8', newline='\n').write(text)


def decide(row, action):
    today = datetime.date.today().isoformat()
    rows = tracker.load(HERE)
    r = next((x for x in rows if x['#'] == row), None)
    if r is None:
        return 404, f'row #{row} not in tracker.csv'
    if tracker.status(r) != 'TO APPLY':
        return 409, f"row #{row} is already {r['Status']}"
    if action == 'applied':
        r['Status'], r['Date Applied'] = 'APPLIED', today
        if 'Stage' in r:
            r['Stage'] = 'sent'  # feeds the "How far applications get" funnel
        para = f'✅ **{today}: APPLIED (marked on the dashboard).** Route and CV not recorded yet; Claude asks next session if it matters for follow-up.'
    else:
        r['Status'], r['Section'] = f'WITHDRAWN (not interested, {today})', 'archive'
        para = f'🚫 **{today}: NOT INTERESTED (marked on the dashboard).** Withdrawn and moved to the archive.'
    prepend_note(os.path.join(HERE, r['Note']), para)
    tracker.save(HERE, rows)
    tracker.build(HERE)
    return 200, 'ok'


class Handler(http.server.BaseHTTPRequestHandler):
    def send(self, code, body, ctype='text/plain; charset=utf-8'):
        data = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.split('?')[0] in ('/', '/index.html'):
            self.send(200, page(), 'text/html; charset=utf-8')
        else:
            self.send(404, 'not found')

    def do_POST(self):
        # JSON-only: a cross-site page can't send this without a CORS preflight, which we never answer.
        if self.path != '/decision' or not self.headers.get('Content-Type', '').startswith('application/json'):
            return self.send(400, 'bad request')
        try:
            req = json.loads(self.rfile.read(min(int(self.headers.get('Content-Length', 0)), 1000)))
            row, action = str(req['row']), req['action']
            assert re.fullmatch(r'\d{1,5}', row) and action in ('applied', 'not_interested')
        except Exception:
            return self.send(400, 'bad request')
        with LOCK:
            try:
                code, msg = decide(row, action)
            except Exception as e:
                code, msg = 500, f'error: {e}'
        self.send(code, msg)

    def log_message(self, fmt, *args):
        print(f'{self.address_string()} {fmt % args}', flush=True)


if __name__ == '__main__':
    os.chdir(HERE)
    print(f'job dashboard on http://localhost:{PORT} (Ctrl+C to stop)', flush=True)
    http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
