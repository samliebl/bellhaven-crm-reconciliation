# Bellhaven reconciliation submission

Completed and verified October 7, 2026. The review app was used to inspect and
decide proposals, and approved changes were actually sent to the candidate CRM.

## End state

| Result | Verified value |
|---|---:|
| Website facilities collected | 35 |
| Current Active facility accounts under Bellhaven | 35 |
| CRM accounts before / after | 121 / 127 |
| Approved and verified proposals | 25 |
| Rejected proposals | 1 |
| Superseded draft plans | 1 |
| Pending or failed proposals | 0 |
| Creates / updates | 6 / 25 |
| Original financial values changed | 0 |
| New proposals on each of two complete reruns | 0 |
| CRM writes on each rerun | 0 |

The end-state verifier passed all 105 checks, including one current Active
Bellhaven account for every website facility, preservation of all original
accounts and financial values, and correspondence between actual changes and
approved payloads. See [submission/verification.json](submission/verification.json),
[submission/locations.csv](submission/locations.csv), and
[submission/decisions.csv](submission/decisions.csv).

## Scraper choices

The directory contains 34 locations over three pages, while the homepage links
to Bellhaven Meadows of Findlay separately and advertises 35 communities. The
crawler follows both directory and homepage links, so Findlay is included.
Each location has the requested name, address, city, state, ZIP, and care
offerings, with source URL and archived HTML. It rejects incomplete crawls
instead of inferring that facilities disappeared.

## Missing accounts created

| Facility | New account |
|---|---|
| Amberly Manor, Hudson, OH | 001FF0765B5D75C548 |
| Bellhaven at Union Square, New Albany, OH | 001344BC744A214FFC |
| Bellhaven of Batavia, OH | 001D735E7FB767CA2C |
| Bellhaven of Carlisle, PA | 001D0D1AC3642E521F |

Amberly Manor in Colorado Springs is a different facility with the same name;
it was left alone. This illustrates why matching includes locality and address.

## Ownership corrections and the billing SOP

Crossings of Lima, Meadows of Findlay, Kettering, and Zanesville were re-parented
directly. Lima and Findlay have revenue history but zero outstanding AR.
Kettering and Zanesville have no revenue history. These satisfy the direct-move
branch of the SOP.

Marietta and Tiffin required protected change-of-ownership accounts:

| Facility | Revenue / outstanding AR | Old account retained under Cedar Trail | New Bellhaven account |
|---|---|---|---|
| Marietta | $51,250 / $3,800 | 001A34WFSUYHCRBLFT | 0019708D63D93C24CD |
| Tiffin | $84,000 / $12,400 | 001U6RW32TY0WSXZZB | 00133D3466ED9A4EC5 |

Both old accounts retain their original parent, name, status, note, billing
fields, phone, and financial values. Their only changed business field is
`chow_current_account`, pointing to the respective successor. The API also
updates its server timestamp. Financial history was not copied into either
new account. These old/new pairs are CHOW records, not duplicates to inactivate.

## Duplicate choices

Seven losing copies across five facilities were marked Inactive, linked through
`duplicate_of_account`, and given explanatory notes. No account was merged or
deleted, and each losing copy retained its parent and financial fields.

| Facility | Survivor | Losing copies |
|---|---|---|
| Gardens of Monroe | 001U1750VLVJAGG1S5 | 0011AB44D05WLA9HTX; 00159PL81N38KM4FHM |
| Shores of Erie | 001CVBBCSDM7YHN220 | 001BLYF02K97SZLZHH |
| Kettering | 001WR41PYNWXCAE2X4 | 0016KTS1UAWBRXS09J; 001B7XZAA3AFALS9GP |
| Owosso | 001EGU7BMJ942ZTRE6 | 001QU150PM4Z15UA71 |
| Port Clinton | 001UELXDAKFRKB8932 | 001JD2MWRA74LTSN24 |

The groups share full normalized facility addresses and compatible care types,
with one website facility per address. Bellhaven's current-brand account was
retained where available. Owosso's survivor also matches the website phone.
The earlier Owosso draft was superseded before any write when that supporting
evidence refined the survivor choice. At Kettering, all three copies had zero
revenue/AR and none matched the website phone; deterministic selection retained
one account, renamed/re-parented it, and inactivated the other copies.

## Other fixes and deliberate restraint

Nine proposals addressed name/care/ZIP discrepancies: Ashland, Grove City,
Shores of Erie, Willow Creek, Sycamore Ridge, Chagrin Falls, Chesterton,
Portsmouth, and the Arbors at Bellhaven in Dayton. Ownership proposals also
corrected the Kettering and Zanesville names and Findlay's second care offering.
Website Memory Support maps to CRM Memory Care; rehabilitation/nursing maps to
Skilled Nursing. Both care offerings are retained for Erie and Findlay.
Portsmouth's ZIP was corrected from 45626 to 45662. Equivalent address spelling
was left alone.

**Rejected:** Ashtabula's suggested replacement of billing street `PO Box 517`
with website street `3156 W Prospect Rd`. The account's exact name, locality,
and phone establish identity. The physical website address does not establish
that its billing mailing address is wrong. The billing field was preserved,
the rejection is recorded, and repeat runs do not re-propose it.

Alliance, Coldwater, and Sandusky do not appear in the complete website crawl.
They were marked Needs Review with notes, retaining ownership and billing data.
Website absence alone does not establish closure or a new owner. Sandusky has
$130,000 revenue history and $5,200 outstanding AR; no parent change was made.
Any future confirmed ownership change must follow the protected CHOW branch.

## Review and daily safety

Every applied proposal was reviewed in the local app and approved under a
reviewer identity identifying Codex as acting for Sam Liebl. No pipeline run
approved changes automatically. Each API write was checked by a fresh GET.

SQLite persists decisions and per-step operation journals. Stable fingerprints
prevent identical decisions from returning. Session form tokens, current-value
checks, host-level locks, and conditional decision updates protect the approval
flow. Create operation markers allow recovery after a lost response. Uncertain
creates are held for investigation instead of retried blindly. Partial approved
plans stay in recovery instead of generating new creates on the next daily run.

The included cron configuration schedules proposal generation at 06:00
America/New_York on a persistent host. It is an example and is not installed.
The `data/` directory must be preserved and backed up; a fresh clone does not
include ignored operational state.

## Validation and remaining limits

29 offline tests pass. They cover billing thresholds and old-account
preservation, writes requiring approval, rejected/applied repeat runs, stale
data, duplicate survivor selection, interrupted writes, homepage-only locations,
and incomplete-crawl refusal. An independent read-only code audit also found
and prompted fixes for truncated CRM pagination, malformed account IDs, blank
required website content, and CHOW plans containing reviewed duplicate copies.
Regression tests now cover these cases and stale duplicate identity evidence.
Live verification separately checked the end state
and approved fields. Two complete website/CRM reruns returned zero new proposals
and zero writes.

The API does not document conditional updates or server idempotency. Local
serialization and journal/marker recovery protect this persistent host; a
separate external CRM writer can still race after a read. The three absent
facilities need business investigation, and Ashtabula's billing-versus-physical
address distinction remains intentionally preserved. These are recorded data
decisions, not an unapproved queue.
