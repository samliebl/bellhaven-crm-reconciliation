# Matching approach, AI use, and next steps

## My matching approach

I treated this as a reconciliation problem: establish which facility each CRM
record represents, propose justified corrections, and preserve the evidence and
decision history. The website establishes Bellhaven's current public locations;
it does not establish every billing or ownership fact.

The scraper follows the homepage, community directory, and pagination links,
then extracts each facility's name, street, city, state, ZIP, and care offerings
from its detail page. It saves source URLs and HTML as evidence. This mattered
because the directory lists 34 facilities, while Findlay appears separately on
the homepage, bringing the total to 35. Incomplete crawls and missing required
fields stop reconciliation rather than producing misleading removal proposals.

Matching uses the full CRM account list, including facilities under other
parents and older brand names. I normalize ordinary address differences such
as “Street” versus “St” and “Northwest” versus “NW,” while retaining house
numbers. Street, city, state, and ZIP agreement is the strongest identity
signal. A ZIP disagreement or an exact name with conflicting address information
requires closer review. Similar names alone are insufficient: Amberly Manor in
Hudson, Ohio, must not match its namesake in Colorado Springs. The scores are
explainable rules, not probabilities, and never authorize a write.

The resulting classifications distinguish current matches, field corrections,
wrong parents, missing accounts, duplicates, absent facilities, and ambiguous
cases. Duplicate candidates require strong address evidence and compatible
care types. Survivor selection favors billing continuity, then the correct
parent and supporting evidence such as the website phone. Losing copies remain
in CRM, marked Inactive with `duplicate_of_account` and an explanatory note.
Facilities missing from the website become Needs Review; absence alone does
not prove closure or justify changing ownership.

Before any parent change, the system checks both financial fields. Positive
lifetime revenue AND positive outstanding AR requires a new account under
Bellhaven and a `chow_current_account` pointer on the old account. Otherwise,
the existing account can move directly. Marietta and Tiffin followed the
protected branch: their old records retained all other business fields. Missing
or invalid financial values block the move.

The review app shows the evidence and exact proposed changes before approval.
It also supports rejection: Ashtabula's website physical address did not prove
its CRM billing PO box was wrong, so that replacement was rejected. Approved
writes are checked against fresh CRM data and read back afterward. Persistent
decisions and operation journals prevent repeat proposals and blind retries of
uncertain account creates. The example daily schedule generates proposals only.

The completed CRM has one current Active Bellhaven account for each of the 35
website facilities. There were 25 applied proposals, six account creates
(four missing facilities and two CHOW successors), and 25 updates. No original
financial values changed. Complete reruns produced zero new proposals and zero
writes. Validation includes 29 offline tests and 105 live end-state checks.

## How I used AI tools

I used OpenAI Codex as a development and execution assistant. It inspected the
API and website, implemented the scraper, matching rules, local review app,
approval safeguards, tests, and documentation. I supplied the assignment and
constraints and asked for an independent audit focused on assessment traps.
A separate AI reviewer inspected the implementation in read-only mode.

That audit identified concrete edge cases: truncated CRM pagination could look
complete, a CHOW plan containing known duplicates could block itself, and blank
required website content could pass parsing. These were fixed and covered by
regression tests, with additional checks for stale duplicate evidence.

Codex also inspected proposals in the app and approved or rejected them on my
behalf. The decision history explicitly identifies Codex as the reviewer; I am
not claiming that I personally clicked every approval. AI involvement is
documented in the submission.

The running application does not call an AI model. Matching and billing rules
are deterministic and inspectable. AI accelerated implementation and review;
the evidence, recorded approvals, tests, and live CRM checks substantiate the
result. The candidate token is excluded from Git and the submission bundle.

## What I would build next

1. **Resolve the remaining business questions.** Confirm the ownership/status
   of Alliance, Coldwater, and Sandusky, and establish an authoritative billing
   address for Ashtabula. Keep physical and billing addresses separate wherever
   the CRM supports them.
2. **Strengthen daily operations.** Deploy one persistent runner, install the
   supplied schedule, automate consistent state backups, and alert on incomplete
   scrapes, failed approvals, or uncertain API outcomes.
3. **Improve matching evidence.** Add stable external facility identifiers and
   an authoritative alias/ownership history. Make ambiguous comparisons easier
   to review and evaluate matching against a larger labeled dataset.
4. **Support a larger review team.** Add authenticated reviewer roles and clearer
   recovery workflows. For multiple runners or simultaneous CRM editors, seek
   API-supported conditional updates and idempotency keys; the current local
   locks cannot prevent an external writer racing after a read.
