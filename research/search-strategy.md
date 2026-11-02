# Search strategy

[Tracker](../tracker.md) · [Search performance](search-performance.md) · [Search log](search-log.csv)

Claude reads this before every search session. Start with a guess, then let the numbers in `search-log.csv` and `search-performance.md` (run `python research/search_report.py`) tell you what to keep.

## Role families

Every tracker row gets one of these in its `Family` column, so the dashboard can show which kinds of roles get replies and interviews.

- Family 1:
- Family 2:
- Family 3:

## Fixed queries (run every session)

| Site | Query | Why |
|---|---|---|
| LinkedIn | | |
| VDAB | (Dutch titles work best) | |
| Jobat | (as a URL slug, e.g. `sales-engineer`) | |

## Rotating queries

Always pair a **role term with a sector term** ("sales engineer pharma", not "sales engineer"). Rotate the sector terms between sessions; check the last session's lines in `search-log.csv` to avoid repeats.

## Review notes

Dated notes on what worked and what was dropped, newest first.
