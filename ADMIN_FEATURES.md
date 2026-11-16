# New and improved admin features

Run `python main.py` on `appNEW` and log in using the existing demo admin account.
Source comments marked `New feature` or `Improved feature` identify the additions.

## Pending-review notification

After successful admin login, and whenever the admin returns to the main menu,
the application reloads the pending-review count. An attention message appears
when the count is greater than zero; option 3 also shows the count. Residents
cannot see this notification. A read failure displays "unavailable" rather than
incorrectly claiming there are no pending complaints.

This is an in-app notification. It refreshes at menu boundaries, not while the
app is waiting for input, and does not send email or notify an offline admin.

## Complaint activity history

Choose **View reports > 5. View complaint history**, then enter the complaint ID.
The same bordered table style displays the time, action, actor and old/new values.
Long entries wrap inside their cells. New submissions, manual approvals, contact
or fault edits, and status changes are recorded. Unchanged values, cancelled
actions and failed writes do not add events.

History is a `history` list inside the seventh item's details dictionary. Each
event contains `timestamp`, `action`, `actor` and `changes`. For example:

```json
{
  "timestamp": "2026-11-04T10:30:00+08:00",
  "action": "Status changed",
  "actor": "Admin",
  "changes": {
    "status": {"old": "Pending Action", "new": "Contractor contacted"}
  }
}
```

The repository saves the event and complaint change in one atomic write,
retaining earlier entries even when Gemini reanalysis replaces the current
details. `save_report()` returns the saved copy, including history; it does not
modify its input.

Older complaints still work and are not rewritten merely by opening them. Their
history starts with the next successful change; previous actions are not invented.
Actors are labelled Resident or Admin. The shared demo account cannot identify
individual admins. Deleting a complaint also deletes its history; this is a
simple activity log, not a separate or tamper-proof audit archive.

## Search and filter reports

Choose **View reports > 6. Search and filter reports**. Enter any combination of:

- Keyword: matches current ID, resident name, phone, description or issue summary.
- Status: Pending Manual Review, Pending Action, Contractor contacted or Resolved.
- Fault category and priority.
- Inclusive submission date range, using `YYYY-MM-DD` and the date recorded on the complaint.

Text matching ignores case. All supplied criteria must match. Leave a field blank
for no restriction, or type `back` at any prompt to cancel. Leaving every field
blank displays all reports. Results use the complaint table; no matches produce
a clear message. Search does not match previous values stored in history.

Filters apply to that search only. The action menu returns without immediately
printing all reports over the results. To run another search or show all reports,
choose option 6 again. Older records with invalid dates can still be found without
a date filter, but are excluded when a date range is supplied.

**Example:** enter keyword `leak`, select Pending Action and plumbing, leave
priority blank, and enter your desired submission dates. Only complaints matching
all of those criteria appear.

## Updated reports menu

1. Update complaint status
2. View complaint by ID
3. Edit complaint
4. Delete complaint
5. View complaint history
6. Search and filter reports
7. Go back to main menu

## Offline verification

Run `python -m unittest -v test_admin_features` for the new feature checks. The
tests use temporary JSON files and simulated input/AI, including failed saves,
legacy records, restart persistence, permissions, date validation and cancellation.
The existing `test_pipeline.py`, `test_oop.py` and `test_input_validation.py` checks
remain available as regression coverage.
