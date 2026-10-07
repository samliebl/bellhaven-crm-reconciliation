# Independent assessment audit

Sam authorized the coordinating chat to assign other project chats review work.
The chat titled **Summarize API documentation** is the coordinator and owns
implementation, review decisions, and CRM changes. Other chats remain read-only.

Work in this repository, whose private remote is
https://github.com/samliebl/bellhaven-crm-reconciliation. Read AGENTS.md,
ASSIGNMENT.md, README.md, and SUBMISSION.md. Record the commit and any local
changes inspected. Do not edit files, approve/reject proposals, mutate CRM,
reset state, or start additional agents. Offline tests and read-only inspection
are allowed. Never print credentials or commit operational state.

Audit for material job-assessment traps:

- Complete website coverage: directory pagination and homepage-only Findlay.
- Same-name facilities in other states, ambiguous addresses, and care mappings.
- Duplicate survivors, financial records, and protected CHOW predecessor accounts.
- Website physical address versus CRM billing mailing address.
- Missing and absent facilities: distinguish proven facts from ownership guesses.
- Exact billing SOP: positive lifetime revenue AND positive outstanding AR
  requires a new correct-parent account and a pointer on the otherwise preserved
  old account. Either zero permits direct re-parenting.
- No CRM write without recorded approval; stale data and concurrent clicks.
- Persistent approved/rejected decisions and safe daily reruns.
- Partial approved plans, lost responses, and uncertain creates: no duplicate POST.
- A daily schedule that generates proposals without approving them.
- Actual corrected CRM, end-state evidence, secret exclusion, and reproducible
  setup instructions. Verify claims independently rather than trusting the report.

Run `python3 -m unittest discover -s tests -v` if useful. The existing local
decision database and `.env` also allow `python3 -m bellhaven verify`, which is
read-only against CRM. Do not invoke writes or use an API mutation directly.

Return prioritized findings with severity, file/line, concrete reproduction,
impact, and suggested fix. Separate proven defects from uncertain business
assumptions. Show findings in your final response for Sam and the coordinator
to read. Sending messages to another chat requires Sam's direct authorization.
