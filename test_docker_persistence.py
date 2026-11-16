"""Offline Docker storage checks: python -m unittest -v test_docker_persistence."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from main import ApplicationFactory


class DockerPersistenceTests(unittest.TestCase):
    """Verify the startup path and records across independent processes."""

    def test_factory_storage_override(self):
        """Use mounted storage unless the caller provides an explicit path."""
        with TemporaryDirectory() as folder:
            mounted = Path(folder) / 'mounted.json'
            explicit = Path(folder) / 'explicit.json'
            with patch.dict(os.environ, {'REPORTS_FILE': str(mounted)}):
                self.assertEqual(ApplicationFactory.create()._data.reports_file, mounted)
                self.assertEqual(ApplicationFactory.create(explicit)._data.reports_file, explicit)

    def test_records_survive_new_process(self):
        """Reload ID, status and history from disk without a live AI request."""
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'reports.json'
            with patch.dict(os.environ, {'REPORTS_FILE': str(path)}):
                repository = ApplicationFactory.create()._data
                complaint = [repository.get_next_complaint_id(), 'Test Resident',
                             '91234567', 'Test leak', 'no_image',
                             '2026-11-15T10:00:00+08:00',
                             {'accepted': True, 'is_unclear': False,
                              'status': 'Pending Action'}]
                repository.save_report(complaint, actor='Resident')
                saved = repository.update_complaint_status(complaint[0], 'Resolved')
                result = subprocess.run(
                    [sys.executable, '-B', '-c',
                     'import json; from main import ApplicationFactory; '
                     'r = ApplicationFactory.create()._data; '
                     'print(json.dumps([r.load_reports(), r.get_next_complaint_id()]))'],
                    check=True, capture_output=True, text=True,
                )
                records, next_id = json.loads(result.stdout)
                self.assertEqual(records, [saved])
                self.assertEqual(records[0][6]['status'], 'Resolved')
                self.assertEqual(len(records[0][6]['history']), 2)
                self.assertEqual(next_id, 'complaint_002')


if __name__ == '__main__':
    unittest.main(verbosity=2)
