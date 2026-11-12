import json
import tempfile
import unittest
from pathlib import Path

from cdmods.modlist import Entry, ModList, ModListError, load, save


def entry(mod_id=452, group_id=7247258, file_id=14966, version="3.1", local_file="a.zip", note=""):
    return Entry(mod_id, group_id, file_id, "Better UI", "Better UI", version, 1788811226, local_file, note)


class ModListFileTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "modlist.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_round_trip(self):
        modlist = ModList("crimsondesert", 8969, "C:/Mods", [entry(note="keep the RAW version"), entry(203, 1, 9, local_file=None)])
        save(modlist, self.path)
        self.assertEqual(load(self.path), ModList("crimsondesert", 8969, "C:/Mods", modlist.sorted_entries()))

    def test_file_format(self):
        save(ModList("crimsondesert", 8969, None, [entry()]), self.path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["entries"][0]["uploaded"], "2026-09-07T20:00:26Z")
        self.assertEqual(data["entries"][0]["modId"], 452)

    def test_rejects_bad_files(self):
        self.path.write_text("not json", encoding="utf-8")
        with self.assertRaises(ModListError):
            load(self.path)
        self.path.write_text('{"version": 99}', encoding="utf-8")
        with self.assertRaisesRegex(ModListError, "version"):
            load(self.path)


class MergeScanTest(unittest.TestCase):
    def test_adds_updates_and_keeps_notes(self):
        modlist = ModList("crimsondesert", 8969, entries=[entry(note="my note")])
        result = modlist.merge_scan([entry(file_id=16903, version="3.2", local_file="b.zip"), entry(203, 1, 9)])
        self.assertEqual([e.mod_id for e in result.added], [203])
        [(before, after)] = result.updated
        self.assertEqual((before.version, after.version, after.note, after.local_file), ("3.1", "3.2", "my note", "b.zip"))
        self.assertEqual(len(modlist.entries), 2)

    def test_missing_archives_stay_listed(self):
        modlist = ModList("crimsondesert", 8969, entries=[entry(), entry(203, 1, 9, local_file=None)])
        result = modlist.merge_scan([])
        self.assertEqual([e.mod_id for e in result.missing], [452])
        self.assertEqual(len(modlist.entries), 2)
        self.assertIsNone(modlist.entries[0].local_file)

    def test_rescan_without_changes(self):
        modlist = ModList("crimsondesert", 8969, entries=[entry()])
        result = modlist.merge_scan([entry()])
        self.assertEqual((result.added, result.updated, result.missing), ([], [], []))


if __name__ == "__main__":
    unittest.main()
