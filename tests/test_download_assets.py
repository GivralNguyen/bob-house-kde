import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import download_assets as downloader


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'assets'
        self.entries = [{'path': name, 'url': 'https://wuffs.org/bob/test',
                         'size': 4, 'sha256': hashlib.sha256(b'test').hexdigest()}
                        for name in ('ROVER.ACT', 'rooms/source/data.json')]
        self.manifest = self.root / 'manifest.json'
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps({'files': self.entries}))

    def test_path_escape_rejected(self):
        self.entries[0]['path'] = '../outside'
        self.write_manifest()
        with self.assertRaises(ValueError):
            downloader.load_manifest(self.manifest)

    def test_unexpected_host_rejected(self):
        self.entries[0]['url'] = 'http://other.example/a'
        self.write_manifest()
        with self.assertRaises(ValueError):
            downloader.load_manifest(self.manifest)

    def test_bad_download_leaves_no_assets(self):
        with patch.object(downloader, 'fetch', side_effect=OSError('network failed')):
            with self.assertRaises(OSError):
                downloader.download(self.target, self.manifest)
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.root.glob('.bob-download-*')))

    def test_hash_mismatch_rejected(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def geturl(self): return 'https://wuffs.org/bob/test'
            def read(self, size): return b'evil'
        with patch.object(downloader, 'urlopen', return_value=Response()):
            with self.assertRaises(ValueError):
                downloader.fetch(self.entries[0], self.root / 'output')
        self.assertFalse((self.root / 'output').exists())

    def test_existing_assets_never_overwritten(self):
        self.target.mkdir()
        (self.target / 'ROVER.ACT').write_bytes(b'keep')
        with patch.object(downloader, 'fetch') as fetch:
            with self.assertRaises(ValueError):
                downloader.download(self.target, self.manifest)
            fetch.assert_not_called()
        self.assertEqual((self.target / 'ROVER.ACT').read_bytes(), b'keep')

    def test_complete_download_and_no_network_on_rerun(self):
        def fetch(entry, target):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'test')
        with patch.object(downloader, 'fetch', side_effect=fetch), patch.object(downloader, 'validate'):
            downloader.download(self.target, self.manifest)
        with patch.object(downloader, 'fetch') as fetch, patch.object(downloader, 'validate'):
            downloader.download(self.target, self.manifest)
            fetch.assert_not_called()
        self.assertTrue((self.target / 'NOTICE.txt').exists())


if __name__ == '__main__':
    unittest.main()
