# Complaint storage and history format

## Storage

The application stores complaints in reports.json as a JSON list.
JsonReportRepository loads and saves the records.

Each complaint contains seven items:

| Index | Value |
|---|---|
| 0 | Complaint ID |
| 1 | Resident name |
| 2 | Phone number stored as text |
| 3 | Original complaint description |
| 4 | Image path or no_image |
| 5 | Submission timestamp |
| 6 | Dictionary containing analysis, status and history |

## Complaint status

Accepted complaints start with Pending Action.

Other statuses are:
- Contractor contacted
- Resolved
- Pending Manual Review when AI processing is unavailable

Pending complaints require approval before normal status updates.

## Activity history

The details dictionary contains a history list.

Each event includes:
- timestamp: when the action occurred
- action: submission, edit, status change or manual approval
- actor: Resident or Admin
- changes: changed fields with their old and new values

Existing history is preserved when a complaint changes.
Older records without history remain readable.
Deleting a complaint also deletes its history.

## Persistence and failed writes

The repository writes a temporary file before replacing reports.json.
The complaint and its history are saved together.

A missing file is treated as an empty collection.
A corrupt file raises an error instead of being silently overwritten.
If replacement fails, the original file remains unchanged.

## Verification

Run:

python -m unittest test_data_manager -v

Tests use temporary files rather than real complaint records.
Record the actual test result after running the command.