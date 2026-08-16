#!/usr/bin/env python3
"""Focused tests for the Kiwi release metadata contract."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from release_metadata import (
    _installed_payload_entry,
    load_manifest,
    wheel_installation_hash,
    wheel_platform_tag,
)


class ReleaseMetadataTest(unittest.TestCase):
    def test_manifest_declares_content_addressable_release_identity(self) -> None:
        manifest = load_manifest()
        self.assertEqual(manifest["version"], "1.231.0+kiwi.4")
        self.assertRegex(str(manifest["upstreamCommit"]), r"^[a-f0-9]{40}$")
        self.assertEqual(manifest["pythonVersion"], "3.12")
        self.assertEqual(manifest["rustToolchain"], "1.97.1")

    def test_wheel_platform_tag_is_taken_from_artifact_name(self) -> None:
        wheel = Path(
            "nautilus_trader-1.231.0+kiwi.4-cp312-cp312-macosx_14_0_arm64.whl"
        )
        self.assertEqual(wheel_platform_tag(wheel), "macosx_14_0_arm64")

    def test_invalid_wheel_name_is_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            wheel_platform_tag(Path("nautilus_trader.whl"))

    def test_installation_hash_is_stable_and_excludes_rewritten_record(self) -> None:
        with TemporaryDirectory() as directory:
            first = Path(directory) / "first.whl"
            second = Path(directory) / "second.whl"
            with zipfile.ZipFile(first, "w") as archive:
                archive.writestr("nautilus_trader/module.py", b"value = 1\n")
                archive.writestr("nautilus_trader-1.dist-info/METADATA", b"Version: 1\n")
                archive.writestr("nautilus_trader-1.dist-info/RECORD", b"first")
            with zipfile.ZipFile(second, "w") as archive:
                archive.writestr("nautilus_trader-1.dist-info/RECORD", b"rewritten")
                archive.writestr("nautilus_trader-1.dist-info/METADATA", b"Version: 1\n")
                archive.writestr("nautilus_trader/module.py", b"value = 1\n")
            self.assertEqual(wheel_installation_hash(first), wheel_installation_hash(second))

            with zipfile.ZipFile(second, "w") as archive:
                archive.writestr("nautilus_trader/module.py", b"value = 2\n")
                archive.writestr("nautilus_trader-1.dist-info/METADATA", b"Version: 1\n")
            self.assertNotEqual(wheel_installation_hash(first), wheel_installation_hash(second))

    def test_installed_payload_excludes_interpreter_generated_files(self) -> None:
        self.assertFalse(_installed_payload_entry("nautilus_trader/__pycache__/a.cpython-312.pyc"))
        self.assertFalse(_installed_payload_entry("nautilus_trader/a.pyc"))
        self.assertFalse(_installed_payload_entry("nautilus_trader/a.pyo"))
        self.assertFalse(_installed_payload_entry(
            "nautilus_trader-1.dist-info/uv_cache.json"
        ))
        self.assertTrue(_installed_payload_entry("nautilus_trader/a.py"))


if __name__ == "__main__":
    unittest.main()
