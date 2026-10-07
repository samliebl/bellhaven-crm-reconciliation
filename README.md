# Bellhaven CRM reconciliation

Scrape the complete Bellhaven website, compare it with all CRM accounts, and review exact changes before applying them. Python 3.10+; no third-party packages.

**The candidate CRM was corrected on October 7, 2026.** All 35 website facilities have one current Active account under Bellhaven. There were 25 approved proposals, one deliberately rejected billing-address replacement, six account creates, and 25 updates. Complete reruns produced zero new proposals and zero writes. The approach, AI use, and next steps are summarized in [WRITEUP.md](WRITEUP.md). Recorded decisions and 105 passing end-state checks are in [submission/decisions.csv](submission/decisions.csv) and [submission/verification.json](submission/verification.json).

## Get started

```sh
git clone https://github.com/samliebl/bellhaven-crm-reconciliation.git
cd bellhaven-crm-reconciliation
cp .env.example .env
# Set CRM_TOKEN in .env, then:
python3 -m unittest discover -s tests -v
python3 -m bellhaven run
python3 -m bellhaven serve
```

Open http://127.0.0.1:8877. Inspect a proposal, enter your reviewer name and optional rationale, then approve or reject. **Approve and apply makes real changes to the candidate CRM.** Running the pipeline never mutates it. Preserve `data/` across runs; a fresh clone does not contain prior operational decisions.

Optional VS Code tasks, test discovery, Python extension recommendations, and debugger configurations are included in `.vscode/`.

## Commands

| Command | Effect |
|---|---|
| `python3 -m bellhaven scrape` | Collect website locations and full source HTML |
| `python3 -m bellhaven run` | Complete website/CRM read and proposal generation; no CRM writes |
| `python3 -m bellhaven run --cached-website` | Reconcile using the saved complete website snapshot |
| `python3 -m bellhaven serve` | Start the local review app on port 8877 |
| `python3 -m bellhaven serve --port 8878` | Use another local port |
| `python3 -m bellhaven export` | Save evidence, decisions, and operation journals to data/audit.json |
| `python3 -m bellhaven verify` | Read live CRM and verify it against approvals and the original snapshot |

## Scraping and evidence

The crawl starts from the homepage, community directory, and About page. It follows same-host community detail and pagination links. The directory declares 34 facilities, while the homepage advertises 35 and links to Findlay separately; both sources are necessary. Every detail page must parse successfully. Directory counts and advertised totals must reconcile before a new location snapshot is published. A partial crawl cannot generate removals.

Each facility records name, street, city, state, ZIP, care offerings, source URL, and supporting public phone/administrator information when available. Supporting contact details are not synchronized to CRM contacts. Full HTML is saved with the crawl timestamp. [submission/locations.csv](submission/locations.csv) contains all 35 locations and their current CRM account ids.

## Matching and outcomes

The pipeline reads **all CRM pages**, including previous-brand names and facilities under other parents. The corporate parent is identified uniquely; use `CRM_PARENT_ID` if ambiguous.

Address normalization handles street suffixes and compass directions without dropping house numbers. Exact address/locality matches score 100; a differing ZIP scores 94; an exact name and city/state with a different address scores 88 and requires careful address review. Lower-confidence or conflicting identities become investigation items with no executable changes. Scores are rules, not calibrated probabilities. Multiple website facilities at one address are held for investigation.

| Finding | Proposed outcome |
|---|---|
| Confident current match | No mutation |
| Name, care, or justified address discrepancy | Small PATCH with differing fields |
| Wrong/missing parent, no protected AR | Re-parent the existing account after checking billing |
| Wrong parent, revenue history and positive AR | Create a successor and link the old account through CHOW |
| Missing account | Create an Active account under Bellhaven |
| Confirmed duplicate | Keep the loser, mark Inactive, set duplicate_of_account, explain in note |
| Absent from the complete website | Mark Needs Review with a note; retain parent and finances |
| Ambiguous identity or unknown billing | Investigation; approval disabled until a concrete plan exists |

Duplicate survivor ranking prioritizes existing CHOW targets and billing continuity, then the correct parent, matching website phone, current name, active status, and deterministic id. Reviewers inspect the candidate group; a score alone never approves a change.

Website terminology maps to `care_type`: Short-Term Rehabilitation & Nursing → Skilled Nursing; Memory Support → Memory Care. Multiple offerings are preserved using semicolons. Equivalent address abbreviations are left alone.

## Mandatory billing protection

Before a parent change, inspect `lifetime_revenue` and `outstanding_ar`. If both are positive, create a correct-parent successor and set **only** `chow_current_account` on the old record. Do not copy financial history into the new account or change the old parent, name, status, billing values, or note. The API updates its server timestamp. If either financial value is zero, move the existing account directly. Missing/invalid values block the move.

## Approval and repeat-run safety

- SQLite stores proposal fingerprints, evidence, decisions, reviewer/rationale, and each operation's outcome. Fingerprints represent the proposed result and target, excluding timestamps and before-snapshots. Identical decided proposals are not added again. Pending evidence refreshes in place; obsolete pending plans become superseded and cannot be approved.
- Approval is committed before writes. Existing accounts are re-read to check reviewed fields and billing facts. Every write is read back and compared with its approved payload.
- File locks serialize runs and execution on this host. A conditional decision update prevents two clicks from deciding the same proposal twice.
- A create carries an operation marker in its approved note. Its journal entry is committed before transmission. After an interrupted response, recovery finds the marker and resumes without another create. If the outcome cannot be established, the system blocks instead of blindly retrying POST.
- PATCH recovery recognizes already-applied values. Partially completed approved plans are held for recovery; daily runs do not replace them with new proposals. The app offers a safe resume control.
- Rejected proposals remain rejected. At Ashtabula, the website proves a physical address, not that the CRM mailing address is wrong.

The API documents no conditional-update or server idempotency support. These guards are designed for one persistent review host; another independent CRM writer can still race after a read. Failed or conflicting writes require review.

## Daily operation and state

[schedule.cron](schedule.cron) is an example 06:00 America/New_York schedule. It is not installed or live. Replace checkout/interpreter paths and configure the host timezone if its cron does not support CRON_TZ. Keep one persistent checkout and `data/`; the scheduled command only generates proposals.

Back up `data/`, including review.sqlite3 and journal files, while the service is stopped, or use SQLite's backup API for a consistent running backup. Fresh Git clones contain source and reports, not ignored operational state. Restore that state when moving the runner to another machine.

`.env`, tokens, raw CRM snapshots, source-page archives, the live database, and local screenshots are excluded from Git. The server binds to 127.0.0.1, validates Host/Origin, and requires a session-specific form token for decisions.

## API observations

The live schema uses `account_id`, `billing_street`, `billing_city`, `billing_state`, `billing_zip`, and `care_type`. Internally `id` aliases `account_id`; the alias is never sent as a write field. The client paginates the `data/page/page_size/total` response. Authentication requires the candidate Bearer token despite being absent from Swagger. The specification also omits account models and POST/PATCH bodies; field mapping was established from authenticated records and verified writes.

## Tests and limits

The 29 offline tests cover address normalization, same-name facilities in other states, homepage-only locations, incomplete-crawl refusal, malformed CRM pagination, billing thresholds, stale data, duplicate selection, approval gating, persistent rejection, applied reruns, and lost-response recovery. Live verification checks approved fields, financial and CHOW preservation, original-record retention, absence of unapproved edits, and one current account per website facility.

Website absence does not prove closure or current ownership. Alliance, Coldwater, and Sandusky remain Needs Review. The scraper targets this site's HTML and fails loudly if it changes; it does not guess missing data or approve writes automatically.
