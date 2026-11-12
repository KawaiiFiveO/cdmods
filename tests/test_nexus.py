import unittest

from cdmods.nexus import Nexus, NexusError, file_url, parse_url


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.payloads = []

    def __call__(self, payload):
        self.payloads.append(payload)
        return self.responses.pop(0)


GAME = {"data": {"game": {"id": "8969"}}}


class NexusTest(unittest.TestCase):
    def test_mod_files_batches_aliases_and_sorts(self):
        transport = FakeTransport(
            GAME,
            {
                "data": {
                    "m452": [
                        {"fileId": 16903, "groupId": 7247258, "name": "B", "version": "3.2", "category": "MAIN", "date": 200, "sqid": "x"},
                        {"fileId": 14966, "groupId": 7247258, "name": "B", "version": "3.1", "category": "OLD_VERSION", "date": 100, "sqid": "y"},
                    ],
                    "m999": [],
                }
            },
        )
        files = Nexus("crimsondesert", transport).mod_files([999, 452, 452])
        self.assertEqual([f.file_id for f in files[452]], [14966, 16903])
        self.assertEqual(files[999], [])
        self.assertFalse(files[452][0].is_current)
        self.assertTrue(files[452][1].is_current)
        query = transport.payloads[1]["query"]
        self.assertIn("m452: modFiles(modId: 452, gameId: 8969)", query)
        self.assertEqual(query.count("modFiles("), 2)

    def test_file_without_group_is_its_own_group(self):
        transport = FakeTransport(
            GAME,
            {"data": {"m1": [{"fileId": 5, "groupId": None, "name": None, "version": None, "category": "MAIN", "date": 1, "sqid": None}]}},
        )
        f = Nexus("crimsondesert", transport).mod_files([1])[1][0]
        self.assertEqual((f.group_id, f.name, f.version, f.sqid), (-5, "", "", ""))

    def test_large_requests_are_split(self):
        ids = list(range(1, 46))
        transport = FakeTransport(GAME, *({"data": {}} for _ in range(3)))
        Nexus("crimsondesert", transport).mod_files(ids)
        self.assertEqual(len(transport.payloads), 4)

    def test_mods(self):
        transport = FakeTransport({"data": {"legacyModsByDomain": {"nodes": [{"modId": 452, "name": "Better UI", "status": "published"}]}}})
        mods = Nexus("crimsondesert", transport).mods([452, 999999])
        self.assertEqual(mods[452].name, "Better UI")
        self.assertNotIn(999999, mods)
        self.assertEqual(transport.payloads[0]["variables"]["ids"][0], {"gameDomain": "crimsondesert", "modId": 452})

    def test_errors_raise(self):
        transport = FakeTransport({"errors": [{"message": "Game not found"}], "data": {"game": None}})
        with self.assertRaisesRegex(NexusError, "Game not found"):
            Nexus("nope", transport).game_id()


class UrlTest(unittest.TestCase):
    def test_parse_url(self):
        self.assertEqual(parse_url("https://www.nexusmods.com/crimsondesert/mods/452?tab=files&file_id=16903"), ("crimsondesert", 452, 16903))
        self.assertEqual(parse_url("https://www.nexusmods.com/crimsondesert/mods/452"), ("crimsondesert", 452, None))
        self.assertEqual(parse_url("nexusmods.com/games/CrimsonDesert/mods/203?tab=description"), ("crimsondesert", 203, None))

    def test_parse_url_rejects_other_urls(self):
        with self.assertRaises(ValueError):
            parse_url("https://www.nexusmods.com/crimsondesert")

    def test_file_url(self):
        self.assertEqual(file_url("crimsondesert", 452, 16903), "https://www.nexusmods.com/crimsondesert/mods/452?tab=files&file_id=16903")


if __name__ == "__main__":
    unittest.main()
