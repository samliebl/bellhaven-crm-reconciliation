# Bellhaven project instructions

- Read README.md and ASSIGNMENT.md before making changes.
- The original coordinating chat owns the end-to-end submission. A session
  assigned a review role must remain read-only and return actionable findings.
- Daily pipeline runs collect evidence and generate proposals; they must never
  approve or mutate CRM records.
- Execute CRM mutations only through recorded review-app approvals. Preserve
  the full billing SOP and check current CRM facts again before execution.
- Never commit `.env`, tokens, raw CRM snapshots, or the live SQLite database.
- Preserve decisions and operation journals across runs. Do not reset data to
  make tests or screenshots look clean.
- Run `python3 -m unittest discover -s tests -v` for substantive code changes.
  Run `python3 -m bellhaven verify` for read-only live end-state verification
  when the candidate token and local decision database are available.
