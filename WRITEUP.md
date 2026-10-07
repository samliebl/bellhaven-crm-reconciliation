# Approach, AI use, and next steps

The core problem was that Bellhaven’s website and CRM disagreed: facilities had outdated names, incorrect parents, duplicate records, or missing accounts. We needed to correct the CRM while protecting billing history and requiring approval for every change.

We scoped the solution into collection, matching, review, and execution. The scraper collected 35 facilities across the directory and homepage, including Findlay, which the directory omitted. Matching compared the entire CRM using normalized addresses, locality, names, care offerings, and supporting phone information. Similar names alone were insufficient. The review app showed evidence and exact proposed changes before execution.

Billing protection shaped ownership corrections. When both lifetime revenue and outstanding AR were positive, we created a successor under Bellhaven and preserved the old account, adding only its CHOW pointer. Otherwise, we could re-parent directly. Duplicate copies were retained as Inactive with survivor links; absent facilities became Needs Review. We rejected one address replacement because a website’s physical address did not prove the CRM’s billing PO box was wrong.

We defined completion as a corrected, verified CRM plus safe reruns. Twenty-five proposals were applied, all 35 facilities had current Bellhaven accounts, and original financial values remained unchanged. Validation included 29 automated tests and 105 live checks. Reruns produced zero new proposals or writes; the supplied daily schedule generates proposals only.

I used Codex for implementation, testing, and proposal review, including approvals on my behalf, which the audit records disclose. An independent AI audit identified edge cases we fixed. Next, I would resolve remaining business questions, deploy daily scheduling with backups and alerts, and add stronger reviewer access and API concurrency safeguards.
