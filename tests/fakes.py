"""A stand-in for the Nexus API, with data copied from real Crimson Desert mods."""

from __future__ import annotations

from cdmods.nexus import NexusFile, NexusMod


def nf(mod_id, file_id, group_id, name, version, category, date, sqid=""):
    return NexusFile(mod_id, file_id, group_id, name, version, category, date, sqid)


FILES = {
    452: [
        nf(452, 14186, 7247258, "Better Inventory and Trade UI", "3.0", "OLD_VERSION", 1787758689, "mhw3QMq4Q"),
        nf(452, 14966, 7247258, "Better Inventory and Trade UI", "3.1", "OLD_VERSION", 1788811226, "g7OwxhwXd"),
        nf(452, 16903, 7247258, "Better Inventory and Trade UI", "3.2", "MAIN", 1791291994, "GgXl7mltF"),
    ],
    203: [
        nf(203, 9001, 7000001, "Better Custom Markers", "1.7", "OPTIONAL", 1778420608, "AAAAAAAAA"),
        nf(203, 14947, 7469036, "Map Tweaks (Reticle And Roads)", "2.8", "OLD_VERSION", 1788800745, "XOtFiwFZe"),
        nf(203, 16877, 7469036, "Map Tweaks (Reticle And Roads)", "2.9", "MAIN", 1791226969, "KZqzaDzIv"),
    ],
    334: [
        nf(334, 9100, 7100001, "Clean Kills", "1.1", "MAIN", 1778478892, "BBBBBBBBB"),
    ],
    2406: [
        nf(2406, 14276, 7871586, "Healthbar Always On 2.00.00", "1", "ARCHIVED", 1788120720, "Aq02rzu9p"),
        nf(2406, 14695, 7871586, "Healthbar Always On 2.01.00", "2", "MAIN", 1789145280, "qrIkcUpZs"),
        nf(2406, 13814, 7620377, "DMM_Healthbar Always On-multi target from Caites", "4", "ARCHIVED", 1787313240, "mhw3QMqWU"),
    ],
}

MOD_NAMES = {
    452: "Better Inventory and Trade UI",
    203: "Map Tweaks",
    334: "Clean Kills",
    2406: "Healthbar always on",
}


class FakeNexus:
    def __init__(self, game="crimsondesert", files=None, mod_names=None):
        self.game = game
        self.files = FILES if files is None else files
        self.mod_names = MOD_NAMES if mod_names is None else mod_names
        self.requested: list[list[int]] = []

    def game_id(self) -> int:
        return 8969

    def mod_files(self, mod_ids):
        ids = sorted(set(mod_ids))
        self.requested.append(ids)
        return {m: list(self.files.get(m, [])) for m in ids}

    def mods(self, mod_ids):
        return {m: NexusMod(m, self.mod_names[m], "published") for m in set(mod_ids) if m in self.mod_names}
