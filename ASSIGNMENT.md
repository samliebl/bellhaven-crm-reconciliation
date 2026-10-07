# Assignment and acceptance criteria

1. Scrape every Bellhaven website location: name, street address, city, state,
   ZIP, and care offerings. Preserve source evidence and follow pagination.
2. Match facilities against the CRM and classify confident matches, fixes,
   missing accounts, accounts absent from the website, duplicates, and uncertain
   identities. Accounts connect to company parents through `parent_id`.
3. Provide a small review app with evidence and exact proposed changes. A
   reviewer can approve or reject. Nothing writes without approval.
4. Supply a daily schedule configuration; it need not be live. Re-runs must be
   safe and must not re-propose already decided items.
5. The submission includes an actually corrected candidate CRM copy: run the
   pipeline, review proposals in the app, approve justified changes, and verify
   the resulting records. An unreviewed queue is not completion.

## Available outcomes

`status`: Active, Inactive, Needs Review. `note`: free-text explanation. No merge
or delete. For a confirmed duplicate, set `duplicate_of_account` on the losing
copy to the survivor's account id and mark the loser Inactive.

## Mandatory billing SOP

Before moving an account to a different parent, inspect `lifetime_revenue` and
`outstanding_ar`. If BOTH are greater than zero, do not change the old account's
parent or other business fields. Create a new account under the correct parent,
then set `chow_current_account` on the old account to the new account's id.
If either value is zero, re-parent the existing account directly. Unknown or
invalid billing data must block an ownership change pending investigation.

## Integration

Website: https://analyst-assessment-production.up.railway.app/

API docs: https://analyst-assessment-production.up.railway.app/api/docs

Authentication: candidate token in `Authorization: Bearer <token>`. Store locally
as `CRM_TOKEN` in `.env`; never put the token into source control.
