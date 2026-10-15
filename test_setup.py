"""Installer retries must reuse complete downloads and repair interrupted ones."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import setup_helper


class SetupTests(unittest.TestCase):
    def test_missing_package_requests_install(self):
        with patch('setup_helper.importlib.metadata.version',
                   side_effect=setup_helper.importlib.metadata.PackageNotFoundError):
            self.assertFalse(setup_helper.packages_ready())

    def test_wrong_package_version_requests_install(self):
        with patch('setup_helper.importlib.metadata.version', return_value='0.0.0'):
            self.assertFalse(setup_helper.packages_ready())

    def test_complete_model_reused_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('model.bin', 'config.json', 'tokenizer.json'):
                (Path(folder) / name).touch()
            with patch('faster_whisper.utils.download_model', return_value=folder) as download:
                self.assertEqual(setup_helper.prepare_model(), folder)
            self.assertEqual(download.call_count, 1)
            self.assertTrue(download.call_args.kwargs['local_files_only'])

    def test_missing_cache_downloaded(self):
        with patch('faster_whisper.utils.download_model',
                   side_effect=[FileNotFoundError(), 'downloaded']) as download:
            self.assertEqual(setup_helper.prepare_model(), 'downloaded')
        self.assertNotIn('local_files_only', download.call_args.kwargs)

    def test_interrupted_download_is_completed(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'config.json').touch()
            with patch('faster_whisper.utils.download_model',
                       side_effect=[folder, 'completed']) as download:
                self.assertEqual(setup_helper.prepare_model(), 'completed')
            self.assertEqual(download.call_count, 2)


if __name__ == '__main__':
    unittest.main()
