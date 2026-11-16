# Condo Fault Report System

This is our Python 3.11 complaint reporting app. Residents can submit complaints.
Admins can manage reports, review complaints when the AI fails, view history,
and search for reports. The app uses Gemini to analyse complaints and JSON to save them.

Demo admin account:
- Username: `admin123`
- Password: `password123`

## 1. Set up Docker

Open Docker Desktop and make sure it is using Linux containers.
Use the `appNEW` branch, then open PowerShell in the project folder.

Create the folders for saved reports and photos:

```powershell
New-Item -ItemType Directory -Force data, images | Out-Null
```

Run this to create `.env` if you do not already have it:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Open `.env` and enter your own Gemini API key like this:

```text
GEMINI_API_KEY=your-key
```

Do not upload `.env` or your key to GitHub. If the key is missing or the AI fails,
the complaint is saved as Pending Manual Review for an admin to check.

## 2. Build the image

```powershell
docker build -t g4-condo-fault-report:local .
```

Run this again after changing the Python code.

## 3. Run the app

Copy the whole command below into PowerShell. The backticks let the command
continue on the next line.

```powershell
docker run --rm -it --env-file .env `
  -e TZ=Asia/Singapore `
  -v "${PWD}/data:/app/data" `
  -v "${PWD}/images:/app/images:ro" `
  g4-condo-fault-report:local
```

Choose Resident or Admin at the welcome screen. Type `quit` to close the app.

- `--rm` removes the container when the app closes.
- `-it` lets you type into the app.
- `--env-file` reads the settings from `.env`.
- `-v` lets Docker use the folders on your computer.

## 4. Where the data is saved

Reports are saved in `data/reports.json` on your computer. The run command above
keeps this folder outside the container, so reports, statuses and history remain
when you close and reopen the app. Keep the `data` folder and use the same run command.
Without this folder connection, reports are lost when the container is removed.

The app uses `/app/data/reports.json` inside Docker. `REPORTS_FILE` tells the app
which file to use. We connect the whole folder because saving a report involves
writing a temporary file and then replacing the old JSON file.

For a photo, put it in `images` and enter a path such as `images/photo.jpg` in the
app. Keep the photo there for later review. A Windows path such as `C:\...` will
not work inside Docker.

If you want to use reports from an earlier Python run, back up your files first.
Copy the old `reports.json` into `data/reports.json` only if you intend to replace
that file. These two report files do not update each other automatically.
Old photo paths may also need updating. Do not upload personal reports or photos
to GitHub.

## 5. Run the tests

Build the image first, then run:

```powershell
docker run --rm g4-condo-fault-report:local python -m unittest -v test_ai_manager test_oop test_admin_features test_data_manager_storage test_docker_persistence
docker run --rm g4-condo-fault-report:local python test_pipeline.py
docker run --rm g4-condo-fault-report:local python test_input_validation.py
```

The tests use temporary files and sample AI responses. They do not call Gemini
or change your saved complaints.

To check saved data yourself, submit a test complaint, note its ID, and quit.
Run the app again and log in as admin to check that the report is still there.
Use a separate test data folder if you already have real complaints.

## Run without Docker

You can also run the app directly in PowerShell:

```powershell
python -m pip install -r requirements.txt
$env:GEMINI_API_KEY = "your-key"
python main.py
```

This saves to `reports.json` in the project folder unless you set `REPORTS_FILE`.
When running this way, the app does not read `.env` automatically.

## Test results - 16 November 2026

The image `g4-condo-fault-report:local` was built from `appNEW` with the Docker changes.

- The image built successfully and the app opened and closed normally.
- All 41 unit tests, the pipeline checks and input validation passed in Docker.
- After removing the first container, a new container could read `complaint_001`,
  its Resolved status and its two history entries. The next ID was `complaint_002`.
- The image did not contain `.env`, existing reports or the `.git` folder.

These checks used test data. A real Gemini API request was not tested.
