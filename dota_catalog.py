from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import requests

from app_paths import asset_cache_dir, asset_cache_path, resource_path
from dota_api import OpenDotaClient

ATTRIBUTE_LABELS = {
    "str": "Сила",
    "agi": "Ловкость",
    "int": "Интеллект",
    "all": "Универсальность",
    "universal": "Универсальность",
}

ATTRIBUTE_COLORS = {
    "str": (153, 59, 41),
    "agi": (54, 136, 88),
    "int": (57, 103, 173),
    "all": (154, 101, 202),
    "universal": (154, 101, 202),
}

HERO_ROWS: list[tuple[str, str, list[str]]] = [
    ("Abaddon", "all", ["Support", "Durable", "Dispel", "Save"]),
    ("Alchemist", "str", ["Carry", "Durable", "Farming", "Scaling"]),
    ("Ancient Apparition", "int", ["Support", "Nuker", "Anti-Heal", "Teamfight"]),
    ("Anti-Mage", "agi", ["Carry", "Escape", "Split Push", "Mana Burn"]),
    ("Arc Warden", "agi", ["Carry", "Pusher", "Scaling", "Split Push"]),
    ("Axe", "str", ["Offlane", "Initiator", "Durable", "Disabler"]),
    ("Bane", "all", ["Support", "Disabler", "Save", "Lane Control"]),
    ("Batrider", "all", ["Mid", "Initiator", "Disabler", "Pickoff"]),
    ("Beastmaster", "all", ["Offlane", "Pusher", "Initiator", "Aura"]),
    ("Bloodseeker", "agi", ["Carry", "Mid", "Chase", "Anti-Escape"]),
    ("Bounty Hunter", "agi", ["Roamer", "Support", "Invisibility", "Vision"]),
    ("Brewmaster", "all", ["Offlane", "Initiator", "Durable", "Teamfight"]),
    ("Bristleback", "str", ["Offlane", "Durable", "Carry", "Frontline"]),
    ("Broodmother", "all", ["Offlane", "Pusher", "Micro", "Tempo"]),
    ("Centaur Warrunner", "str", ["Offlane", "Initiator", "Durable", "Teamfight"]),
    ("Chaos Knight", "str", ["Carry", "Durable", "Illusions", "Burst"]),
    ("Chen", "all", ["Support", "Micro", "Pusher", "Heal"]),
    ("Clinkz", "agi", ["Carry", "Invisibility", "Pusher", "Pickoff"]),
    ("Clockwerk", "all", ["Support", "Offlane", "Initiator", "Vision"]),
    ("Crystal Maiden", "int", ["Support", "Nuker", "Disabler", "Mana"]),
    ("Dark Seer", "all", ["Offlane", "Teamfight", "Aura", "Initiator"]),
    ("Dark Willow", "all", ["Support", "Nuker", "Disabler", "Burst"]),
    ("Dawnbreaker", "all", ["Offlane", "Support", "Global", "Save"]),
    ("Dazzle", "all", ["Support", "Save", "Heal", "Lane Control"]),
    ("Death Prophet", "int", ["Mid", "Pusher", "Teamfight", "Sustain"]),
    ("Disruptor", "int", ["Support", "Disabler", "Teamfight", "Catch"]),
    ("Doom", "str", ["Offlane", "Disabler", "Durable", "Anti-Core"]),
    ("Dragon Knight", "str", ["Mid", "Offlane", "Durable", "Pusher"]),
    ("Drow Ranger", "agi", ["Carry", "Ranged", "Pusher", "Scaling"]),
    ("Earth Spirit", "str", ["Support", "Roamer", "Initiator", "Disabler"]),
    ("Earthshaker", "str", ["Support", "Initiator", "Teamfight", "Anti-Illusion"]),
    ("Elder Titan", "str", ["Support", "Offlane", "Aura", "Teamfight"]),
    ("Ember Spirit", "agi", ["Mid", "Carry", "Escape", "Magic Burst"]),
    ("Enchantress", "int", ["Support", "Offlane", "Heal", "Lane Control"]),
    ("Enigma", "all", ["Offlane", "Support", "Teamfight", "Pusher"]),
    ("Faceless Void", "agi", ["Carry", "Initiator", "Teamfight", "Scaling"]),
    ("Grimstroke", "int", ["Support", "Nuker", "Teamfight", "Combo"]),
    ("Gyrocopter", "agi", ["Carry", "Nuker", "AoE", "Scaling"]),
    ("Hoodwink", "agi", ["Support", "Nuker", "Escape", "Break"]),
    ("Huskar", "str", ["Mid", "Carry", "Durable", "Cheese"]),
    ("Invoker", "int", ["Mid", "Nuker", "Control", "Scaling"]),
    ("Io", "all", ["Support", "Save", "Global", "Heal"]),
    ("Jakiro", "int", ["Support", "Pusher", "Nuker", "Teamfight"]),
    ("Juggernaut", "agi", ["Carry", "Pusher", "Sustain", "Magic Immunity"]),
    ("Keeper of the Light", "int", ["Support", "Nuker", "Mana", "Wave Clear"]),
    ("Kez", "agi", ["Carry", "Mid", "Tempo", "Mobility"]),
    ("Kunkka", "str", ["Mid", "Offlane", "Teamfight", "Durable"]),
    ("Legion Commander", "str", ["Offlane", "Initiator", "Dispel", "Pickoff"]),
    ("Leshrac", "int", ["Mid", "Pusher", "Magic Damage", "Tempo"]),
    ("Lich", "int", ["Support", "Nuker", "Save", "Teamfight"]),
    ("Lifestealer", "str", ["Carry", "Durable", "Anti-Tank", "Magic Immunity"]),
    ("Lina", "int", ["Mid", "Carry", "Nuker", "Burst"]),
    ("Lion", "int", ["Support", "Disabler", "Burst", "Pickoff"]),
    ("Lone Druid", "all", ["Carry", "Pusher", "Micro", "Tempo"]),
    ("Luna", "agi", ["Carry", "Pusher", "AoE", "Scaling"]),
    ("Lycan", "all", ["Carry", "Pusher", "Zoo", "Tempo"]),
    ("Magnus", "all", ["Offlane", "Initiator", "Teamfight", "Buff"]),
    ("Marci", "all", ["Support", "Carry", "Initiator", "Burst"]),
    ("Mars", "str", ["Offlane", "Initiator", "Teamfight", "Frontline"]),
    ("Medusa", "agi", ["Carry", "Durable", "Illusions", "Scaling"]),
    ("Meepo", "agi", ["Mid", "Carry", "Micro", "Snowball"]),
    ("Mirana", "all", ["Support", "Roamer", "Disabler", "Global"]),
    ("Monkey King", "agi", ["Carry", "Mid", "Initiator", "Teamfight"]),
    ("Morphling", "agi", ["Carry", "Escape", "Burst", "Scaling"]),
    ("Muerta", "int", ["Carry", "Mid", "Magic Damage", "Scaling"]),
    ("Naga Siren", "agi", ["Carry", "Illusions", "Disabler", "Split Push"]),
    ("Nature's Prophet", "int", ["Pusher", "Global", "Split Push", "Tempo"]),
    ("Necrophos", "int", ["Mid", "Offlane", "Sustain", "Anti-Tank"]),
    ("Night Stalker", "str", ["Offlane", "Initiator", "Vision", "Silence"]),
    ("Nyx Assassin", "all", ["Support", "Roamer", "Disabler", "Invisibility"]),
    ("Ogre Magi", "str", ["Support", "Durable", "Buff", "Lane Control"]),
    ("Omniknight", "str", ["Support", "Save", "Heal", "Durable"]),
    ("Oracle", "int", ["Support", "Save", "Dispel", "Heal"]),
    ("Outworld Destroyer", "int", ["Mid", "Anti-Core", "Pure Damage", "Save"]),
    ("Pangolier", "all", ["Offlane", "Mid", "Initiator", "Teamfight"]),
    ("Phantom Assassin", "agi", ["Carry", "Burst", "Escape", "Scaling"]),
    ("Phantom Lancer", "agi", ["Carry", "Illusions", "Split Push", "Scaling"]),
    ("Phoenix", "all", ["Support", "Teamfight", "Heal", "AoE"]),
    ("Primal Beast", "str", ["Offlane", "Mid", "Initiator", "Durable"]),
    ("Puck", "int", ["Mid", "Escape", "Initiator", "Control"]),
    ("Pudge", "str", ["Support", "Offlane", "Pickoff", "Durable"]),
    ("Pugna", "int", ["Mid", "Support", "Pusher", "Save"]),
    ("Queen of Pain", "int", ["Mid", "Escape", "Burst", "Tempo"]),
    ("Razor", "agi", ["Carry", "Offlane", "Anti-Core", "Durable"]),
    ("Riki", "agi", ["Carry", "Invisibility", "Escape", "Silence"]),
    ("Ringmaster", "all", ["Support", "Control", "Save", "Teamfight"]),
    ("Rubick", "int", ["Support", "Disabler", "Nuker", "Counter-Initiate"]),
    ("Sand King", "all", ["Offlane", "Initiator", "Teamfight", "Anti-Illusion"]),
    ("Shadow Demon", "int", ["Support", "Save", "Disruption", "Anti-Illusion"]),
    ("Shadow Fiend", "agi", ["Mid", "Carry", "Nuker", "Scaling"]),
    ("Shadow Shaman", "int", ["Support", "Disabler", "Pusher", "Pickoff"]),
    ("Silencer", "int", ["Support", "Core", "Silence", "Teamfight"]),
    ("Skywrath Mage", "int", ["Support", "Nuker", "Silence", "Burst"]),
    ("Slardar", "str", ["Offlane", "Initiator", "Anti-Armor", "Durable"]),
    ("Slark", "agi", ["Carry", "Escape", "Pickoff", "Scaling"]),
    ("Snapfire", "all", ["Support", "Nuker", "Teamfight", "Save"]),
    ("Sniper", "agi", ["Carry", "Mid", "Ranged", "Siege"]),
    ("Spectre", "agi", ["Carry", "Global", "Durable", "Scaling"]),
    ("Spirit Breaker", "str", ["Support", "Offlane", "Global", "Initiator"]),
    ("Storm Spirit", "int", ["Mid", "Escape", "Pickoff", "Scaling"]),
    ("Sven", "str", ["Carry", "Disabler", "Anti-Illusion", "Burst"]),
    ("Techies", "all", ["Support", "Nuker", "Control", "Wave Clear"]),
    ("Templar Assassin", "agi", ["Mid", "Carry", "Burst", "Roshan"]),
    ("Terrorblade", "agi", ["Carry", "Illusions", "Pusher", "Scaling"]),
    ("Tidehunter", "str", ["Offlane", "Initiator", "Durable", "Teamfight"]),
    ("Timbersaw", "all", ["Offlane", "Mid", "Durable", "Magic Damage"]),
    ("Tinker", "int", ["Mid", "Nuker", "Split Push", "Scaling"]),
    ("Tiny", "str", ["Mid", "Carry", "Initiator", "Burst"]),
    ("Treant Protector", "str", ["Support", "Save", "Vision", "Teamfight"]),
    ("Troll Warlord", "agi", ["Carry", "Roshan", "Scaling", "Duel"]),
    ("Tusk", "str", ["Support", "Offlane", "Save", "Initiator"]),
    ("Underlord", "str", ["Offlane", "Aura", "Durable", "Global"]),
    ("Undying", "str", ["Support", "Offlane", "Lane Control", "Teamfight"]),
    ("Ursa", "agi", ["Carry", "Roshan", "Anti-Tank", "Burst"]),
    ("Vengeful Spirit", "all", ["Support", "Save", "Aura", "Initiator"]),
    ("Venomancer", "all", ["Support", "Offlane", "Damage Over Time", "Vision"]),
    ("Viper", "agi", ["Mid", "Offlane", "Break", "Lane Control"]),
    ("Visage", "all", ["Mid", "Offlane", "Micro", "Pusher"]),
    ("Void Spirit", "all", ["Mid", "Escape", "Burst", "Tempo"]),
    ("Warlock", "int", ["Support", "Teamfight", "Heal", "Push"]),
    ("Weaver", "agi", ["Carry", "Escape", "Invisibility", "Minus Armor"]),
    ("Windranger", "all", ["Mid", "Support", "Escape", "Pickoff"]),
    ("Winter Wyvern", "all", ["Support", "Save", "Teamfight", "Anti-Physical"]),
    ("Witch Doctor", "int", ["Support", "Heal", "Burst", "Teamfight"]),
    ("Wraith King", "str", ["Carry", "Durable", "Initiator", "Scaling"]),
    ("Zeus", "int", ["Mid", "Nuker", "Global", "Vision"]),
]

# A broad local item base. When internet is available, the Items tab refreshes it
# from OpenDota constants/items and keeps this list as fallback.
ITEM_GROUPS: dict[str, list[str]] = {
    "Consumables": [
        "Tango", "Healing Salve", "Clarity", "Enchanted Mango", "Blood Grenade", "Smoke of Deceit",
        "Town Portal Scroll", "Observer Ward", "Sentry Ward", "Dust of Appearance", "Bottle", "Aghanim's Shard",
    ],
    "Attributes": [
        "Iron Branch", "Gauntlets of Strength", "Slippers of Agility", "Mantle of Intelligence", "Circlet", "Crown",
        "Belt of Strength", "Band of Elvenskin", "Robe of the Magi", "Ogre Axe", "Blade of Alacrity",
        "Staff of Wizardry", "Diadem",
    ],
    "Basic": [
        "Quelling Blade", "Ring of Protection", "Orb of Venom", "Blight Stone", "Wind Lace", "Magic Stick",
        "Sage's Mask", "Ring of Regen", "Gloves of Haste", "Boots of Speed", "Cloak", "Talisman of Evasion",
        "Void Stone", "Gem of True Sight", "Morbid Mask", "Shadow Amulet", "Ghost Scepter", "Blink Dagger",
        "Hyperstone", "Demon Edge", "Eaglesong", "Reaver", "Mystic Staff", "Sacred Relic", "Energy Booster",
        "Vitality Booster", "Point Booster", "Platemail", "Claymore", "Mithril Hammer", "Javelin", "Quarterstaff",
        "Broadsword", "Blitz Knuckles", "Chainmail", "Helm of Iron Will", "Lifesteal Mask", "Cornucopia",
    ],
    "Early Game": [
        "Bracer", "Wraith Band", "Null Talisman", "Magic Wand", "Soul Ring", "Orb of Corrosion", "Falcon Blade",
        "Power Treads", "Phase Boots", "Arcane Boots", "Tranquil Boots", "Boots of Travel", "Hand of Midas",
        "Ring of Basilius", "Vladmir's Offering", "Mekansm", "Buckler", "Headdress", "Drum of Endurance",
        "Butterfly", "Mask of Madness", "Perseverance", "Oblivion Staff", "Witch Blade", "Pavise", "Solar Crest",
    ],
    "Core Damage": [
        "Armlet of Mordiggian", "Battle Fury", "Maelstrom", "Mjollnir", "Gleipnir", "Desolator", "Diffusal Blade",
        "Disperser", "Echo Sabre", "Harpoon", "Mage Slayer", "Orchid Malevolence", "Bloodthorn", "Parasma",
        "Dragon Lance", "Hurricane Pike", "Yasha", "Kaya", "Sange", "Manta Style", "Sange and Yasha",
        "Kaya and Sange", "Yasha and Kaya", "Daedalus", "Crystalys", "Silver Edge", "Monkey King Bar",
        "Divine Rapier", "Satanic", "Eye of Skadi", "Butterfly", "Abyssal Blade", "Skull Basher", "Moon Shard",
        "Butterfly", "Revenant's Brooch", "Ethereal Blade", "Radiance", "Nullifier", "Butterfly",
    ],
    "Defense and Utility": [
        "Black King Bar", "Linken's Sphere", "Lotus Orb", "Eul's Scepter of Divinity", "Wind Waker", "Force Staff",
        "Glimmer Cape", "Pipe of Insight", "Crimson Guard", "Guardian Greaves", "Holy Locket", "Aeon Disk",
        "Heaven's Halberd", "Blade Mail", "Heart of Tarrasque", "Eternal Shroud", "Shiva's Guard", "Bloodstone",
        "Octarine Core", "Refresher Orb", "Aghanim's Scepter", "Boots of Bearing", "Scythe of Vyse", "Dagon",
        "Veil of Discord", "Helm of the Dominator", "Helm of the Overlord", "Meteor Hammer", "Assault Cuirass",
        "Vanguard", "Hood of Defiance", "Butterfly", "Rod of Atos", "Urn of Shadows", "Spirit Vessel", "Drums of Slom",
    ],
    "Neutral Items": [
        "Arcane Ring", "Broom Handle", "Duelist Gloves", "Faded Broach", "Lance of Pursuit", "Occult Bracelet",
        "Pig Pole", "Royal Jelly", "Safety Bubble", "Seeds of Serenity", "Spark of Courage", "Trusty Shovel",
        "Vambrace", "Pupil's Gift", "Philosopher's Stone", "Dragon Scale", "Grove Bow", "Orb of Destruction",
        "Specialist's Array", "Eye of the Vizier", "Bullwhip", "Whisper of the Dread", "Vindicator's Axe",
        "Paladin Sword", "Titan Sliver", "Elven Tunic", "Cloak of Flames", "Ceremonial Robe", "Psychic Headband",
        "Dandelion Amulet", "Defiant Shell", "Craggy Coat", "Mind Breaker", "Ninja Gear", "Telescope", "Timeless Relic",
        "Trickster Cloak", "Stormcrafter", "Havoc Hammer", "Stygian Desolator", "Pirate Hat", "Apex", "Ballista",
        "Ex Machina", "Fallen Sky", "Giant's Ring", "Book of Shadows", "Arcanist's Armor", "Seer Stone",
        "Force Boots", "Mirror Shield", "Unwavering Condition", "Aviana's Feather", "Rattlecage", "Nemesis Curse",
    ],
}

HERO_COUNTERS: dict[str, dict[str, list[str]]] = {
    "Anti-Mage": {"heroes": ["Axe", "Legion Commander", "Doom", "Shadow Shaman", "Lion", "Faceless Void"], "items": ["Scythe of Vyse", "Orchid Malevolence", "Bloodthorn", "Abyssal Blade", "Heaven's Halberd"]},
    "Phantom Assassin": {"heroes": ["Axe", "Viper", "Legion Commander", "Bane", "Bloodseeker"], "items": ["Monkey King Bar", "Silver Edge", "Heaven's Halberd", "Ghost Scepter", "Scythe of Vyse"]},
    "Huskar": {"heroes": ["Ancient Apparition", "Viper", "Necrophos", "Axe", "Bloodseeker"], "items": ["Spirit Vessel", "Eye of Skadi", "Heaven's Halberd", "Silver Edge", "Shiva's Guard"]},
    "Medusa": {"heroes": ["Anti-Mage", "Nyx Assassin", "Lion", "Phantom Lancer", "Invoker"], "items": ["Diffusal Blade", "Disperser", "Scythe of Vyse", "Silver Edge", "Butterfly"]},
    "Phantom Lancer": {"heroes": ["Earthshaker", "Axe", "Sand King", "Leshrac", "Sven"], "items": ["Mjollnir", "Battle Fury", "Shiva's Guard", "Radiance", "Gleipnir"]},
    "Naga Siren": {"heroes": ["Earthshaker", "Axe", "Sand King", "Leshrac", "Sven"], "items": ["Mjollnir", "Battle Fury", "Shiva's Guard", "Radiance", "Crimson Guard"]},
    "Broodmother": {"heroes": ["Earthshaker", "Sand King", "Axe", "Legion Commander", "Sven"], "items": ["Crimson Guard", "Maelstrom", "Mjollnir", "Shiva's Guard", "Radiance"]},
    "Pudge": {"heroes": ["Lifestealer", "Ursa", "Slark", "Viper", "Oracle"], "items": ["Force Staff", "Linken's Sphere", "Black King Bar", "Ghost Scepter", "Lotus Orb"]},
    "Slark": {"heroes": ["Bloodseeker", "Disruptor", "Axe", "Legion Commander", "Bane"], "items": ["Force Staff", "Ghost Scepter", "Heaven's Halberd", "Scythe of Vyse", "Bloodthorn"]},
    "Tinker": {"heroes": ["Spectre", "Storm Spirit", "Clockwerk", "Nyx Assassin", "Zeus"], "items": ["Black King Bar", "Orchid Malevolence", "Bloodthorn", "Blink Dagger", "Scythe of Vyse"]},
    "Storm Spirit": {"heroes": ["Disruptor", "Lion", "Shadow Shaman", "Doom", "Puck"], "items": ["Orchid Malevolence", "Bloodthorn", "Scythe of Vyse", "Eul's Scepter of Divinity", "Black King Bar"]},
    "Faceless Void": {"heroes": ["Oracle", "Winter Wyvern", "Shadow Demon", "Vengeful Spirit", "Dazzle"], "items": ["Aeon Disk", "Ghost Scepter", "Force Staff", "Eul's Scepter of Divinity", "Linken's Sphere"]},
    "Drow Ranger": {"heroes": ["Spectre", "Phantom Assassin", "Storm Spirit", "Clockwerk", "Mars"], "items": ["Blink Dagger", "Shadow Blade", "Heaven's Halberd", "Blade Mail", "Black King Bar"]},
    "Sniper": {"heroes": ["Spectre", "Storm Spirit", "Clockwerk", "Spirit Breaker", "Mars"], "items": ["Blink Dagger", "Shadow Blade", "Blade Mail", "Heaven's Halberd", "Smoke of Deceit"]},
}

GENERIC_COUNTERS = {
    "Escape": (["Lion", "Shadow Shaman", "Disruptor", "Bane", "Doom"], ["Scythe of Vyse", "Orchid Malevolence", "Bloodthorn", "Eul's Scepter of Divinity"]),
    "Durable": (["Ancient Apparition", "Viper", "Necrophos", "Ursa", "Lifestealer"], ["Spirit Vessel", "Eye of Skadi", "Silver Edge", "Shiva's Guard"]),
    "Illusions": (["Earthshaker", "Axe", "Sand King", "Leshrac", "Sven"], ["Mjollnir", "Battle Fury", "Shiva's Guard", "Radiance"]),
    "Invisibility": (["Bounty Hunter", "Zeus", "Slardar", "Disruptor", "Night Stalker"], ["Sentry Ward", "Dust of Appearance", "Gem of True Sight", "Gleipnir"]),
    "Teamfight": (["Silencer", "Rubick", "Disruptor", "Vengeful Spirit", "Winter Wyvern"], ["Black King Bar", "Linken's Sphere", "Aeon Disk", "Lotus Orb"]),
    "Pusher": (["Tidehunter", "Sand King", "Keeper of the Light", "Leshrac", "Axe"], ["Crimson Guard", "Shiva's Guard", "Glyph timing", "Boots of Travel"]),
}

ROLE_REQUIREMENTS = {
    "Hard Carry": {"need": ["Carry", "Scaling", "Damage"], "weight": 18},
    "Mid Tempo": {"need": ["Mid", "Tempo", "Nuker", "Burst"], "weight": 14},
    "Offlane Frontline": {"need": ["Offlane", "Initiator", "Durable", "Frontline"], "weight": 16},
    "Support Control": {"need": ["Support", "Disabler", "Save", "Vision"], "weight": 14},
    "Teamfight/Push": {"need": ["Teamfight", "Pusher", "Aura", "Global"], "weight": 12},
}

ITEM_TAG_RULES: list[tuple[list[str], list[str]]] = [
    (["Black King Bar", "Linken", "Lotus", "Aeon", "BKB"], ["defense", "core_safe"]),
    (["Blink", "Force", "Hurricane", "Shadow Blade", "Silver Edge", "Boots", "Wind Waker"], ["mobility"]),
    (["Desolator", "Daedalus", "Rapier", "Crystalys", "Monkey King Bar", "Butterfly", "Bloodthorn", "Abyssal", "Manta", "Satanic", "Skadi"], ["damage", "carry"]),
    (["Maelstrom", "Mjollnir", "Battle Fury", "Radiance", "Midas", "Mask of Madness"], ["farming", "carry"]),
    (["Scythe", "Orchid", "Bloodthorn", "Eul", "Atos", "Gleipnir", "Abyssal", "Halberd"], ["control"]),
    (["Mekansm", "Greaves", "Pipe", "Crimson", "Vladmir", "Drum", "Bearing", "Assault", "Solar", "Pavise", "Holy Locket", "Glimmer"], ["support", "aura", "save"]),
    (["Ward", "Dust", "Smoke", "Gem"], ["vision", "support"]),
    (["Kaya", "Dagon", "Ethereal", "Veil", "Shiva", "Bloodstone", "Octarine", "Aghanim"], ["magic", "caster"]),
    (["Heart", "Vanguard", "Eternal Shroud", "Blade Mail", "Hood", "Crimson", "Pipe", "Shiva"], ["durability", "offlane"]),
    (["Diffusal", "Disperser", "Skadi", "Vessel", "Silver Edge"], ["counter"]),
]

ITEM_DESCRIPTIONS = {
    "Black King Bar": "Ключевой защитный предмет для коров: позволяет нажать урон/инициацию без мгновенного контроля.",
    "Blink Dagger": "Инициация и позиционка. Сильнее всего, когда команда готова нажать заклинания сразу после врыва.",
    "Force Staff": "Спасение от плохой позиции, Clock/Pudge/Slark и способ разорвать дистанцию.",
    "Glimmer Cape": "Дешевый save для саппорта: магическое сопротивление, сейв союзника и обман фокуса.",
    "Scythe of Vyse": "Поздний hard-control против мобильных коров и героев, которых нельзя выпускать из стана.",
    "Monkey King Bar": "Контрит уклонение и Butterfly, особенно против Phantom Assassin, Windranger и high-evasion сборок.",
    "Silver Edge": "Break против пассивок и способ начать драку из невидимости; ценен против Bristleback, Huskar, PA.",
    "Spirit Vessel": "Контрит лечение, высокий regen и героев вроде Huskar, Necrophos, Alchemist, Io-связок.",
    "Eye of Skadi": "Замедляет, режет лечение и дает плотность керри в длинных драках.",
    "Aghanim's Scepter": "Сильный апгрейд способностей; покупать, когда конкретный Aghanim меняет драку или темп карты.",
    "Aghanim's Shard": "Дешевый power spike после 15 минуты, если shard героя реально открывает драки или фарм.",
}

SLUG_RE = re.compile(r"[^a-z0-9]+")

STEAM_CDN = "https://cdn.cloudflare.steamstatic.com"
ASSET_TIMEOUT = 5
MIN_REAL_ICON_BYTES = 800

HERO_DOTA_SLUG_OVERRIDES = {
    "Anti-Mage": "antimage",
    "Clockwerk": "rattletrap",
    "Centaur Warrunner": "centaur",
    "Doom": "doom_bringer",
    "Io": "wisp",
    "Lifestealer": "life_stealer",
    "Magnus": "magnataur",
    "Nature's Prophet": "furion",
    "Necrophos": "necrolyte",
    "Outworld Destroyer": "obsidian_destroyer",
    "Queen of Pain": "queenofpain",
    "Shadow Fiend": "nevermore",
    "Timbersaw": "shredder",
    "Treant Protector": "treant",
    "Underlord": "abyssal_underlord",
    "Vengeful Spirit": "vengefulspirit",
    "Windranger": "windrunner",
    "Wraith King": "skeleton_king",
    "Zeus": "zuus",
}

ITEM_DOTA_SLUG_OVERRIDES = {
    "Aghanim's Scepter": "ultimate_scepter",
    "Aghanim's Shard": "aghanims_shard",
    "Blink Dagger": "blink",
    "Butterfly": "butterfly",
    "Boots of Speed": "boots",
    "Boots of Travel": "travel_boots",
    "Eul's Scepter of Divinity": "cyclone",
    "Gem of True Sight": "gem",
    "Hand of Midas": "hand_of_midas",
    "Linken's Sphere": "sphere",
    "Monkey King Bar": "monkey_king_bar",
    "Observer Ward": "ward_observer",
    "Sentry Ward": "ward_sentry",
    "Scythe of Vyse": "sheepstick",
    "Town Portal Scroll": "tpscroll",
}


def slugify(name: str) -> str:
    text = name.lower().replace("'", "")
    return SLUG_RE.sub("_", text).strip("_") or "unknown"


def normalize_attr(attr: str | None) -> str:
    value = (attr or "all").lower()
    if value in {"universal", "all"}:
        return "all"
    if value.startswith("str"):
        return "str"
    if value.startswith("agi"):
        return "agi"
    if value.startswith("int"):
        return "int"
    return value if value in ATTRIBUTE_LABELS else "all"


def attr_label(attr: str | None) -> str:
    return ATTRIBUTE_LABELS.get(normalize_attr(attr), "Универсальность")


def get_hero_catalog(client: OpenDotaClient | None = None) -> list[dict[str, Any]]:
    heroes = [
        {
            "name": name,
            "attr": normalize_attr(attr),
            "attr_ru": attr_label(attr),
            "roles": list(dict.fromkeys(roles)),
            "dota_slug": dota_slug_for_hero(name),
            "source": "offline",
        }
        for name, attr, roles in HERO_ROWS
    ]
    by_name = {h["name"].lower(): h for h in heroes}

    if client is not None:
        try:
            live = client.get_heroes()
        except Exception:
            live = {}
        for row in live.values():
            name = row.get("localized_name") or row.get("name") or ""
            if not name:
                continue
            # OpenDota names sometimes use npc_dota_hero_ prefix.
            name = _pretty_hero_name(name)
            attr = normalize_attr(row.get("primary_attr"))
            roles = row.get("roles") or []
            if not isinstance(roles, list):
                roles = []
            existing = by_name.get(name.lower())
            if existing:
                existing["attr"] = attr
                existing["attr_ru"] = attr_label(attr)
                if roles:
                    existing["roles"] = list(dict.fromkeys([*roles, *existing.get("roles", [])]))
                existing["dota_slug"] = str(row.get("name", "")).replace("npc_dota_hero_", "") or dota_slug_for_hero(name)
                existing["source"] = "OpenDota"
            else:
                heroes.append({
                    "name": name,
                    "attr": attr,
                    "attr_ru": attr_label(attr),
                    "roles": list(dict.fromkeys(roles or ["Hero"])),
                    "dota_slug": str(row.get("name", "")).replace("npc_dota_hero_", "") or dota_slug_for_hero(name),
                    "source": "OpenDota",
                })
    heroes.sort(key=lambda x: x["name"])
    return heroes


def _pretty_hero_name(value: str) -> str:
    value = value.replace("npc_dota_hero_", "").replace("_", " ").strip()
    special = {
        "antimage": "Anti-Mage",
        "nevermore": "Shadow Fiend",
        "furion": "Nature's Prophet",
        "obsidian destroyer": "Outworld Destroyer",
        "windrunner": "Windranger",
        "wisp": "Io",
        "skeleton king": "Wraith King",
        "centaur": "Centaur Warrunner",
        "shredder": "Timbersaw",
        "abyssal underlord": "Underlord",
    }
    return special.get(value.lower(), value.title())


def get_item_catalog(client: OpenDotaClient | None = None) -> list[dict[str, Any]]:
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for category, names in ITEM_GROUPS.items():
        for name in names:
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            items.append(_make_item(name, category, "offline"))

    if client is not None:
        try:
            data = client._get("constants/items", max_age=24 * 3600)  # OpenDota current constants.
        except Exception:
            data = {}
        if isinstance(data, dict):
            for raw_name, row in data.items():
                if not isinstance(row, dict):
                    continue
                name = row.get("dname") or row.get("localized_name") or _pretty_item_name(raw_name)
                if not name or name.lower() in seen:
                    continue
                cost = row.get("cost")
                category = _category_from_cost_and_row(cost, row)
                item = _make_item(str(name), category, "OpenDota")
                item["dota_slug"] = str(raw_name).replace("item_", "")
                item["cost"] = cost if isinstance(cost, int) else row.get("cost", "—")
                hint = row.get("hint") or row.get("notes")
                if isinstance(hint, list):
                    item["description"] = " ".join(str(x) for x in hint[:2]) or item["description"]
                elif isinstance(hint, str) and hint.strip():
                    item["description"] = hint.strip()
                items.append(item)
                seen.add(str(name).lower())
    items.sort(key=lambda x: (x.get("category", ""), x.get("name", "")))
    return items


def _pretty_item_name(value: str) -> str:
    value = str(value).replace("item_", "").replace("_", " ")
    return value.title().replace(" Of ", " of ").replace(" And ", " and ")


def _category_from_cost_and_row(cost: Any, row: dict[str, Any]) -> str:
    if row.get("neutral_tier") or row.get("neutral"):
        return "Neutral Items"
    try:
        c = int(cost)
    except Exception:
        return "Other"
    if c <= 120:
        return "Consumables"
    if c <= 700:
        return "Basic"
    if c <= 1800:
        return "Early Game"
    if c <= 4200:
        return "Core Damage"
    return "Defense and Utility"


def _item_tags(name: str, category: str) -> list[str]:
    tags = [category.lower().replace(" ", "_")]
    if category == "Neutral Items":
        tags.extend(["neutral", "neutral_slot"])
    for needles, found_tags in ITEM_TAG_RULES:
        if any(n.lower() in name.lower() for n in needles):
            tags.extend(found_tags)
    return list(dict.fromkeys(tags))


def _make_item(name: str, category: str, source: str) -> dict[str, Any]:
    tags = _item_tags(name, category)
    return {
        "name": name,
        "category": category,
        "tags": tags,
        "cost": "—",
        "description": ITEM_DESCRIPTIONS.get(name, _generic_item_description(name, tags, category)),
        "best_for": _best_for(tags),
        "dota_slug": dota_slug_for_item(name),
        "source": source,
    }


def _generic_item_description(name: str, tags: list[str], category: str) -> str:
    bits: list[str] = []
    if "damage" in tags or "carry" in tags:
        bits.append("усиливает урон/темп кора")
    if "defense" in tags or "core_safe" in tags:
        bits.append("помогает пережить контроль и фокус")
    if "support" in tags or "save" in tags:
        bits.append("дает сейв, ауру или командную пользу")
    if "vision" in tags:
        bits.append("открывает карту и наказывает невидимость")
    if "mobility" in tags:
        bits.append("улучшает позиционку и старт драки")
    if "control" in tags:
        bits.append("добавляет контроль против мобильных героев")
    if category == "Neutral Items":
        bits.append("кладется в отдельный нейтральный слот и не занимает один из 6 основных слотов")
    if not bits:
        bits.append("закрывает базовую потребность героя в этой стадии игры")
    return f"{name}: предмет категории {category}; " + ", ".join(bits) + "."


def _best_for(tags: list[str]) -> str:
    roles: list[str] = []
    if "carry" in tags or "damage" in tags or "farming" in tags:
        roles.extend(["Carry", "Mid damage"])
    if "support" in tags or "save" in tags or "vision" in tags:
        roles.extend(["Hard Support", "Soft Support"])
    if "offlane" in tags or "aura" in tags or "durability" in tags:
        roles.extend(["Offlane", "Frontline"])
    if "caster" in tags or "magic" in tags or "control" in tags:
        roles.extend(["Mid caster", "Utility"])
    if "neutral" in tags:
        roles.append("нейтральный слот, выбирай по текущей задаче")
    if not roles:
        roles.append("ситуационные герои")
    return ", ".join(dict.fromkeys(roles))


def find_hero(heroes: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    key = name.strip().lower()
    for hero in heroes:
        if hero.get("name", "").lower() == key:
            return hero
    return None


def find_item(items: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    key = name.strip().lower()
    for item in items:
        if item.get("name", "").lower() == key:
            return item
    return None


def hero_counters(hero: dict[str, Any]) -> tuple[list[str], list[str]]:
    name = hero.get("name", "")
    roles = set(hero.get("roles") or [])
    counter_heroes: list[str] = []
    counter_items: list[str] = []
    explicit = HERO_COUNTERS.get(name)
    if explicit:
        counter_heroes.extend(explicit.get("heroes", []))
        counter_items.extend(explicit.get("items", []))
    for role in roles:
        if role in GENERIC_COUNTERS:
            h, i = GENERIC_COUNTERS[role]
            counter_heroes.extend(h)
            counter_items.extend(i)
    if not counter_heroes:
        counter_heroes = ["Doom", "Lion", "Shadow Shaman", "Disruptor", "Bane"]
    if not counter_items:
        counter_items = ["Black King Bar", "Scythe of Vyse", "Force Staff", "Linken's Sphere", "Lotus Orb"]
    return list(dict.fromkeys(counter_heroes))[:8], list(dict.fromkeys(counter_items))[:8]


def hero_details_markdown(hero: dict[str, Any]) -> str:
    counters, counter_items = hero_counters(hero)
    roles = hero.get("roles") or []
    attr = hero.get("attr_ru") or attr_label(hero.get("attr"))
    source = hero.get("source", "offline")
    plan = _hero_game_plan(roles)
    return (
        f"## {hero.get('name', 'Hero')}\n\n"
        f"**Тип:** {attr}  \n"
        f"**Роли/стиль:** {', '.join(roles) or '—'}  \n"
        f"**Источник:** {source}\n\n"
        f"**Как играть:** {plan}\n\n"
        f"**Контрпики героя:** {', '.join(counters)}.\n\n"
        f"**Предметы против него:** {', '.join(counter_items)}.\n\n"
        "**Мини-чеклист:** не пикай героя в вакуум — проверь, есть ли у команды stun, frontline, wave clear и способ забрать Roshan/башни."
    )


def _hero_game_plan(roles: list[str]) -> str:
    r = set(roles)
    lines: list[str] = []
    if "Carry" in r:
        lines.append("закрывай линию с минимумом смертей, держи фарм-паттерн lane → jungle → lane и выходи в драки на power spike предметов")
    if "Mid" in r:
        lines.append("играй от рун, темпа и смещений; каждая удачная руна должна превращаться в kill, tower damage или защиту кора")
    if "Offlane" in r:
        lines.append("ломай safe farm врага, заставляй саппортов реагировать и начинай драки, когда core готов нажать урон")
    if "Support" in r:
        lines.append("контролируй вижен, смоки и save; твоя задача — не только поставить ward, а открыть объект под команду")
    if "Pusher" in r or "Split Push" in r:
        lines.append("играй от давления линий: сначала запушь линию, потом заходи в лес/объект")
    if not lines:
        lines.append("выбирай понятный power spike, играй от сильной стороны героя и не дерись без цели")
    return "; ".join(lines) + "."


def item_details_markdown(item: dict[str, Any]) -> str:
    tags = ", ".join(item.get("tags") or [])
    neutral_note = ""
    if item.get("category") == "Neutral Items":
        neutral_note = (
            "\n\n**Нейтральный слот:** этот предмет кладется в отдельный нейтральный слот; "
            "обычно выбирай один лучший под текущую стадию, героя и матчап."
        )
    return (
        f"## {item.get('name', 'Item')}\n\n"
        f"**Категория:** {item.get('category', '—')}  \n"
        f"**Цена:** {item.get('cost', '—')}  \n"
        f"**Лучше всего на:** {item.get('best_for', '—')}  \n"
        f"**Теги:** {tags}\n\n"
        f"{item.get('description', '')}"
        f"{neutral_note}\n\n"
        "**Когда покупать:** когда предмет закрывает конкретную проблему: контроль, выживаемость, урон, темп фарма, save или вижен."
    )


def draft_analysis_markdown(allies: list[str], enemies: list[str], heroes: list[dict[str, Any]]) -> str:
    score = 50
    notes: list[str] = []
    ally_rows = [find_hero(heroes, x) for x in allies if x]
    enemy_rows = [find_hero(heroes, x) for x in enemies if x]
    ally_rows = [x for x in ally_rows if x]
    enemy_rows = [x for x in enemy_rows if x]
    ally_roles = [role for h in ally_rows for role in (h.get("roles") or [])]
    enemy_roles = [role for h in enemy_rows for role in (h.get("roles") or [])]

    for block, cfg in ROLE_REQUIREMENTS.items():
        count = sum(1 for role in ally_roles if role in cfg["need"])
        if count:
            score += min(cfg["weight"], 5 + count * 4)
            notes.append(f"✅ Есть блок {block}: {count} совпадений.")
        else:
            score -= cfg["weight"] // 2
            notes.append(f"⚠️ Не хватает блока {block}.")

    # Counters: if ally hero is listed as a counter to enemy hero, add points.
    counter_hits: list[str] = []
    danger_hits: list[str] = []
    for enemy in enemy_rows:
        counters, _ = hero_counters(enemy)
        for ally in ally_rows:
            if ally.get("name") in counters:
                counter_hits.append(f"{ally['name']} хорошо отвечает на {enemy['name']}")
                score += 4
    for ally in ally_rows:
        counters, _ = hero_counters(ally)
        for enemy in enemy_rows:
            if enemy.get("name") in counters:
                danger_hits.append(f"{enemy['name']} контрит {ally['name']}")
                score -= 5

    if "Illusions" in enemy_roles and not any(r in ally_roles for r in ["Anti-Illusion", "AoE", "Wave Clear"]):
        score -= 12
        notes.append("⚠️ У врага иллюзии, а у тебя мало AoE/anti-illusion.")
    if any(r in enemy_roles for r in ["Invisibility", "Escape"]) and not any(r in ally_roles for r in ["Vision", "Disabler", "Silence", "Catch"]):
        score -= 8
        notes.append("⚠️ Враги мобильные/инвизные — нужен catch, silence или больше вижена.")
    if any(r in ally_roles for r in ["Pusher", "Split Push"]) and any(r in ally_roles for r in ["Teamfight", "Initiator"]):
        score += 8
        notes.append("✅ Драфт умеет и давить линии, и начинать драки.")

    score = max(0, min(100, score))
    tier = "сильный" if score >= 75 else "нормальный" if score >= 55 else "рискованный"
    lines = [f"## Оценка драфта: {score}/100 — {tier}", ""]
    if allies:
        lines.append("**Твой пик:** " + ", ".join(allies))
    if enemies:
        lines.append("**Вражеский пик:** " + ", ".join(enemies))
    lines.append("")
    lines.extend(notes[:10])
    for hit in counter_hits[:5]:
        lines.append(f"✅ {hit}.")
    for hit in danger_hits[:5]:
        lines.append(f"❌ {hit}.")
    if len(allies) < 5 or len(enemies) < 5:
        lines.append("\nДобавь 5 на 5 для более точной оценки.")
    lines.append("\n**Совет:** хороший драфт не обязан иметь 5 контрпиков; важнее закрыть stun, tower damage, Roshan/объекты, wave clear и save.")
    return "\n".join(lines)


def item_build_analysis_markdown(hero_name: str, item_names: list[str], heroes: list[dict[str, Any]], items: list[dict[str, Any]]) -> str:
    hero = find_hero(heroes, hero_name) if hero_name else None
    selected = [find_item(items, x) for x in item_names]
    selected = [x for x in selected if x]
    if not hero:
        return "## Выбери героя\n\nСначала выбери героя, потом добавь 3-6 предметов."
    if not selected:
        return f"## {hero['name']}\n\nДобавь предметы в билд, чтобы получить оценку."

    roles = set(hero.get("roles") or [])
    score = 45
    notes: list[str] = []
    tags = [tag for item in selected for tag in (item.get("tags") or [])]
    tag_set = set(tags)

    def has_any(*need: str) -> bool:
        return any(n in tag_set for n in need)

    if "Carry" in roles:
        if has_any("farming", "damage", "carry"):
            score += 20; notes.append("✅ Есть урон/фарм под core-роль.")
        else:
            score -= 15; notes.append("⚠️ Керри без фарм/урон-предмета часто не успевает к timing.")
        if has_any("defense", "core_safe"):
            score += 12; notes.append("✅ Есть защита для входа в драки.")
        else:
            notes.append("⚠️ Подумай о BKB/Linken/Aeon/Satanic, если враг контролит.")
    if "Mid" in roles:
        if has_any("mobility", "magic", "control", "damage"):
            score += 18; notes.append("✅ Предметы дают темп мидеру: kill threat или мобильность.")
        else:
            score -= 10; notes.append("⚠️ Мидеру обычно нужен tempo item: mobility, burst или control.")
    if "Support" in roles:
        if has_any("support", "save", "vision", "aura"):
            score += 20; notes.append("✅ Есть предметы для save/vision/team utility.")
        else:
            score -= 12; notes.append("⚠️ Саппорт без save/vision предметов редко влияет после лейнинга.")
    if "Offlane" in roles:
        if has_any("durability", "aura", "mobility", "control"):
            score += 18; notes.append("✅ Оффлейн получает frontline/инициацию/ауру.")
        else:
            score -= 10; notes.append("⚠️ Оффлейнеру нужен способ начинать драку или пережить первый фокус.")

    neutral_count = sum(1 for item in selected if item.get("category") == "Neutral Items")
    main_count = len(selected) - neutral_count
    if main_count > 6:
        score -= (main_count - 6) * 3
        notes.append("⚠️ В Dota 6 основных слотов: лишние основные предметы оценивай как backpack/late swap.")
    if neutral_count == 1:
        score += 4
        notes.append("✅ Учтен отдельный нейтральный слот: он не занимает один из 6 основных слотов.")
    elif neutral_count > 1:
        score -= (neutral_count - 1) * 4
        notes.append("⚠️ Одновременно активен только один нейтральный предмет: остальные должны быть заменами под ситуацию.")
    if sum(1 for tag in tags if tag == "farming") >= 3:
        score -= 8
        notes.append("⚠️ Слишком много фарм-предметов: можно опоздать на драки.")
    if "vision" in tag_set and "Carry" in roles and len(selected) >= 4:
        notes.append("ℹ️ Вижен полезен, но на core лучше покупать его ситуативно, не вместо ключевого timing.")

    missing: list[str] = []
    if not has_any("defense", "core_safe") and ("Carry" in roles or "Mid" in roles):
        missing.append("Black King Bar / Linken's Sphere / Satanic")
    if not has_any("mobility") and ("Initiator" in roles or "Offlane" in roles or "Support" in roles):
        missing.append("Blink Dagger / Force Staff / Boots of Bearing")
    if not has_any("control") and any(r in roles for r in ["Support", "Mid", "Offlane"]):
        missing.append("Scythe of Vyse / Eul / Rod of Atos / Orchid")
    if not has_any("save", "aura", "vision") and "Support" in roles:
        missing.append("Glimmer Cape / Force Staff / Sentry + Smoke / Lotus Orb")

    score = max(0, min(100, score))
    tier = "хороший" if score >= 75 else "играбельный" if score >= 55 else "слабый"
    lines = [f"## Билд на {hero['name']}: {score}/100 — {tier}", ""]
    lines.append("**Предметы:** " + ", ".join(item.get("name", "") for item in selected))
    if neutral_count:
        lines.append(f"**Нейтральные:** {neutral_count} шт. | Основные слоты: {main_count}/6")
    lines.append("")
    lines.extend(notes[:10])
    if missing:
        lines.append("\n**Что лучше добавить:** " + "; ".join(dict.fromkeys(missing)) + ".")
    lines.append("\n**Почему так:** предмет должен отвечать на конкретную проблему матча — урон, контроль, выживание, save, вижен или tempo. Если предмет не решает проблему, он задерживает твой timing.")
    return "\n".join(lines)




def dota_slug_for_hero(hero_name: str) -> str:
    if hero_name in HERO_DOTA_SLUG_OVERRIDES:
        return HERO_DOTA_SLUG_OVERRIDES[hero_name]
    return slugify(hero_name).replace("_", "_")


def dota_slug_for_item(item_name: str) -> str:
    if item_name in ITEM_DOTA_SLUG_OVERRIDES:
        return ITEM_DOTA_SLUG_OVERRIDES[item_name]
    return slugify(item_name)


def _asset_marker(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".real")


def _asset_is_placeholder(path: Path) -> bool:
    """Return True for bundled/generated fallback art.

    Real downloaded art writes a small .real marker next to the png, so future
    refreshes do not keep overwriting already-good assets.
    """
    try:
        if not path.exists():
            return True
        if _asset_marker(path).exists() and path.stat().st_size >= MIN_REAL_ICON_BYTES:
            return False
        return True
    except OSError:
        return True


def _download_binary(session: requests.Session, url: str, target: Path) -> bool:
    try:
        response = session.get(url, timeout=ASSET_TIMEOUT, headers={"User-Agent": "DotaCoachAI/0.9"})
        if not response.ok or not response.content or len(response.content) < MIN_REAL_ICON_BYTES:
            return False
        content_type = response.headers.get("content-type", "")
        if "image" not in content_type and not response.content.startswith((b"\x89PNG", b"\xff\xd8")):
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        try:
            _asset_marker(target).write_text(url, encoding="utf-8")
        except OSError:
            pass
        return True
    except Exception:
        return False


def download_catalog_assets(heroes: list[dict[str, Any]], items: list[dict[str, Any]], client: OpenDotaClient | None = None) -> dict[str, int]:
    """Download real Dota hero/item portraits into ui/assets/catalog.

    The app ships with offline placeholder art, but when internet is available it
    replaces placeholders with the same Steam CDN/OpenDota images that community
    sites commonly use. It is safe to call repeatedly: existing real icons are
    left untouched.
    """
    stats = {"hero_downloaded": 0, "item_downloaded": 0, "hero_total": len(heroes), "item_total": len(items)}
    # Download to writable per-user cache. In a packaged .exe the bundled
    # resource folder is read-only, so never overwrite files inside the app.
    heroes_dir = asset_cache_dir("heroes")
    items_dir = asset_cache_dir("items")
    session = requests.Session()

    hero_urls: dict[str, list[str]] = {}
    if client is not None:
        try:
            for row in client.get_public_hero_stats():
                name = row.get("localized_name") or row.get("dname") or row.get("name") or ""
                if not name:
                    continue
                display = _pretty_hero_name(str(name))
                urls: list[str] = []
                for key in ("img", "icon"):
                    path = row.get(key)
                    if isinstance(path, str) and path.startswith("/"):
                        urls.append(STEAM_CDN + path)
                if urls:
                    hero_urls[display] = urls
        except Exception:
            pass

    if not hero_urls:
        # Avoid hundreds of CDN timeout attempts when the machine is offline or OpenDota is unreachable.
        hero_iterable: list[dict[str, Any]] = []
    else:
        hero_iterable = heroes

    for hero in hero_iterable:
        name = str(hero.get("name") or "").strip()
        if not name:
            continue
        target = heroes_dir / f"{slugify(name)}.png"
        if not _asset_is_placeholder(target):
            continue
        urls = list(hero_urls.get(name) or [])
        dota_slug = str(hero.get("dota_slug") or dota_slug_for_hero(name))
        urls.extend([
            f"{STEAM_CDN}/apps/dota2/images/dota_react/heroes/{dota_slug}.png",
            f"{STEAM_CDN}/apps/dota2/images/heroes/{dota_slug}_full.png",
            f"{STEAM_CDN}/apps/dota2/images/heroes/{dota_slug}_icon.png",
        ])
        for url in dict.fromkeys(urls):
            if _download_binary(session, url, target):
                stats["hero_downloaded"] += 1
                break

    item_urls: dict[str, list[str]] = {}
    if client is not None:
        try:
            raw_items = client._get("constants/items", max_age=24 * 3600)
        except Exception:
            raw_items = {}
        if isinstance(raw_items, dict):
            for raw_name, row in raw_items.items():
                if not isinstance(row, dict):
                    continue
                name = row.get("dname") or row.get("localized_name") or _pretty_item_name(raw_name)
                if not name:
                    continue
                urls: list[str] = []
                path = row.get("img")
                if isinstance(path, str) and path.startswith("/"):
                    urls.append(STEAM_CDN + path)
                slug = str(raw_name).replace("item_", "")
                urls.extend([
                    f"{STEAM_CDN}/apps/dota2/images/dota_react/items/{slug}.png",
                    f"{STEAM_CDN}/apps/dota2/images/items/{slug}_lg.png",
                ])
                item_urls[str(name)] = urls

    if not item_urls:
        item_iterable: list[dict[str, Any]] = []
    else:
        item_iterable = items

    for item in item_iterable:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        target = items_dir / f"{slugify(name)}.png"
        if not _asset_is_placeholder(target):
            continue
        slug = str(item.get("dota_slug") or dota_slug_for_item(name))
        urls = list(item_urls.get(name) or [])
        urls.extend([
            f"{STEAM_CDN}/apps/dota2/images/dota_react/items/{slug}.png",
            f"{STEAM_CDN}/apps/dota2/images/items/{slug}_lg.png",
        ])
        for url in dict.fromkeys(urls):
            if _download_binary(session, url, target):
                stats["item_downloaded"] += 1
                break
    return stats

def hero_icon_path(hero_name: str) -> Path:
    slug = slugify(hero_name)
    cached = asset_cache_path("heroes", f"{slug}.png")
    if cached.exists() and cached.stat().st_size > 800:
        return cached
    path = resource_path("ui", "assets", "catalog", "heroes", f"{slug}.png")
    if path.exists():
        return path
    fallback = resource_path("ui", "assets", "dota_coach_icon.png")
    return fallback


def item_icon_path(item_name: str) -> Path:
    slug = slugify(item_name)
    cached = asset_cache_path("items", f"{slug}.png")
    if cached.exists() and cached.stat().st_size > 800:
        return cached
    path = resource_path("ui", "assets", "catalog", "items", f"{slug}.png")
    if path.exists():
        return path
    fallback = resource_path("ui", "assets", "dota_coach_icon.png")
    return fallback


def source_summary(heroes: list[dict[str, Any]], items: list[dict[str, Any]]) -> str:
    h_live = sum(1 for x in heroes if x.get("source") == "OpenDota")
    i_live = sum(1 for x in items if x.get("source") == "OpenDota")
    return f"Герои: {len(heroes)} ({h_live} OpenDota). Предметы: {len(items)} ({i_live} OpenDota)."
