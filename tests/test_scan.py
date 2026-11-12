import tempfile
import unittest
from pathlib import Path

from cdmods.scan import scan

from .fakes import FakeNexus, nf


class ScanTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.folder = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def touch(self, *names):
        for name in names:
            path = self.folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    def test_identifies_both_name_formats(self):
        self.touch(
            "Better Inventory and Trade UI 452 3.1 2026-09-07T20-00Z g7OwxhwXd.zip",
            "Better Custom Markers-203-1-7-1778420608.zip",
            "Clean Kills-334-1-1-1778478892.zip",
        )
        result = scan(self.folder, FakeNexus())
        found = {(e.mod_id, e.file_id): e for e in result.found}
        self.assertEqual(set(found), {(452, 14966), (203, 9001), (334, 9100)})
        self.assertEqual(found[(203, 9001)].mod_name, "Map Tweaks")
        self.assertEqual(found[(203, 9001)].file_name, "Better Custom Markers")
        self.assertEqual(found[(452, 14966)].local_file, "Better Inventory and Trade UI 452 3.1 2026-09-07T20-00Z g7OwxhwXd.zip")
        self.assertEqual(result.unidentified, [])
        self.assertEqual(result.archives, 3)

    def test_keeps_newest_copy_per_group(self):
        self.touch(
            "Better Inventory and Trade UI 452 3.0 2026-08-26T15-38Z mhw3QMq4Q.zip",
            "Better Inventory and Trade UI 452 3.1 2026-09-07T20-00Z g7OwxhwXd.zip",
            "Healthbar Always On 2.00.00 2406 1 2026-08-27T20-12Z Aq02rzu9p.zip",
            "Healthbar Always On 2.01.00 2406 2 2026-09-04T17-48Z qrIkcUpZs.zip",
        )
        result = scan(self.folder, FakeNexus())
        self.assertEqual(sorted(e.file_id for e in result.found), [14695, 14966])
        self.assertEqual(
            [name for name, _ in result.older_copies],
            ["Better Inventory and Trade UI 452 3.0 2026-08-26T15-38Z mhw3QMq4Q.zip", "Healthbar Always On 2.00.00 2406 1 2026-08-27T20-12Z Aq02rzu9p.zip"],
        )

    def test_unidentified(self):
        self.touch(
            "MyMod.zip",
            "Better Inventory and Trade UI 452 3.1 2026-09-07T20-00Z zzzzzzzzz.zip",  # unknown sqid
            "notes.txt",
        )
        result = scan(self.folder, FakeNexus())
        self.assertEqual(result.found, [])
        self.assertEqual(result.unidentified, ["Better Inventory and Trade UI 452 3.1 2026-09-07T20-00Z zzzzzzzzz.zip", "MyMod.zip"])
        self.assertEqual(result.archives, 2)

    def test_falls_back_to_other_readings(self):
        files = {34: [nf(34, 77, 700, "Patch-12", "1.0", "MAIN", 1778478892)]}
        self.touch("Patch-12-34-1-0-1778478892.zip")
        nexus = FakeNexus(files=files, mod_names={34: "Patches"})
        [found] = scan(self.folder, nexus).found
        self.assertEqual((found.mod_id, found.file_id), (34, 77))
        self.assertEqual(nexus.requested, [[12], [34]])

    def test_each_mod_is_fetched_once(self):
        self.touch(
            "Better Inventory and Trade UI 452 3.0 2026-08-26T15-38Z mhw3QMq4Q.zip",
            "Better Inventory and Trade UI 452 3.1 2026-09-07T20-00Z g7OwxhwXd.zip",
            "Clean Kills-334-1-1-1778478892.zip",
        )
        nexus = FakeNexus()
        scan(self.folder, nexus)
        self.assertEqual(nexus.requested, [[334, 452]])

    def test_subfolders_only_when_recursive(self):
        self.touch("old/Clean Kills-334-1-1-1778478892.zip")
        self.assertEqual(scan(self.folder, FakeNexus()).found, [])
        [found] = scan(self.folder, FakeNexus(), recursive=True).found
        self.assertEqual(found.local_file, "old/Clean Kills-334-1-1-1778478892.zip")


if __name__ == "__main__":
    unittest.main()
