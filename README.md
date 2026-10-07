# Bellhaven CRM reconciliation

Python 3.10+; no third-party dependencies. Work in progress: public website
scraping and proposal generation are implemented; the approval app and verified
CRM execution are being completed in this repository.

The scraper follows all community directory pages and community links on the
homepage. The initial crawl found 35 facilities, including the Findlay facility
linked from the homepage but omitted from the 34-item directory. It saves full
HTML evidence and normalized location fields locally.

Create `.env` from `.env.example` and set the candidate `CRM_TOKEN`. Credentials,
CRM snapshots, and the review database are ignored by Git. Decisions must remain
in the persistent local database between daily runs.

All CRM mutations must be triggered by a recorded approval. Billing-bearing
accounts with outstanding AR are preserved under their old parent: create the
correct-parent successor, then set only `chow_current_account` on the old account.
Duplicates are retained as Inactive with `duplicate_of_account`; absent website
records are marked Needs Review rather than assuming closure or ownership.
