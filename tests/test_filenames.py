import unittest
from datetime import datetime, timezone

from cdmods.filenames import parse_candidates


def utc(text):
    return int(datetime.strptime(text, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc).timestamp())


# Real archive names from a Crimson Desert mod folder: (filename, name, mod ID, version, sqid).
REAL_NAMES = [
    ("Better Custom Markers-203-1-7-1778420608.zip", "Better Custom Markers", 203, "1.7", None),
    ("Better Inventory and Trade UI 452 3.1 2026-09-07T20-00Z g7OwxhwXd.zip", "Better Inventory and Trade UI", 452, "3.1", "g7OwxhwXd"),
    ("Better Knowledge Card (RAW) 224 1.9 2026-08-26T07-51Z LVZD4oi2c.zip", "Better Knowledge Card (RAW)", 224, "1.9", "LVZD4oi2c"),
    ("Better Radial Menus 618 2.8.1 2026-09-07T16-29Z QnWuyNush.zip", "Better Radial Menus", 618, "2.8.1", "QnWuyNush"),
    (
        "Better Status Bar (Fixed Zoom map) No Dragon HP 820 2.3 2026-09-07T17-56Z ifG1RW1Nc.zip",
        "Better Status Bar (Fixed Zoom map) No Dragon HP", 820, "2.3", "ifG1RW1Nc",
    ),
    ("CD JSON Mod Manager V9.9.3-113-9-9-3-1777103670.zip", "CD JSON Mod Manager V9.9.3", 113, "9.9.3", None),
    ("Clean Kills-334-1-1-1778478892.zip", "Clean Kills", 334, "1.1", None),
    ("No Intro (CCMM)-731-1-0-1775505664.zip", "No Intro (CCMM)", 731, "1.0", None),
    ("Subtitles Outlined (RAW)-208-1-5-1-1777202999.zip", "Subtitles Outlined (RAW)", 208, "1.5.1", None),
    ("saveslot_mod_v1 659 0.9.5 2026-08-27T05-02Z nySpzGLRO.7z", "saveslot_mod_v1", 659, "0.9.5", "nySpzGLRO"),
    ("Healthbar Always On 2.00.00 2406 1 2026-08-27T20-12Z Aq02rzu9p.zip", "Healthbar Always On 2.00.00", 2406, "1", "Aq02rzu9p"),
    ("CrimsonSharpAlphaV08a1-84-0-8-1-1776240537.zip", "CrimsonSharpAlphaV08a1", 84, "0.8.1", None),
    (
        "Healthbar Always On and multi target from Caites 2406 10 2026-08-16T11-52Z kbnNJiPz3.zip",
        "Healthbar Always On and multi target from Caites", 2406, "10", "kbnNJiPz3",
    ),
]


class ParseCandidatesTest(unittest.TestCase):
    def test_real_names(self):
        for filename, name, mod_id, version, sqid in REAL_NAMES:
            with self.subTest(filename):
                first = parse_candidates(filename)[0]
                self.assertEqual((first.name, first.mod_id, first.version, first.sqid), (name, mod_id, version, sqid))

    def test_upload_time(self):
        self.assertEqual(parse_candidates("Clean Kills-334-1-1-1778478892.zip")[0].uploaded, 1778478892)
        current = parse_candidates("Better Inventory and Trade UI 452 3.1 2026-09-07T20-00Z g7OwxhwXd.zip")[0]
        self.assertEqual(current.uploaded, utc("2026-09-07T20:00"))

    def test_current_format_has_one_reading(self):
        self.assertEqual(len(parse_candidates("Better Radial Menus 618 2.8.1 2026-09-07T16-29Z QnWuyNush.zip")), 1)

    def test_browser_duplicate_suffix(self):
        self.assertEqual(parse_candidates("Clean Kills-334-1-1-1778478892 (1).zip")[0].mod_id, 334)
        self.assertEqual(parse_candidates("Better Radial Menus 618 2.8.1 2026-09-07T16-29Z QnWuyNush (2).zip")[0].sqid, "QnWuyNush")

    def test_extension_is_case_insensitive(self):
        self.assertEqual(parse_candidates("Clean Kills-334-1-1-1778478892.ZIP")[0].mod_id, 334)

    def test_not_nexus_names(self):
        for filename in ["readme.txt", "MyMod.zip", "Clean Kills-334-1-1-1778478892.txt", "Mod-12.zip"]:
            with self.subTest(filename):
                self.assertEqual(parse_candidates(filename), [])

    def test_number_in_name_offers_other_readings(self):
        # "Patch-12" could be the name, or the name could be "Patch" with mod ID 12.
        readings = [(c.name, c.mod_id, c.version) for c in parse_candidates("Patch-12-34-1-0-1778478892.zip")]
        self.assertEqual(readings[:2], [("Patch", 12, "34.1.0"), ("Patch-12", 34, "1.0")])

    def test_prefers_numeric_versions(self):
        first = parse_candidates("Fix-2-Thing-334-1-0-1778478892.zip")[0]
        self.assertEqual((first.name, first.mod_id, first.version), ("Fix-2-Thing", 334, "1.0"))

    def test_letters_in_version(self):
        first = parse_candidates("Some Mod-500-1-0b-1778478892.zip")[0]
        self.assertEqual((first.mod_id, first.version), (500, "1.0b"))


if __name__ == "__main__":
    unittest.main()
