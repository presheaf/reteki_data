import enum
from functools import total_ordering

import yaml
from config import (CORP_CARDBACK_BLEED, CORP_CARDBACK_NONBLEED,
                    RUNNER_CARDBACK_BLEED, RUNNER_CARDBACK_NONBLEED,
                    alts_yaml_path, bleed_img_dir, nonbleed_img_dir,
                    reboot_change_yaml_path)


# Purpose of this is to facilitate "if change[cardname] > ChangeLevel.DeckConstructionChange
@total_ordering
class ChangeLevel(enum.Enum):
    Unchanged = 1
    DeckConstructionChange = 2
    IngameChange = 3

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


with open(reboot_change_yaml_path) as f:
    _yaml_data = yaml.safe_load(f)

with open(alts_yaml_path) as f:
    _alt_yaml_data = yaml.safe_load(f)


multi_faced_cards: dict[str, tuple[str, ...]] = {
    "Jinteki Biotech: Life Imagined": (
        "Jinteki Biotech: Life Imagined",
        "The Brewery: Jinteki Biotech",
        "The Greenhouse: Jinteki Biotech",
        "The Tank: Jinteki Biotech",
    ),
    "SYNC: Everything, Everywhere": (
        "SYNC: Everything, Everywhere",
        "SYNC: Everything, Everywhere, Back side",
    ),
    "Molotov": ("Molotov", "Blaze"),
    "On the Trail": ("On the Trail", "Moment of Truth"),
    "Subsidized Processor": ("Subsidized Processor", "Borrowed Storage"),
    "Echo Memvaults: Reality Reimagined": (
        "Echo Memvaults: Reality Reimagined",
        "Echo Memvaults: Reality Reimagined Back"
    ),
    "Vulcan 1.0": ("Vulcan 1.0", "Mind Maze"),
    "Talent Scout": ("Talent Scout", "Red Carpet"),
    "Caterpillar": ("Caterpillar", "Monarch"),
    "Foxtrot": ("Foxtrot", "Blockade"),
    "Futureproofing": ("Futureproofing", "Epiph4ny"),
    "Hype": ("Hype", "Hope"),
    "The Horde: Defiant Disenfrancistos": (
        "The Horde: Defiant Disenfrancistos",
        "The Horde: Defiant Disenfrancistos Back"
    ),
    "Patent Acquisition": ("Patent Acquisition", "Injunction"),
    "Iris Capital: Trading Tomorrow": ("Iris Capital: Trading Tomorrow", "Consolidation"),
    "Project Genesis": ("Project Genesis", "Acheron", "Cocytus", "Phlegethon")
}


cardname_to_img_basename: dict[str, str] = {}

for code, data in _yaml_data.items():
    cardname = data["title"]
    if cardname in multi_faced_cards:
        front_face, *reverse_faces = multi_faced_cards[cardname]

        cardname_to_img_basename[front_face] = f"{code}_front.jpg"
        for face_idx, facename in enumerate(reverse_faces, start=1):
            cardname_to_img_basename[facename] = f"{code}_back_{face_idx}.jpg"

    else:
        cardname_to_img_basename[cardname] = f"{code}.jpg"

cardname_to_alts_basename = {
    cardname: basepath for cardname, basepath in _alt_yaml_data.items()
}

card_change_levels = {
    data["title"]: ChangeLevel.Unchanged
    if data["change"] is None
    else ChangeLevel.IngameChange
    if data["ingame_change"]
    else ChangeLevel.DeckConstructionChange
    for data in _yaml_data.values()
}
card_change_strings = {
    data["title"]: data["change"] if data["change"] is not None else "No change"
    for data in _yaml_data.values()
}


# used for data entry

_cardname_aliases = {
    ("jinteki biotech", "biotech"): "Jinteki Biotech: Life Imagined",
    ("sync",): "SYNC: Everything, Everywhere",
}

cardname_aliases = {
    s: cardname for tpl, cardname in _cardname_aliases.items() for s in tpl
}
