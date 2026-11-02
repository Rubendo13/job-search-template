# Job search with Claude Code

A ready-made workspace for running a job search in Belgium with [Claude Code](https://claude.com/claude-code): a tracker that opens in Excel, a ranked shortlist, a local dashboard with Applied / Not interested buttons, search logging, and house rules for CVs, cover letters and interview prep.

Everything personal is left blank for you to fill in.

## What you need

- A Claude subscription (Pro or Max) and **Claude Code** installed: https://code.claude.com/docs/en/setup
- **Python 3** (Windows: from python.org, tick "Add python.exe to PATH" during install)
- **Node.js** (LTS, from nodejs.org): for the Playwright browser that reads VDAB, Jobat and StepStone
- **Google Chrome**: for the browser and for turning CVs into PDFs
- **Git**

## Setup

1. Make your own **private** copy. On GitHub use **"Use this template" → private repo**, or clone this repo and push it to a new private one. It will contain your CV and applications: keep it private.
2. Clone your copy and open a terminal in the folder:
   ```
   git clone https://github.com/<you>/<your-repo>.git
   cd <your-repo>
   claude
   ```
3. Approve the **playwright** MCP server when Claude Code asks.
   - *Windows only:* if the browser won't start, change `"command": "npx"` in `.mcp.json` to `"command": "cmd"` and put `"/c", "npx"` at the front of `args`.
4. Optional but recommended: in claude.ai → Settings → Connectors, connect **Gmail** and **Google Calendar**. Claude then reads recruiter mail, keeps the tracker in sync and adds interviews to your calendar. It can only make Gmail **drafts**: sending is blocked in `.claude/settings.json`.
5. Say: **"Let's set up my job search."** Claude interviews you to fill in `profile/profile.md`, your scoring rubric, your role families and your own rules (see the top of `CLAUDE.md`). Then put your CV into `profile/CV_base.html` (or give Claude your current CV PDF and ask it to fill the template).

## Daily use

- **"Search for new leads"**: saved LinkedIn/Jobat jobs first, then keyword searches. Each new lead is checked, scored and logged.
- **"Make a CV and letter for #12"**: a tailored CV and letter in `applications/<company>/`, rendered to PDF.
- **"Prep me for the interview with X on Thursday"**
- **"I applied to #12"** / **"X replied, interview on the 14th"**: Claude updates the tracker (and the calendar).
- **Dashboard:** `python dashboard_server.py` (Mac: `python3`), then open http://localhost:8090.
- **Excel:** `tracker.csv` is the real data. After editing it by hand, run `python tracker.py build .`.

## Logging in to job sites

The Playwright browser keeps its own profile. The first time Claude opens LinkedIn's saved jobs or Jobat favourites, a Chrome window appears: log in there yourself, then tell Claude to carry on.

## Files

See the "Project structure" section in `CLAUDE.md`. Short version: `tracker.csv` is the data, `leads/` holds the notes per lead, and `tracker.md` / `SHORTLIST.md` / `control-panel.html` are rebuilt from them by `tracker.py`.
