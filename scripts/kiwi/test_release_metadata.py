#!/usr/bin/env python3
"""Focused tests for the Kiwi release metadata contract."""

from pathlib import Path
import unittest

from release_metadata import load_manifest, wheel_platform_tag


class ReleaseMetadataTest(unittest.TestCase):
    def test_manifest_declares_content_addressable_release_identity(self) -> None:
        manifest = load_manifest()
        self.assertEqual(manifest["version"], "1.231.0+kiwi.1")
        self.assertRegex(str(manifest["upstreamCommit"]), r"^[a-f0-9]{40}$")
        self.assertEqual(manifest["pythonVersion"], "3.12")
        self.assertEqual(manifest["rustToolchain"], "1.97.1")

    def test_wheel_platform_tag_is_taken_from_artifact_name(self) -> None:
        wheel = Path(
            "nautilus_trader-1.231.0+kiwi.1-cp312-cp312-macosx_14_0_arm64.whl"
        )
        self.assertEqual(wheel_platform_tag(wheel), "macosx_14_0_arm64")

    def test_invalid_wheel_name_is_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            wheel_platform_tag(Path("nautilus_trader.whl"))


if __name__ == "__main__":
    unittest.main()
