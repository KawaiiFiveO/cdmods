import unittest

from cdmods.modlist import Entry
from cdmods.status import State, classify

from .fakes import FILES


def entry_for(f, **changes):
    entry = Entry(f.mod_id, f.group_id, f.file_id, "Mod", f.name, f.version, f.date)
    for name, value in changes.items():
        setattr(entry, name, value)
    return entry


class ClassifyTest(unittest.TestCase):
    def test_outdated(self):
        status = classify(entry_for(FILES[452][1]), FILES[452])
        self.assertIs(status.state, State.OUTDATED)
        self.assertEqual(status.latest.version, "3.2")

    def test_current(self):
        status = classify(entry_for(FILES[452][2]), FILES[452])
        self.assertIs(status.state, State.CURRENT)

    def test_renamed_file_in_same_group_is_an_update(self):
        status = classify(entry_for(FILES[2406][0]), FILES[2406])
        self.assertIs(status.state, State.OUTDATED)
        self.assertEqual(status.latest.name, "Healthbar Always On 2.01.00")

    def test_other_groups_are_ignored(self):
        # The mod's other files (Map Tweaks 2.9) aren't updates to Better Custom Markers.
        status = classify(entry_for(FILES[203][0]), FILES[203])
        self.assertIs(status.state, State.CURRENT)

    def test_group_with_no_current_file_is_gone(self):
        status = classify(entry_for(FILES[2406][2]), FILES[2406])
        self.assertIs(status.state, State.GONE)
        self.assertEqual([f.file_id for f in status.alternatives], [14695])

    def test_removed_mod_is_gone(self):
        status = classify(entry_for(FILES[452][2]), [])
        self.assertIs(status.state, State.GONE)
        self.assertIn("removed", status.reason)

    def test_newer_than_anything_listed_is_current(self):
        status = classify(entry_for(FILES[452][2], file_id=99999, uploaded=1800000000), FILES[452])
        self.assertIs(status.state, State.CURRENT)


if __name__ == "__main__":
    unittest.main()
