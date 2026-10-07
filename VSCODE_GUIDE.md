# VS Code guide for this project

Codex is helping develop this Python project. VS Code provides the files,
terminal, Git changes, tests, and debugger in one workspace. You can keep using
the separate Codex app with the same folder, or use the official Codex extension
inside VS Code.

## First setup

1. Choose **File → Open Folder** and open the `bellhaven-crm-reconciliation`
   local clone, the folder containing README.md and `.git`.
2. Open Extensions (`⌘⇧X`). The repository recommends **Python** and **Python
   Debugger** from Microsoft, and **Codex** from OpenAI (`openai.chatgpt`). Install
   the ones you want. The recommendation file does not install them itself.
3. Open the Command Palette (`⌘⇧P`) and choose **Python: Select Interpreter**.
   Select an installed Python 3.10 or newer. This machine already has Python;
   this project needs no third-party packages or OpenAI API key to run.
4. Keep the candidate CRM token in `.env`. It is already configured locally and
   ignored by Git. After a fresh clone elsewhere, copy `.env.example` to `.env`
   and supply your token.

## Your first run

The app may already be running at http://127.0.0.1:8877. If that page works, use
it directly. Otherwise open the Command Palette, choose **Tasks: Run Task**, and
select **Bellhaven: Start review app**. The terminal stays open while it runs;
Ctrl+C stops the process.

Other tasks:

| Task | What it does |
|---|---|
| Bellhaven: Run tests | Exercises matching, approval gating, billing preservation, and recovery without live CRM writes |
| Bellhaven: Collect website only | Saves the complete location list and source pages |
| Bellhaven: Generate proposals (no CRM writes) | Collects the website, reads the CRM, and updates the local review queue |
| Bellhaven: Start review app | Opens the local approval server; use its displayed URL in a browser |
| Bellhaven: Export audit | Saves decisions, evidence, and operation journals to data/audit.json |

Approving in the review app really changes the CRM. Generating proposals and
running tests do not. The current submission has already been reviewed and
applied; rerunning the pipeline preserves those decisions.

## The parts of VS Code you will use most

- **Explorer:** file sidebar. Start with README.md, then ASSIGNMENT.md.
- **Command Palette (`⌘⇧P`):** search for any command rather than memorizing menus.
- **Quick Open (`⌘P`):** find a file by part of its name, much like Sublime.
- **Search (`⌘⇧F`):** find text across the project.
- **Terminal (View → Terminal):** run commands and read results without leaving
  the editor. The project commands in README.md work here.
- **Source Control (`⌃⇧G`):** changed files and line-by-line comparisons. Click a
  file, inspect the diff, stage intended files, commit with a meaningful message,
  and push. Local commits and GitHub pushes are separate steps.
- **Testing:** the Python extension discovers the unittest suite. Run individual
  tests or the full suite from the beaker view.
- **Run and Debug (`⌘⇧D`):** select a Bellhaven configuration and press F5. A
  breakpoint is a click beside a line number; it pauses the program there so you
  can inspect values. The review-app debugger uses port 8878, allowing it to
  coexist with the already-running review server on 8877.

## A productive AI workflow

1. Ask for a focused result and relevant constraints: “Improve the matching
   evidence shown to reviewers. Preserve approval gating and the billing SOP.”
2. Ask the assistant to explain its intended change if you want to learn before
   it edits. Useful requests include “Explain this function in plain language,”
   “Show the path from an approval click to the CRM request,” and “Reproduce this
   bug before fixing it.”
3. Inspect the proposed code changes in Source Control. Ask about any line you
   do not understand.
4. Run the relevant tests and use the app to check the actual behavior.
5. Commit a coherent, verified change. A commit gives you a named checkpoint
   you can compare against later.

The project is Python and HTTP; “AI project” here describes how we develop it.
There is no model call required by the scraper or reviewer app.

## A map of the code

| File | Responsibility |
|---|---|
| bellhaven/core.py | Website parser, API client, persistent database, and locks |
| bellhaven/matching.py | Matching, classifications, and exact proposed operations |
| bellhaven/execution.py | Approval gate, billing checks, write journal, and read-back verification |
| bellhaven/app.py | Review pages and approval/rejection forms |
| bellhaven/verification.py | Independent read-only validation of the CRM end state |
| bellhaven/__main__.py | Commands that run the system |
| tests/test_pipeline.py | Offline tests for correctness and failure recovery |
| data/ | Local evidence, credentials-free snapshots, and persistent decisions; ignored by Git |

## Common first-time issues

- **Address already in use:** a review server is already running. Open its URL,
  stop the one you started, or use `python3 -m bellhaven serve --port 8878`.
- **No Python interpreter:** use Python: Select Interpreter. Tasks invoke
  `python3` from your terminal PATH; the debugger uses your selected interpreter.
- **CRM_TOKEN missing / HTTP 401:** check your local `.env` and candidate token.
- **A stale or failed approval:** open the item and inspect the error. Resume
  approved work using the recovery button; never delete the database or journal
  to retry a create.
- **Source Control shows secrets:** `.env` should be ignored. Do not force-add it.
- **Daily decisions disappear:** preserve and back up the entire local `data/`
  directory. A fresh clone has source code, not this ignored operational state.

## Official references

- [Python in VS Code](https://code.visualstudio.com/docs/languages/python/)
- [VS Code tasks](https://code.visualstudio.com/docs/debugtest/tasks)
- [Python debugging](https://code.visualstudio.com/docs/python/debugging)
- [Codex IDE extension](https://learn.chatgpt.com/docs/codex/ide)
