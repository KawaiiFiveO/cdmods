import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cdmods import cli

from .fakes import FakeNexus

ARCHIVES = [
    "Better Inventory and Trade UI 452 3.1 2026-09-07T20-00Z g7OwxhwXd.zip",
    "Better Custom Markers-203-1-7-1778420608.zip",
    "Clean Kills-334-1-1-1778478892.zip",
    "MyMod.zip",
]


class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        self.folder = root / "mods"
        self.folder.mkdir()
        for name in ARCHIVES:
            (self.folder / name).touch()
        self.list = root / "modlist.json"
        patcher = mock.patch.object(cli, "make_nexus", lambda game: FakeNexus(game))
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.dir.cleanup()

    def run_cli(self, *args, answers=()):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), mock.patch("builtins.input", side_effect=list(answers)):
            code = cli.main(["--list", str(self.list), *args])
        return code, out.getvalue(), err.getvalue()

    def entries(self):
        return json.loads(self.list.read_text(encoding="utf-8"))["entries"]

    def test_scan_then_check(self):
        code, out, _ = self.run_cli("scan", str(self.folder))
        self.assertEqual(code, 0)
        self.assertIn("Added (3)", out)
        self.assertIn("Not identified", out)
        self.assertIn("MyMod.zip", out)
        self.assertEqual(len(self.entries()), 3)

        code, out, _ = self.run_cli("check")
        self.assertEqual(code, 0)
        self.assertIn("Outdated (1)", out)
        self.assertIn("3.1 -> 3.2", out)
        self.assertIn("mods/452?tab=files&file_id=16903", out)
        self.assertIn("1 outdated, 0 gone, 2 up to date", out)

    def test_rescan_uses_saved_folder(self):
        self.run_cli("scan", str(self.folder))
        (self.folder / "Better Inventory and Trade UI 452 3.2 2026-10-06T13-06Z GgXl7mltF.zip").touch()
        code, out, _ = self.run_cli("scan")
        self.assertEqual(code, 0)
        self.assertIn("Updated (1)", out)
        self.assertIn("3.1 -> 3.2", out)
        self.assertIn("Older copies", out)

    def test_scan_needs_a_folder_the_first_time(self):
        code, _, err = self.run_cli("scan")
        self.assertEqual(code, 1)
        self.assertIn("give the folder", err)

    def test_links(self):
        self.run_cli("scan", str(self.folder))
        _, out, _ = self.run_cli("links", "--outdated")
        self.assertEqual(out.count("https://"), 1)
        self.assertIn("file_id=16903", out)
        _, out, _ = self.run_cli("links", "--current")
        self.assertEqual(out.count("https://"), 3)
        self.assertIn("file_id=14966", out)

    def test_links_open_one_at_a_time(self):
        self.run_cli("scan", str(self.folder))
        with mock.patch("webbrowser.open") as browser_open:
            self.run_cli("links", "--current", "--open", answers=["", "q"])
        self.assertEqual(browser_open.call_count, 2)

    def test_add_by_file_url(self):
        code, out, _ = self.run_cli("add", "https://www.nexusmods.com/crimsondesert/mods/452?tab=files&file_id=16903")
        self.assertEqual(code, 0)
        self.assertIn("Added: Better Inventory and Trade UI 3.2", out)
        [entry] = self.entries()
        self.assertIsNone(entry["localFile"])
        code, out, _ = self.run_cli("add", "https://www.nexusmods.com/crimsondesert/mods/452?tab=files&file_id=16903")
        self.assertIn("Already listed", out)

    def test_add_by_mod_url_asks_which_file(self):
        code, out, _ = self.run_cli("add", "https://www.nexusmods.com/crimsondesert/mods/203", answers=["1,2"])
        self.assertEqual(code, 0)
        self.assertIn("several files", out)
        self.assertEqual(sorted(e["fileId"] for e in self.entries()), [9001, 16877])

    def test_add_rejects_other_games(self):
        self.run_cli("scan", str(self.folder))
        code, _, err = self.run_cli("add", "https://www.nexusmods.com/skyrimspecialedition/mods/266")
        self.assertEqual(code, 1)
        self.assertIn("skyrimspecialedition", err)

    def test_remove(self):
        self.run_cli("scan", str(self.folder))
        self.run_cli("add", "https://www.nexusmods.com/crimsondesert/mods/203?tab=files&file_id=16877")
        code, out, err = self.run_cli("remove", "203")
        self.assertEqual(code, 1)
        self.assertIn("Several files", out)
        code, out, _ = self.run_cli("remove", "203", "7469036")
        self.assertEqual(code, 0)
        self.assertIn("Removed: Map Tweaks / Map Tweaks (Reticle And Roads)", out)
        self.assertEqual(len(self.entries()), 3)

    def test_export(self):
        self.run_cli("scan", str(self.folder))
        _, out, _ = self.run_cli("export")
        self.assertIn("| [Map Tweaks](https://www.nexusmods.com/crimsondesert/mods/203?tab=files) | Better Custom Markers | 1.7 |", out)
        output = Path(self.dir.name) / "list.csv"
        self.run_cli("export", "--format", "csv", "-o", str(output))
        lines = output.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0].split(",")[:3], ["mod_id", "mod_name", "file_id"])
        self.assertEqual(len(lines), 4)

    def test_export_html(self):
        self.run_cli("scan", str(self.folder))
        output = Path(self.dir.name) / "modlist.html"
        code, _, _ = self.run_cli("export", "--format", "html", "-o", str(output))
        self.assertEqual(code, 0)
        page = output.read_text(encoding="utf-8")
        self.assertIn("1 outdated, 0 gone, 2 up to date", page)
        rows = [line for line in page.splitlines() if line.startswith("<tr class=")]
        self.assertEqual(len(rows), 3)
        # Outdated files come first and link to the newest version.
        self.assertTrue(rows[0].startswith('<tr class="outdated">'))
        self.assertIn("Outdated: 3.1 → 3.2", rows[0])
        self.assertIn('href="https://www.nexusmods.com/crimsondesert/mods/452?tab=files&amp;file_id=16903"', rows[0])
        self.assertEqual(sum(row.startswith('<tr class="current">') for row in rows), 2)

    def test_export_html_escapes_names(self):
        self.run_cli("scan", str(self.folder))
        names = {452: "Better <UI> & Co", 203: "Map Tweaks", 334: "Clean Kills"}
        with mock.patch.object(cli, "make_nexus", lambda game: FakeNexus(game, mod_names=names)):
            self.run_cli("scan")
        _, out, _ = self.run_cli("export", "--format", "html")
        self.assertIn("Better &lt;UI&gt; &amp; Co", out)
        self.assertNotIn("<UI>", out)

    def test_commands_need_a_list(self):
        code, _, err = self.run_cli("check")
        self.assertEqual(code, 1)
        self.assertIn("no mod list", err)


if __name__ == "__main__":
    unittest.main()
