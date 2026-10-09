import json
import sys
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import data_manager
import main

def example_analysis(**changes):
    """Return a fresh sample AI dictionary, overriding fields from changes.

    Keyword arguments let tests create different hazards or invalid values
    without changing the default example used by other tests.
    """
    result = {
        "fault_category": "plumbing",
        "summary": "A pipe is leaking in the shared corridor.",
        "risk_indicators": ["active_leak"],
        "common_area_hazard": True,
        "is_unclear": False,
    }
    result.update(changes)
    return result

def test_complaint_ids():
    """Verify readable IDs, restart persistence, and safe failure handling.

    Use temporary storage and real input collection with simulated answers.
    Return None when numbering and saved records match all expectations.
    """

    with TemporaryDirectory() as folder:
        path = Path(folder) / "reports.json"
        with patch.object(data_manager, "REPORTS_FILE", path):
            assert data_manager.get_next_complaint_id() == "complaint_001"
            path.write_text("[]", encoding="utf-8")
            assert data_manager.get_next_complaint_id() == "complaint_001"

            for expected in ("complaint_001", "complaint_002"):
                with patch("builtins.input", side_effect=["Test Resident", "91234567", "Pipe leaking", "n"]), patch("builtins.print"), patch("ai_manager.analyze_complaint", return_value=example_analysis()):
                    saved = main.process_new_report()
                assert saved[0] == expected
            assert [report[0] for report in data_manager.load_reports()] == ["complaint_001", "complaint_002"]

            # A separate Python process must derive its number from disk too.
            result = subprocess.run(
                [sys.executable, "-B", "-c",
                 "import sys; from pathlib import Path; import data_manager, io_manager; "
                 "data_manager.REPORTS_FILE = Path(sys.argv[1]); "
                 "io_manager.show_message(data_manager.get_next_complaint_id())", str(path)],
                cwd=Path(__file__).resolve().parent,
                capture_output=True, text=True, check=True,
            )
            assert result.stdout.strip() == "complaint_003"

            before = path.read_bytes()
            with patch("builtins.input", side_effect=["Test Resident", "91234567", "Unclear fault", "n"]), patch("builtins.print"), patch("ai_manager.analyze_complaint", return_value=example_analysis(is_unclear=True)):
                assert main.process_new_report() is None
            assert path.read_bytes() == before
            assert data_manager.get_next_complaint_id() == "complaint_003"

            for ids, expected in [
                (["HDB-legacy"], "complaint_002"),
                (["complaint_009", "complaint_002"], "complaint_010"),
                (["complaint_999"], "complaint_1000"),
                (["HDB-legacy", "complaint_007"], "complaint_008"),
            ]:
                path.write_text(json.dumps([[value] for value in ids]), encoding="utf-8")
                assert data_manager.get_next_complaint_id() == expected

            path.write_text("{broken", encoding="utf-8")
            with patch("io_manager.collect_complaint") as collect, patch("io_manager.show_message"):
                assert main.process_new_report() is None
                collect.assert_not_called()
            assert path.read_text(encoding="utf-8") == "{broken"

if __name__ == "__main__":
    test_complaint_ids()