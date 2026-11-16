from __future__ import annotations

from typing import Final

CAVERN_SLOTS: Final = {"Head", "Hands", "Body", "Feet"}
PLANAR_SLOTS: Final = {"Planar Sphere", "Link Rope"}

CHECKPOINT_LEVELS: Final = (0, 3, 6, 9, 12, 15)
MAX_ENHANCEMENT_BY_RARITY: Final = {
    2: 6,
    3: 9,
    4: 12,
    5: 15,
}

# Reliquary Archiver exports values in display units. Grade-5 substats have
# three growth tiers; this project uses the middle tier as one Standard Roll.
GRADE5_HIGH_ROLL: Final = {
    "HP": 42.33755,
    "ATK": 21.168773,
    "DEF": 21.168773,
    "HP_": 4.32000026,
    "ATK_": 4.32000026,
    "DEF_": 5.4,
    "SPD": 2.6,
    "CRIT Rate_": 3.24000004,
    "CRIT DMG_": 6.48000008,
    "Effect Hit Rate_": 4.32000026,
    "Effect RES_": 4.32000026,
    "Break Effect_": 6.48000008,
}

GRADE5_MID_ROLL: Final = {
    "HP": 38.103795,
    "ATK": 19.051896,
    "DEF": 19.051896,
    "HP_": 3.8880002,
    "ATK_": 3.8880002,
    "DEF_": 4.86,
    "SPD": 2.3,
    "CRIT Rate_": 2.91600004,
    "CRIT DMG_": 5.83200008,
    "Effect Hit Rate_": 3.8880002,
    "Effect RES_": 3.8880002,
    "Break Effect_": 5.83200008,
}

# 5-star +15 main stat values from the same data family as Fribbels'
# relic_main_affixes.json, converted to display units where applicable.
GRADE5_MAIN_STAT_MAX: Final = {
    "Head": {"HP": 705.6},
    "Hands": {"ATK": 352.8},
    "Body": {
        "HP_": 43.2,
        "ATK_": 43.2,
        "DEF_": 54.0,
        "CRIT Rate_": 32.4,
        "CRIT DMG_": 64.8,
        "Outgoing Healing Boost": 34.5606,
        "Effect Hit Rate_": 43.2,
    },
    "Feet": {
        "HP_": 43.2,
        "ATK_": 43.2,
        "DEF_": 54.0,
        "SPD": 25.032,
    },
    "Planar Sphere": {
        "HP_": 43.2,
        "ATK_": 43.2,
        "DEF_": 54.0,
        "Physical DMG Boost": 38.8803015,
        "Fire DMG Boost": 38.8803015,
        "Ice DMG Boost": 38.8803015,
        "Lightning DMG Boost": 38.8803015,
        "Wind DMG Boost": 38.8803015,
        "Quantum DMG Boost": 38.8803015,
        "Imaginary DMG Boost": 38.8803015,
    },
    "Link Rope": {
        "Break Effect_": 64.8,
        "Energy Regeneration Rate": 19.4394015,
        "HP_": 43.2,
        "ATK_": 43.2,
        "DEF_": 54.0,
    },
}

STANDARD_MAIN_STAT_ROLLS: Final = GRADE5_MAIN_STAT_MAX["Body"]["ATK_"] / GRADE5_MID_ROLL["ATK_"]

NON_SUBSTAT_STANDARD_ROLL_VALUE: Final = {
    "Energy Regeneration Rate": GRADE5_MAIN_STAT_MAX["Link Rope"]["Energy Regeneration Rate"]
    / STANDARD_MAIN_STAT_ROLLS,
    "Outgoing Healing Boost": GRADE5_MAIN_STAT_MAX["Body"]["Outgoing Healing Boost"]
    / STANDARD_MAIN_STAT_ROLLS,
    "DMG Boost": GRADE5_MAIN_STAT_MAX["Planar Sphere"]["Fire DMG Boost"] / STANDARD_MAIN_STAT_ROLLS,
    "DOT DMG Boost": GRADE5_MAIN_STAT_MAX["Planar Sphere"]["Fire DMG Boost"] / STANDARD_MAIN_STAT_ROLLS,
    "Skill DMG Boost": GRADE5_MAIN_STAT_MAX["Planar Sphere"]["Fire DMG Boost"] / STANDARD_MAIN_STAT_ROLLS,
    "Ultimate DMG Boost": GRADE5_MAIN_STAT_MAX["Planar Sphere"]["Fire DMG Boost"] / STANDARD_MAIN_STAT_ROLLS,
    "Follow-up DMG Boost": GRADE5_MAIN_STAT_MAX["Planar Sphere"]["Fire DMG Boost"] / STANDARD_MAIN_STAT_ROLLS,
    "Physical DMG Boost": GRADE5_MAIN_STAT_MAX["Planar Sphere"]["Physical DMG Boost"]
    / STANDARD_MAIN_STAT_ROLLS,
    "Fire DMG Boost": GRADE5_MAIN_STAT_MAX["Planar Sphere"]["Fire DMG Boost"] / STANDARD_MAIN_STAT_ROLLS,
    "Ice DMG Boost": GRADE5_MAIN_STAT_MAX["Planar Sphere"]["Ice DMG Boost"] / STANDARD_MAIN_STAT_ROLLS,
    "Lightning DMG Boost": GRADE5_MAIN_STAT_MAX["Planar Sphere"]["Lightning DMG Boost"]
    / STANDARD_MAIN_STAT_ROLLS,
    "Wind DMG Boost": GRADE5_MAIN_STAT_MAX["Planar Sphere"]["Wind DMG Boost"] / STANDARD_MAIN_STAT_ROLLS,
    "Quantum DMG Boost": GRADE5_MAIN_STAT_MAX["Planar Sphere"]["Quantum DMG Boost"] / STANDARD_MAIN_STAT_ROLLS,
    "Imaginary DMG Boost": GRADE5_MAIN_STAT_MAX["Planar Sphere"]["Imaginary DMG Boost"]
    / STANDARD_MAIN_STAT_ROLLS,
    # User policy anchor: 20% DEF PEN is equivalent to 6 standard rolls.
    "DEF PEN": 20.0 / 6.0,
}

STANDARD_ROLL_VALUE: Final = GRADE5_MID_ROLL | NON_SUBSTAT_STANDARD_ROLL_VALUE

DISPLAY_STAT_ALIASES: Final = {
    "HP": "HP_",
    "ATK": "ATK_",
    "DEF": "DEF_",
    "CRIT Rate": "CRIT Rate_",
    "CRIT DMG": "CRIT DMG_",
    "Effect Hit Rate": "Effect Hit Rate_",
    "Effect RES": "Effect RES_",
    "Break Effect": "Break Effect_",
}

SUBSTAT_ALIASES: Final = {
    "CRIT Rate": "CRIT Rate_",
    "CRIT DMG": "CRIT DMG_",
    "Effect Hit Rate": "Effect Hit Rate_",
    "Effect RES": "Effect RES_",
    "Break Effect": "Break Effect_",
}


def normalize_substat_key(key: str) -> str:
    return SUBSTAT_ALIASES.get(key, key)


def normalize_main_stat(slot: str, stat: str) -> str:
    if slot == "Head" and stat == "HP":
        return "HP"
    if slot == "Hands" and stat == "ATK":
        return "ATK"
    return DISPLAY_STAT_ALIASES.get(stat, stat)


def is_planar_slot(slot: str) -> bool:
    return slot in PLANAR_SLOTS


def is_cavern_slot(slot: str) -> bool:
    return slot in CAVERN_SLOTS
