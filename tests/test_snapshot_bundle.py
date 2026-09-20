import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backtest_hpg.infrastructure.snapshot_bundle import capture_bundle, read_bundle


class SnapshotBundleTest(unittest.TestCase):
    def test_round_trip_integrity_and_partial_download(self):
        raw = json.dumps(dict(s="ok", t=[1773626400], o=[100], h=[101],
                              l=[99], c=[100], v=[5])).encode()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "bundle"
            with patch("backtest_hpg.infrastructure.snapshot_bundle.urlopen",
                       side_effect=[io.BytesIO(raw), io.BytesIO(b'{"s":"no_data"}')]):
                with self.assertRaises(ValueError):
                    capture_bundle(target)
            self.assertFalse(target.exists())
            with patch("backtest_hpg.infrastructure.snapshot_bundle.urlopen",
                       side_effect=[io.BytesIO(raw), io.BytesIO(raw)]):
                path = capture_bundle(target)
            manifest = read_bundle(path)
            self.assertEqual(len(manifest["datasets"]), 2)
            self.assertEqual(manifest["mode"], "raw_capture_not_backtest_ready")
            self.assertTrue(manifest["datasets"][0]["extracted_at"].endswith("+00:00"))
            altered = json.loads(path.read_bytes())
            altered["datasets"][0]["start"] = "2020-01-01T09:00:00+07:00"
            path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "range mismatch"):
                read_bundle(path)
            path.write_text(json.dumps(manifest), encoding="utf-8")
            (target / manifest["datasets"][0]["raw_path"]).write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                read_bundle(path)


if __name__ == "__main__":
    unittest.main()
