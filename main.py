import base64, os, shutil, struct, sys, tkinter as tk
from tkinter import ttk, filedialog, messagebox

from mhw_data import (
    DECORATION_NAMES,
    ITEM_NAMES,
    ITEM_RARITIES,
    ITEM_TYPES,
    VANILLA_ITEM_B64,
    VANILLA_SHOP_B64,
)


def resource_path(filename):
    """Return the correct path for bundled PyInstaller resources."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


# ---------------------------------------------------------------------------
# Application / binary format constants
# ---------------------------------------------------------------------------

APP_TITLE = 'MHW Item & Shop Editor'
ITEM_RECORD_SIZE=32
ITEM_HEADER_SIZE=42
SELL_OFFSET=24
BUY_OFFSET=28
SHOP_HEADER_SIZE=24
SHOP_RECORD_SIZE=14
MAX_SHOP_ITEMS=255

# Item names are populated by the optional build helper. Unknown IDs remain visible.
# Final embedded MHW/Iceborne item-ID database.
# Generated from the supplied Item-IDs.md; no internet connection is required.
# Unavailable/unknown entries, account/furniture entries, IDs 114-136, and IDs 172-204
# are omitted, except IDs 174-178 and 180 as explicitly retained.

# ---------------------------------------------------------------------------
# Item database and shop safety
# ---------------------------------------------------------------------------

NORMAL_ITEM_NAMES = dict(ITEM_NAMES)
SHOP_NAMES=dict(NORMAL_ITEM_NAMES)
SHOP_NAMES.update(DECORATION_NAMES)

# Conservative list. The editor never adds these automatically.
NON_SHOP_IDS=set(range(114,137)) | ({i for i in range(172,205) if i not in {174,175,176,177,178,180}}) | {956,957,999,1004,1005,1022,1023,1024,1025}
UNSAFE_IDS=set(NON_SHOP_IDS)
KNOWN_IDS=set(NORMAL_ITEM_NAMES) - NON_SHOP_IDS
SHOP_KNOWN_IDS=set(SHOP_NAMES) - NON_SHOP_IDS
MAX_DISPLAY_PRICE=0xFFFFFFFF//2

# ---------------------------------------------------------------------------
# Shop preset definitions
# ---------------------------------------------------------------------------

# Self-contained shop presets. Material presets use the known item database only.
# MR groups are split into three smaller progression presets to stay below the 255-item shop limit.
EVENT_TICKET_IDS={i for i,n in ITEM_NAMES.items() if ('Ticket' in n or 'Coin' in n or 'Blueprint' in n or n in {'Unity Symbol','S.T.A.R.S. Badge','Azure Era Seal','Large Azure Era Gem'})}
GUIDING_LANDS_IDS={i for i,n in ITEM_NAMES.items() if 997 <= i <= 1174 or 1258 <= i <= 1273}
CONSUMABLE_IDS={i for i in KNOWN_IDS if i <= 113 or 137 <= i <= 180}
# Base-game monster/general material blocks.
# Material presets grouped by source type/rank rather than quest stars.
# Small-monster materials are separate LR / HR / MR presets.
# Large-monster materials are LR+HR together, while MR is split into two
# monster-complete chunks so one monster is never cut between MR preset 1 and 2.

def _ids_exact_names(names):
    wanted={n.lower() for n in names}
    return {i for i,n in NORMAL_ITEM_NAMES.items() if n.lower() in wanted}

def _ids_name_contains(*needles):
    return {i for i,n in NORMAL_ITEM_NAMES.items()
            if any(x.lower() in n.lower() for x in needles)}

# Small monsters / endemic hostile creatures.
_SMALL_LR_NAMES={
    'Mosswine Hide','Warm Pelt','Vespoid Shell','Vespoid Wing','Hornetaur Shell','Hornetaur Wing',
    'Hornetaur Head','Gajau Skin','Gajau Whisker','Wingdrake Hide','Barnos Hide+','Barnos Talon',
    'Kestodon Shell','Kestodon Scalp','Jagras Scale','Jagras Hide','Shamos Scale','Shamos Hide',
    'Girros Scale','Girros Hide','Girros Fang'
}
_SMALL_HR_NAMES={
    'High-quality Pelt','Vespoid Carapace','Vespoid Innerwing','Hornetaur Carapace','Hornetaur Innerwing',
    'Gajau Scale','Grand Gajau Whisker','Wingdrake Hide+','Kestodon Carapace','Gastodon Carapace',
    'Gastodon Horn','Jagras Scale+','Jagras Hide+','Shamos Scale+','Shamos Hide+',
    'Girros Scale+','Girros Hide+'
}
_SMALL_MR_NAMES={
    'Prized Pelt','Vespoid Razorwing','Hornetaur Razorwing','Gajau Thickhide','Steel Gajau Whisker',
    'Wingdrake Finehide','Barnos Hardclaw','Kestodon Husk','Gastodon Husk','Jagras Shard',
    'Shamos Shard','Girros Shard','Wulg Thickfur','Cortos Hardclaw'
}
SMALL_MONSTER_LR_IDS=_ids_exact_names(_SMALL_LR_NAMES)
SMALL_MONSTER_HR_IDS=_ids_exact_names(_SMALL_HR_NAMES)
SMALL_MONSTER_MR_IDS=_ids_exact_names(_SMALL_MR_NAMES)

# Large-monster families. Name matching is used deliberately so all parts from the same monster
# remain together when building the MR chunks.
_LARGE_LRHR_MONSTERS=[
    'Great Jagras','Kulu-Ya-Ku','Pukei-Pukei','Barroth','Jyuratodus','Tobi-Kadachi','Anjanath',
    'Tzitzi-Ya-Ku','Paolumu','Great Girros','Radobaan','Rathian','Pink Rathian','Legiana',
    'Odogaron','Rathalos','Azure Rathalos','Diablos','Black Diablos','Dodogama','Lavasioth',
    'Uragaan','Bazelgeuse','Deviljho','Kirin','Nergigante','Vaal Hazak','Teostra','Lunastra',
    'Kushala Daora','Daora','Zorah Magdaros',"Xeno'jiiva",'Kulve Taroth','Behemoth'
]
# Rank-specific large-monster pools.  We classify the material form, not merely the
# monster name, so LR and HR versions of the same monster land in different presets.
_HR_MARKERS=(
    '+','Scale+','Hide+','Pelt+','Claw+','Fang+','Ridge+','Plume+','Beak+','Sac+',
    'Carapace','Wing','Innerwing','Tail+','Horn+','Talon','Medulla','Ruby','Gem',
    'High-quality','Keenbone','Hardbone','Broth','Toxin Sac','Omniplegia Sac',
    'Coma Sac','Inferno Sac','Torrent Sac','Freezer Sac','Thunder Sac',
    'Azure Rathalos','Pink Rathian','Black Diablos','Dodogama','Lavasioth',
    'Uragaan','Bazelgeuse','Deviljho','Nergigante','Vaal Hazak','Teostra',
    'Lunastra','Daora','Xeno','Kulve Taroth','Behemoth'
)
_MR_FORM_MARKERS=(
    'Shard','Cortex','Thick','Hardclaw','Hardfang','Fellwing','Mantle','Pallium',
    'Lash','Grandfin','Chine','Surspike','Weave','Tailedge','Hellshell',
    'Tenderscale','Boulderplate','Tenderplate','Petalstone','Tenderclaw',
    'Skymerald','Dragonsphire','Evil Eye','Riptalon','Direwing','Diretail',
    'Skyswayer','Pectus','Wildpelt','Dragonlocks','Dragonhold','Apoplexy'
)

_LRHR_CANDIDATES=set()
for _m in _LARGE_LRHR_MONSTERS:
    _LRHR_CANDIDATES |= _ids_name_contains(_m)

LARGE_MONSTER_LR_IDS=set()
LARGE_MONSTER_HR_IDS=set()
for _i in _LRHR_CANDIDATES:
    _n=NORMAL_ITEM_NAMES.get(_i,'')
    if any(x.lower() in _n.lower() for x in _MR_FORM_MARKERS):
        continue
    if any(x.lower() in _n.lower() for x in _HR_MARKERS):
        LARGE_MONSTER_HR_IDS.add(_i)
    else:
        LARGE_MONSTER_LR_IDS.add(_i)

# MR monster order follows Iceborne's broad progression. Each family is indivisible for splitting.
_MR_MONSTER_ORDER=[
    'Great Jagras','Kulu-Ya-Ku','Pukei-Pukei','Barroth','Jyuratodus','Beotodus','Banbaro',
    'Tobi-Kadachi','Viper Tobi-Kadachi','Coral Pukei-Pukei','Anjanath','Tzitzi-Ya-Ku',
    'Great Girros','Paolumu','Nightshade Paolumu','Radobaan','Rathian','Pink Rathian',
    'Legiana','Shrieking Legiana','Odogaron','Rathalos','Azure Rathalos','Diablos','Black Diablos',
    'Lavasioth','Uragaan','Barioth','Nargacuga','Tigrex','Glavenus','Brachydios',
    'Fulgur Anjanath','Ebony Odogaron','Acidic Glavenus','Bazelgeuse','Seething Bazelgeuse',
    'Deviljho','Savage Deviljho','Velkhana','Blackveil Vaal Hazak','Namielle','Shara Ishvalda',
    'Zinogre','Yian Garuga','Scarred Yian Garuga','Gold Rathian','Silver Rathalos','Brute Tigrex',
    'Kirin','Rajang','Stygian Zinogre',"Safi'jiiva",'Frostfang Barioth','Raging Brachydios',
    'Furious Rajang','Kulve Taroth','Alatreon','Fatalis','Nergigante','Ruiner Nergigante',
    'Teostra','Lunastra','Kushala Daora','Daora'
]

# MR-specific terminology keeps HR/LR forms out of the MR lists.
_MR_MARKERS=(
    'Shard','Cortex','Thick','Hard','Fellwing','Mantle','Pallium','Lash','Grandfin','Chine',
    'Surspike','Weave','Tailedge','Hellshell','Tenderscale','Boulderplate','Tenderplate',
    'Petalstone','Tenderclaw','Skymerald','Dragonsphire','Evil Eye','Riptalon','Direwing',
    'Diretail','Skyswayer','Pectus','Wildpelt','Dragonlocks','Dragonhold','Apoplexy',
    'Gorer','Warhead','Obliterator','Reactor','Silverwhite','Silversnow','Bergcrusher',
    'Toughbone','Solidbone','Slogbone','Pure Dragon Blood','Large Elder Dragon',
    'Finehide','Crownhorn','Deathweaver','Shadowpierce','Blackpiel','Vile Fang','Ripper',
    'Crook','Flail','Distilled Blast Fluid','Scorching Silverwing','Rimed Hide',
    'Obsidian Icetalon','Stark Wing','Honed Acidcryst','Molten Bursa','Glowing Slime',
    'Fine Brachydios','Flickering Silvershell','Pulsing Dragonshell','Zionium'
)

def _mr_family_ids(monster):
    out=set()
    ml=monster.lower()
    for i,n in NORMAL_ITEM_NAMES.items():
        nl=n.lower()
        if ml in nl and any(k.lower() in nl for k in _MR_MARKERS):
            out.add(i)
    return out

# Add well-known MR families whose material names sometimes omit the monster's full name.
_MR_EXTRA_FAMILY_TERMS={
    'Velkhana':('Rimed Hide','Obsidian Icetalon','Stark Wing'),
    'Blackveil Vaal Hazak':('Deceased Shard','Deathweaver','Shadowpierce'),
    'Shara Ishvalda':('Tenderscale','Boulderplate','Tenderplate','Petalstone','Tenderclaw'),
    'Raging Brachydios':('Indestructible Ebonshell','Brach Warhead','Flashpoint Slime','Brach Obliterator','Immortal Reactor'),
    'Furious Rajang':('Rajang Apoplexy','Ghoulish Gold Gorer','Rajang Heart'),
    'Frostfang Barioth':('Silverwhite Frostfang','Silversnow Pelt','Bergcrusher Claw'),
}
def _mr_group(monster):
    s=_mr_family_ids(monster)
    if monster in _MR_EXTRA_FAMILY_TERMS:
        s |= _ids_name_contains(*_MR_EXTRA_FAMILY_TERMS[monster])
    return s

# Build unique monster groups in progression order. If a material name was caught by an earlier,
# broader family (e.g. Rathian before Gold Rathian), the later specific family owns its own matches.
_groups=[]
_owned=set()
for _monster in _MR_MONSTER_ORDER:
    _ids=_mr_group(_monster)
    # Specific variants should not duplicate an earlier base-family match.
    _ids -= _owned
    if _ids:
        _groups.append((_monster,_ids))
        _owned |= _ids

# Generic MR monster materials that are not tied to a single named large monster.
_MR_GENERIC=_ids_exact_names({
    'Monster Toughbone','Monster Slogbone','Monster Solidbone','Fey Wyvern Gem','Large Wyvern Gem',
    'Large Elder Dragon Bone','Pure Dragon Blood','Large Elder Dragon Gem'
})
if _MR_GENERIC:
    _groups.insert(0,('Generic MR Monster Materials',_MR_GENERIC))
    _owned |= _MR_GENERIC

# Split as close to the 255-item cap as possible WITHOUT ever splitting a monster family.
# Preset 1 greedily takes complete progression groups until the next whole group would exceed 255.
LARGE_MONSTER_MR_1_IDS=set()
LARGE_MONSTER_MR_2_IDS=set()
MR_PRESET_1_MONSTERS=[]
MR_PRESET_2_MONSTERS=[]
for _monster,_ids in _groups:
    if len(LARGE_MONSTER_MR_1_IDS | _ids) <= MAX_SHOP_ITEMS and not LARGE_MONSTER_MR_2_IDS:
        LARGE_MONSTER_MR_1_IDS |= _ids
        MR_PRESET_1_MONSTERS.append(_monster)
    else:
        LARGE_MONSTER_MR_2_IDS |= _ids
        MR_PRESET_2_MONSTERS.append(_monster)

# Exclude categories that have their own presets or are not ordinary monster materials.
_EXCLUDE_WORDS=('Ticket','Coin','Jewel','Feystone','Streamstone','Blueprint','Crystal Shard',
                'Forest Crystal','Wasteland Crystal','Reef Crystal','Effluvial Crystal',
                'Dragonvein Bone','Spiritvein','Guiding ')
for _s in (SMALL_MONSTER_LR_IDS,SMALL_MONSTER_HR_IDS,SMALL_MONSTER_MR_IDS,
           LARGE_MONSTER_LR_IDS,LARGE_MONSTER_HR_IDS,LARGE_MONSTER_MR_1_IDS,LARGE_MONSTER_MR_2_IDS):
    _s.difference_update({i for i in _s if any(w in NORMAL_ITEM_NAMES.get(i,'') for w in _EXCLUDE_WORDS)})



# Additional final category corrections.
# Meal vouchers belong with usable consumables; all Armor Spheres are treated as consumables/upgrades.
CONSUMABLE_IDS |= ({571,1003} & KNOWN_IDS)
CONSUMABLE_IDS |= {i for i,n in NORMAL_ITEM_NAMES.items() if 'Armor Sphere' in n and i in KNOWN_IDS}

# Generic gathering/bone materials grouped by rank.
_LR_GENERAL_MATERIALS={205,206,207,210,211,216,225,227,228,229,230,236,237,238,239}
_HR_GENERAL_MATERIALS={208,209,212,213,214,215,217,218,219,226,231,232,233}
_MR_GENERAL_MATERIALS={1030,1031,1032,1034,1036,1037,1038,1039,1042,1043,1044,1048,1049,1050,1051,1053}

_LR_GENERAL_MATERIALS &= KNOWN_IDS
_HR_GENERAL_MATERIALS &= KNOWN_IDS
_MR_GENERAL_MATERIALS &= KNOWN_IDS

# These belong exclusively to their rank material preset.
for _s in (LARGE_MONSTER_HR_IDS,LARGE_MONSTER_MR_1_IDS,LARGE_MONSTER_MR_2_IDS):
    _s.difference_update(_LR_GENERAL_MATERIALS)
for _s in (LARGE_MONSTER_LR_IDS,LARGE_MONSTER_MR_1_IDS,LARGE_MONSTER_MR_2_IDS):
    _s.difference_update(_HR_GENERAL_MATERIALS)
for _s in (LARGE_MONSTER_LR_IDS,LARGE_MONSTER_HR_IDS,LARGE_MONSTER_MR_2_IDS):
    _s.difference_update(_MR_GENERAL_MATERIALS)

LARGE_MONSTER_LR_IDS |= _LR_GENERAL_MATERIALS
LARGE_MONSTER_HR_IDS |= _HR_GENERAL_MATERIALS
LARGE_MONSTER_MR_1_IDS |= _MR_GENERAL_MATERIALS

# Final hand-verified preset corrections.
# These explicit moves override the generic name-based rank classification above.
_MOVE_TO_HR={979,980,981,982,983,984,985,986,987,988}
_MOVE_TO_MR={
    1059,1060,1061,1062,1063,1064,1065,
    1214,1215,1216,1217,1218,1219,
    1230,1239,1240,1315,1321,1324,1325,1327,1338,1339,1340,1343,1346,
    1355,1357,1362,1364,1370,1401
}
_MOVE_TO_HR &= KNOWN_IDS
_MOVE_TO_MR &= KNOWN_IDS

# Any large-monster material containing '+' is HR, never LR.
_PLUS_TO_HR={i for i in LARGE_MONSTER_LR_IDS if '+' in NORMAL_ITEM_NAMES.get(i,'')}
_MOVE_TO_HR |= _PLUS_TO_HR

# Remove moved entries from every conflicting preset first.
for _s in (CONSUMABLE_IDS,LARGE_MONSTER_LR_IDS,LARGE_MONSTER_HR_IDS,
           LARGE_MONSTER_MR_1_IDS,LARGE_MONSTER_MR_2_IDS):
    _s.difference_update(_MOVE_TO_MR)
for _s in (LARGE_MONSTER_LR_IDS,LARGE_MONSTER_MR_1_IDS,LARGE_MONSTER_MR_2_IDS):
    _s.difference_update(_MOVE_TO_HR)

LARGE_MONSTER_HR_IDS |= _MOVE_TO_HR
LARGE_MONSTER_MR_1_IDS |= _MOVE_TO_MR


# Explicit general-material rank assignments take final precedence over name heuristics.
for _s in (LARGE_MONSTER_HR_IDS,LARGE_MONSTER_MR_1_IDS,LARGE_MONSTER_MR_2_IDS):
    _s.difference_update(_LR_GENERAL_MATERIALS)
for _s in (LARGE_MONSTER_LR_IDS,LARGE_MONSTER_MR_1_IDS,LARGE_MONSTER_MR_2_IDS):
    _s.difference_update(_HR_GENERAL_MATERIALS)
for _s in (LARGE_MONSTER_LR_IDS,LARGE_MONSTER_HR_IDS,LARGE_MONSTER_MR_2_IDS):
    _s.difference_update(_MR_GENERAL_MATERIALS)
LARGE_MONSTER_LR_IDS |= _LR_GENERAL_MATERIALS
LARGE_MONSTER_HR_IDS |= _HR_GENERAL_MATERIALS
LARGE_MONSTER_MR_1_IDS |= _MR_GENERAL_MATERIALS


# Final Guiding Lands / MR material corrections after multiplayer testing.
CONSUMABLE_IDS |= ({1000,1003,1006,1007,1008} & KNOWN_IDS)

# IDs 1026-1028 must not be exposed as purchasable shop items.
NON_SHOP_IDS |= {1026,1027,1028}
KNOWN_IDS -= {1026,1027,1028}
SHOP_KNOWN_IDS -= {1026,1027,1028}
for _s in (CONSUMABLE_IDS,SMALL_MONSTER_LR_IDS,SMALL_MONSTER_HR_IDS,SMALL_MONSTER_MR_IDS,
           LARGE_MONSTER_LR_IDS,LARGE_MONSTER_HR_IDS,LARGE_MONSTER_MR_1_IDS,LARGE_MONSTER_MR_2_IDS,
           EVENT_TICKET_IDS,GUIDING_LANDS_IDS):
    _s.difference_update({1026,1027,1028})

# Move usable entries from the former, incorrect GL preset into MR Materials.
_OLD_GL_USABLE={i for i in GUIDING_LANDS_IDS if i in KNOWN_IDS}
_OLD_GL_USABLE -= {1000,1003,1006,1007,1008,1026,1027,1028}
LARGE_MONSTER_MR_1_IDS |= _OLD_GL_USABLE

# Correct GL Materials range. Unavailable IDs are absent from the embedded database/KNOWN_IDS.
GUIDING_LANDS_IDS=({1791} | set(range(1795,1968))) & KNOWN_IDS

# Every usable ID 1056-1401 belongs to MR Materials except Small Monsters MR
# and categories with their own dedicated preset.
_MR_FULL_RANGE=(set(range(1056,1402)) & KNOWN_IDS) - SMALL_MONSTER_MR_IDS
LARGE_MONSTER_MR_1_IDS |= _MR_FULL_RANGE

# Keep dedicated categories out of MR Materials.
LARGE_MONSTER_MR_1_IDS -= SMALL_MONSTER_MR_IDS
LARGE_MONSTER_MR_1_IDS -= GUIDING_LANDS_IDS
LARGE_MONSTER_MR_1_IDS -= CONSUMABLE_IDS
LARGE_MONSTER_MR_1_IDS -= EVENT_TICKET_IDS


# Final hand-tested rank corrections.
_KIRIN_HR_IDS={i for i,n in NORMAL_ITEM_NAMES.items() if n in {'Kirin Thundertail','Kirin Azure Horn'}}
_LR_TO_MR={1099,1100,1104,1109,1114,1129,1134,1140,1142,1148,1164,1174,1194,1200,1224,1337} & KNOWN_IDS
_HR_TO_MR={1096,1127,1132,1179,1185,1222,1376} & KNOWN_IDS
_FORCE_HR={907} & KNOWN_IDS

LARGE_MONSTER_LR_IDS -= _KIRIN_HR_IDS
LARGE_MONSTER_HR_IDS |= _KIRIN_HR_IDS
LARGE_MONSTER_LR_IDS -= _LR_TO_MR
LARGE_MONSTER_HR_IDS -= _HR_TO_MR
LARGE_MONSTER_MR_1_IDS |= (_LR_TO_MR | _HR_TO_MR)
LARGE_MONSTER_LR_IDS -= _FORCE_HR
LARGE_MONSTER_MR_1_IDS -= _FORCE_HR
LARGE_MONSTER_HR_IDS |= _FORCE_HR


# Additional hand-tested HR material coverage.
# Add these IDs to HR Materials only if they are not already assigned to another preset.
_HR_REQUESTED_IDS=(
    {225} | set(range(227,231)) | set(range(236,243)) |
    {248,250,252,254,256,258,260} | set(range(261,264)) |
    set(range(302,519))
) & KNOWN_IDS

_HR_OTHER_PRESETS=(
    CONSUMABLE_IDS |
    SMALL_MONSTER_LR_IDS | SMALL_MONSTER_HR_IDS | SMALL_MONSTER_MR_IDS |
    LARGE_MONSTER_LR_IDS |
    LARGE_MONSTER_MR_1_IDS | LARGE_MONSTER_MR_2_IDS |
    GUIDING_LANDS_IDS | EVENT_TICKET_IDS |
    JEWEL_1_IDS if 'JEWEL_1_IDS' in globals() else set()
)
# Jewel presets are defined later, but these requested IDs are below the jewel ranges.
# Therefore only the already-defined non-HR presets need to be excluded here.
_HR_OTHER_PRESETS=(
    CONSUMABLE_IDS |
    SMALL_MONSTER_LR_IDS | SMALL_MONSTER_HR_IDS | SMALL_MONSTER_MR_IDS |
    LARGE_MONSTER_LR_IDS |
    LARGE_MONSTER_MR_1_IDS | LARGE_MONSTER_MR_2_IDS |
    GUIDING_LANDS_IDS | EVENT_TICKET_IDS
)
LARGE_MONSTER_HR_IDS |= (_HR_REQUESTED_IDS - _HR_OTHER_PRESETS)

# Split MR Materials at ID 1290 for clearer separation.
_MR_ALL_IDS=set(LARGE_MONSTER_MR_1_IDS) | set(LARGE_MONSTER_MR_2_IDS)
LARGE_MONSTER_MR_1_IDS={i for i in _MR_ALL_IDS if i < 1290}
LARGE_MONSTER_MR_2_IDS={i for i in _MR_ALL_IDS if i >= 1290}


# Additional event items requested for the Tickets/Coins/Events preset.
_EVENT_EXTRA_NAMES={
    'Spring Insect Field Guide',
    'Summer Insect Field Guide',
    'Black Bandage',
    'Azure Star Shard',
    'Azure Stargem',
    'Red Orb',
    "Master Craftsman's Blueprint",
    "Senu's Feather",
    'Black Eagle Blueprint',
    'Wiggler Pot',
    'S.T.A.R.S. Badge',
    'Sealed Dragon Cloth',
    'Unity Symbol',
}
_EVENT_EXTRA_IDS={i for i,n in NORMAL_ITEM_NAMES.items() if n in _EVENT_EXTRA_NAMES and i in KNOWN_IDS}
EVENT_TICKET_IDS |= _EVENT_EXTRA_IDS

# Jewel presets are grouped by slot level/name rather than rarity.
# Dual-skill jewels (e.g. Drain/Physique Jewel 4) always go into their own preset.
DUAL_SKILL_JEWEL_IDS={i for i,n in DECORATION_NAMES.items() if '/' in n}

def _single_jewel_level(level):
    suffix=' '+str(level)
    return {i for i,n in DECORATION_NAMES.items()
            if i not in DUAL_SKILL_JEWEL_IDS and n.endswith(suffix)}

JEWEL_1_IDS=_single_jewel_level(1)
JEWEL_2_IDS=_single_jewel_level(2)
JEWEL_3_IDS=_single_jewel_level(3)
JEWEL_4_IDS=_single_jewel_level(4)

# ---------------------------------------------------------------------------
# Binary file helpers
# ---------------------------------------------------------------------------

def name(i): return SHOP_NAMES.get(i,f'Item {i}')
def backup(path):
    if os.path.isfile(path):
        try: shutil.copy2(path,path+'.bak')
        except OSError: pass

def parse_item(data):
    if len(data)<ITEM_HEADER_SIZE or (len(data)-ITEM_HEADER_SIZE)%32: raise ValueError('Unsupported ItemData.itm layout.')
    n=(len(data)-ITEM_HEADER_SIZE)//32
    ids=[struct.unpack_from('<H',data,ITEM_HEADER_SIZE+j*32)[0] for j in range(n)]
    if ids and ids[0]==0: ids=ids[1:]
    # This vanilla Iceborne file contains IDs 1..2774. For other valid files we still accept the records.
    return n


def apply_default_jewel_price_fixes(data):
    """Give every known vanilla 0z Jewel a usable shop price automatically."""
    d=bytearray(data)
    n=parse_item(d)
    for j in range(n):
        pos=ITEM_HEADER_SIZE+j*ITEM_RECORD_SIZE
        iid=struct.unpack_from('<H',d,pos)[0]
        if iid not in DECORATION_NAMES:
            continue
        stored_buy=struct.unpack_from('<I',d,pos+BUY_OFFSET)[0]
        if stored_buy==0:
            # Displayed values: Sell 5,000z / Buy 50,000z.
            struct.pack_into('<I',d,pos+SELL_OFFSET,5000*2)
            struct.pack_into('<I',d,pos+BUY_OFFSET,50000*2)
    return d

def read_items_from_bytes(data):
    n=parse_item(data); rows=[]
    for j in range(n):
        pos=ITEM_HEADER_SIZE+j*32; iid=struct.unpack_from('<H',data,pos)[0]
        sell=struct.unpack_from('<I',data,pos+SELL_OFFSET)[0]//2; buy=struct.unpack_from('<I',data,pos+BUY_OFFSET)[0]//2
        rows.append([iid,name(iid),sell,buy,pos])
    return data,rows

def read_items(path):
    return read_items_from_bytes(bytearray(open(path,'rb').read()))

def parse_shop(data):
    if len(data)<SHOP_HEADER_SIZE or (len(data)-SHOP_HEADER_SIZE)%SHOP_RECORD_SIZE: raise ValueError('Unsupported shopList.slt layout.')
    n=(len(data)-SHOP_HEADER_SIZE)//SHOP_RECORD_SIZE
    rows=[]
    for j in range(n):
        p=SHOP_HEADER_SIZE+j*SHOP_RECORD_SIZE; idx,iid,meta,order=struct.unpack_from('<IIIH',data,p); rows.append([idx,iid,meta,order,p])
    return rows

def write_shop(path, original, ids):
    if len(ids)>MAX_SHOP_ITEMS: raise ValueError('A shop can contain at most 255 items.')
    old=parse_shop(original); by_id={r[1]:r for r in old}; max_order=max([r[3] for r in old],default=0)
    out=bytearray(original[:SHOP_HEADER_SIZE])
    # shopList.slt stores (number of entries + 1) in header byte 6.
    # Without updating this, MHW stops reading after the original vanilla 55 entries.
    if len(out) > 6:
        out[6]=(len(ids)+1) & 0xFF
    for pos,iid in enumerate(ids,1):
        if iid in by_id: meta=by_id[iid][2]; order=by_id[iid][3]
        else: meta=0; max_order+=1; order=max_order
        out += struct.pack('<IIIH',pos,int(iid),int(meta),int(order))
    backup(path); open(path,'wb').write(out)

# ---------------------------------------------------------------------------
# Tkinter user interface
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        try:
            self.iconbitmap(resource_path("MHW_Editor.ico"))
        except tk.TclError:
            pass
        self.geometry('1200x720')
        self.minsize(1000,600)
        self.item_path=None; self.item_data=None; self.items=[]; self.shop_path=None; self.shop_data=None; self.shop_ids=[]
        self.sv=tk.StringVar(); self.tsv=tk.StringVar(); self.status=tk.StringVar(value='Ready.')
        self.build()
    def build(self):
        nb=ttk.Notebook(self); nb.pack(fill='both',expand=True,padx=8,pady=8); it=ttk.Frame(nb); sh=ttk.Frame(nb); nb.add(it,text='Price Editor'); nb.add(sh,text='Shop Editor'); self.it=it; self.sh=sh
        self.build_items(); self.build_shop(); ttk.Label(self,textvariable=self.status,anchor='w').pack(fill='x',padx=10,pady=(0,8))
    def build_items(self):
        t=ttk.Frame(self.it); t.pack(fill='x',padx=8,pady=8); ttk.Button(t,text='Open ItemData.itm',command=self.open_item).pack(side='left'); ttk.Button(t,text='Create Vanilla ItemData.itm',command=self.vanilla_item).pack(side='left',padx=6); ttk.Button(t,text='Save',command=self.save_item).pack(side='left',padx=6); ttk.Button(t,text='Save As...',command=self.save_item_as).pack(side='left'); ttk.Label(t,text='Search:').pack(side='left',padx=(25,4)); e=ttk.Entry(t,textvariable=self.sv,width=30); e.pack(side='left'); e.bind('<KeyRelease>',lambda e:self.refresh_items())
        b=ttk.Frame(self.it); b.pack(fill='x',padx=8,pady=(0,8))
        ttk.Button(b,text='×2 All Sell Prices',command=lambda:self.bulk_price(2,2,'Double all sell prices')).pack(side='left')
        ttk.Button(b,text='÷2 All Sell Prices',command=lambda:self.bulk_price(2,0.5,'Halve all sell prices')).pack(side='left',padx=4)
        ttk.Button(b,text='×2 All Buy Prices',command=lambda:self.bulk_price(3,2,'Double all buy prices')).pack(side='left',padx=(12,4))
        ttk.Button(b,text='÷2 All Buy Prices',command=lambda:self.bulk_price(3,0.5,'Halve all buy prices')).pack(side='left')
        ttk.Button(b,text='Cheat Prices',command=self.cheat_prices).pack(side='right'); ttk.Button(b,text='Restore Vanilla Prices',command=self.restore_vanilla_prices).pack(side='right',padx=6)
        self.tree=ttk.Treeview(self.it,columns=('id','name','sell','buy'),show='headings');
        for c,h,w in [('id','Item ID',100),('name','Item Name',500),('sell','Sell Price',150),('buy','Buy Price',150)]: self.tree.heading(c,text=h); self.tree.column(c,width=w)
        self.tree.pack(fill='both',expand=True,padx=8,pady=(0,8)); self.tree.bind('<Double-1>',self.edit_price); ttk.Label(self.it,text='Double-click a price to edit. Prices shown are actual in-game prices.').pack(anchor='w',padx=8,pady=(0,8))
    def refresh_items(self):
        q=self.sv.get().lower(); [self.tree.delete(x) for x in self.tree.get_children()]
        for j,r in enumerate(self.items):
            if r[0] not in SHOP_KNOWN_IDS: continue
            if q and q not in str(r[0]).lower() and q not in r[1].lower(): continue
            self.tree.insert('', 'end',iid=str(j),values=r[:4])
    def open_item(self):
        p=filedialog.askopenfilename(title='Open ItemData.itm',filetypes=[('ItemData.itm','*.itm'),('All files','*.*')]);
        if not p:return
        try:self.item_data,self.items=read_items(p); self.item_path=p; self.refresh_items(); self.status.set(f'Loaded {len(self.items)} item records.')
        except Exception as e:messagebox.showerror('Open failed',str(e))
    def vanilla_item(self):
        p=filedialog.asksaveasfilename(title='Create Vanilla ItemData.itm',initialfile='itemData.itm',defaultextension='.itm',filetypes=[('ItemData.itm','*.itm')]);
        if not p:return
        open(p,'wb').write(apply_default_jewel_price_fixes(base64.b64decode(VANILLA_ITEM_B64))); self.item_path=p; self.item_data,self.items=read_items(p); self.refresh_items(); self.status.set('Created vanilla ItemData.itm.')
    def edit_price(self,e):
        s=self.tree.selection(); c=self.tree.identify_column(e.x);
        if not s or c not in ('#3','#4'):return
        j=int(s[0]); field=2 if c=='#3' else 3; w=tk.Toplevel(self); w.title('Edit Price'); ttk.Label(w,text=f'{self.items[j][1]} (ID {self.items[j][0]})').pack(padx=15,pady=12); v=tk.StringVar(value=str(self.items[j][field])); x=ttk.Entry(w,textvariable=v); x.pack(padx=15); x.focus_set()
        def ok():
            try:n=int(v.get()); assert 0<=n<=0x7fffffff
            except:messagebox.showerror('Invalid price','Enter a non-negative integer.',parent=w);return
            self.items[j][field]=n; self.refresh_items(); w.destroy()
        ttk.Button(w,text='Apply',command=ok).pack(pady=12); x.bind('<Return>',lambda e:ok())
    def known_rows(self):
        return [r for r in self.items if r[0] in SHOP_KNOWN_IDS]
    def restore_vanilla_prices(self):
        if not self.items or self.item_data is None:
            return messagebox.showwarning('No item file','Open an ItemData.itm file first.')
        if not messagebox.askyesno(
            'Restore Vanilla Prices?',
            'Restore ALL known item buy and sell prices to the embedded vanilla values?\n\n'
            'This will overwrite your current price edits. The file is not written to disk until you click Save.'
        ):
            return
        try:
            _, vanilla_rows=read_items_from_bytes(bytearray(base64.b64decode(VANILLA_ITEM_B64)))
            vanilla={r[0]:(r[2],r[3]) for r in vanilla_rows}
            changed=0
            for r in self.items:
                if r[0] in KNOWN_IDS and r[0] in vanilla:
                    vs,vb=vanilla[r[0]]
                    if r[2] != vs or r[3] != vb:
                        r[2],r[3]=vs,vb
                        changed+=1
            self.refresh_items()
            self.status.set(f'Restored vanilla prices for {changed} changed items.')
        except Exception as e:
            messagebox.showerror('Restore failed',str(e))

    def bulk_price(self,field,factor,label):
        rows=self.known_rows()
        if not rows:return messagebox.showwarning('No item data','Open ItemData.itm first.')
        if not messagebox.askyesno('Confirm price change',f'{label} for {len(rows)} known items?'):return
        for r in rows:
            r[field]=min(MAX_DISPLAY_PRICE,r[field]*2) if factor==2 else r[field]//2
        self.refresh_items();self.status.set(f'{label} applied to {len(rows)} known items.')
    def cheat_prices(self):
        rows=self.known_rows()
        if not rows:return messagebox.showwarning('No item data','Open ItemData.itm first.')
        if not messagebox.askyesno('Apply Cheat Prices?','Set the Buy Price of all known items to 1 and Potion Sell Price to 100,000?\n\nAll other Sell Prices remain unchanged.'):return
        for r in rows:r[3]=1
        for r in rows:
            if r[0]==1:
                r[2]=100000;break
        self.refresh_items();self.status.set('Cheat Prices applied: all known Buy Prices = 1; Potion Sell Price = 100,000.')
    def save_item(self):
        if not self.item_path:return self.save_item_as()
        try:
            d=bytearray(self.item_data)
            for r in self.items: struct.pack_into('<I',d,r[4]+SELL_OFFSET,r[2]*2); struct.pack_into('<I',d,r[4]+BUY_OFFSET,r[3]*2)
            backup(self.item_path); open(self.item_path,'wb').write(d); self.item_data=d; self.status.set('ItemData.itm saved; backup created if possible.')
        except Exception as e:messagebox.showerror('Save failed',str(e))
    def save_item_as(self):
        if not self.item_data:return
        p=filedialog.asksaveasfilename(title='Save ItemData.itm As',initialfile='itemData.itm',defaultextension='.itm',filetypes=[('ItemData.itm','*.itm')]);
        if not p:return
        d=bytearray(self.item_data)
        for r in self.items:struct.pack_into('<I',d,r[4]+SELL_OFFSET,r[2]*2);struct.pack_into('<I',d,r[4]+BUY_OFFSET,r[3]*2)
        open(p,'wb').write(d);self.item_path=p;self.item_data=d;self.status.set('ItemData.itm saved.')
    def build_shop(self):
        t=ttk.Frame(self.sh);t.pack(fill='x',padx=8,pady=8);ttk.Button(t,text='Open shopList.slt',command=self.open_shop).pack(side='left');ttk.Button(t,text='Create Vanilla shopList.slt',command=self.vanilla_shop).pack(side='left',padx=6);ttk.Button(t,text='Save',command=self.save_shop).pack(side='left',padx=6);ttk.Button(t,text='Save As...',command=self.save_shop_as).pack(side='left');self.count=ttk.Label(t,text='0 / 255 items');self.count.pack(side='right')
        pr=ttk.LabelFrame(self.sh,text='Shop Presets');pr.pack(fill='x',padx=8,pady=(0,8))

        general_frame=ttk.LabelFrame(pr,text='General')
        general_frame.pack(fill='x',padx=6,pady=(6,4))
        for k in range(2):
            general_frame.columnconfigure(k,weight=1)
        ttk.Button(general_frame,text='Vanilla Shop',command=self.preset_vanilla).grid(row=0,column=0,padx=3,pady=4,sticky='ew')
        ttk.Button(general_frame,text='Consumables/Ammo',command=lambda:self.apply_preset('Consumables/Ammo',CONSUMABLE_IDS)).grid(row=0,column=1,padx=3,pady=4,sticky='ew')

        material_frame=ttk.LabelFrame(pr,text='Materials')
        material_frame.pack(fill='x',padx=6,pady=(4,6))
        for k in range(5):
            material_frame.columnconfigure(k,weight=1)
        material_presets=[
            ('Small Monsters LR',lambda:self.apply_preset('Small Monsters LR',SMALL_MONSTER_LR_IDS)),
            ('Small Monsters HR',lambda:self.apply_preset('Small Monsters HR',SMALL_MONSTER_HR_IDS)),
            ('Small Monsters MR',lambda:self.apply_preset('Small Monsters MR',SMALL_MONSTER_MR_IDS)),
            ('LR Materials',lambda:self.apply_preset('LR Materials',LARGE_MONSTER_LR_IDS)),
            ('HR Materials',lambda:self.apply_preset('HR Materials',LARGE_MONSTER_HR_IDS)),
            ('MR Materials 1',lambda:self.apply_preset('MR Materials 1',LARGE_MONSTER_MR_1_IDS)),
            ('MR Materials 2',lambda:self.apply_preset('MR Materials 2',LARGE_MONSTER_MR_2_IDS)),
            ('GL Materials',lambda:self.apply_preset('GL Materials',GUIDING_LANDS_IDS)),
            ('Tickets/Coins/Events',lambda:self.apply_preset('Tickets/Coins/Events',EVENT_TICKET_IDS))
        ]
        for k,(txt,cmd) in enumerate(material_presets):
            ttk.Button(material_frame,text=txt,command=cmd).grid(row=k//5,column=k%5,padx=3,pady=3,sticky='ew')

        jewel_frame=ttk.LabelFrame(self.sh,text='Jewels',padding=6)
        jewel_frame.pack(fill='x',padx=8,pady=(0,8))
        jewel_presets=[
            ('Jewel 1',lambda:self.apply_preset('Jewel 1',JEWEL_1_IDS)),
            ('Jewel 2',lambda:self.apply_preset('Jewel 2',JEWEL_2_IDS)),
            ('Jewel 3',lambda:self.apply_preset('Jewel 3',JEWEL_3_IDS)),
            ('Jewel 4',lambda:self.apply_preset('Jewel 4',JEWEL_4_IDS)),
            ('Dual-Skill Jewels',lambda:self.apply_preset('Dual-Skill Jewels',DUAL_SKILL_JEWEL_IDS))
        ]
        for k,(txt,cmd) in enumerate(jewel_presets):
            ttk.Button(jewel_frame,text=txt,command=cmd).grid(row=0,column=k,padx=3,pady=3,sticky='ew')
            jewel_frame.columnconfigure(k,weight=1)
        pan=ttk.PanedWindow(self.sh,orient='horizontal');pan.pack(fill='both',expand=True,padx=8,pady=(0,8));l=ttk.Frame(pan);r=ttk.Frame(pan);pan.add(l,weight=1);pan.add(r,weight=1);ttk.Label(l,text='Available Items').pack(anchor='w');q=ttk.Frame(l);q.pack(fill='x',pady=4);ttk.Label(q,text='Search:').pack(side='left');x=ttk.Entry(q,textvariable=self.tsv);x.pack(side='left',fill='x',expand=True,padx=4);x.bind('<KeyRelease>',lambda e:self.refresh_available());self.av=tk.Listbox(l,selectmode='extended');self.av.pack(fill='both',expand=True);b=ttk.Frame(l);b.pack(fill='x',pady=5);ttk.Button(b,text='Add Selected →',command=self.add).pack(side='left');ttk.Button(b,text='Add All Matching',command=self.addall).pack(side='left',padx=5);ttk.Label(r,text='Items in Shop').pack(anchor='w');self.ins=tk.Listbox(r,selectmode='extended');self.ins.pack(fill='both',expand=True);b=ttk.Frame(r);b.pack(fill='x',pady=5);ttk.Button(b,text='← Remove Selected',command=self.remove).pack(side='left');ttk.Button(b,text='Move Up',command=lambda:self.move(-1)).pack(side='left',padx=5);ttk.Button(b,text='Move Down',command=lambda:self.move(1)).pack(side='left');ttk.Button(b,text='Clear Shop',command=self.clear).pack(side='right');self.refresh_available()
    def apply_preset(self,label,ids):
        ids=[i for i in sorted(set(ids)) if i in SHOP_KNOWN_IDS and i not in UNSAFE_IDS]
        existing=set(self.shop_ids)
        add=[i for i in ids if i not in existing]
        skipped=len(ids)-len(add)
        new_total=len(self.shop_ids)+len(add)
        if new_total>MAX_SHOP_ITEMS:
            return messagebox.showwarning(
                'Shop limit',
                f'Cannot add the “{label}” preset.\n\n'
                f'Current shop: {len(self.shop_ids)} items\n'
                f'New unique items: {len(add)}\n'
                f'Result: {new_total} / {MAX_SHOP_ITEMS}\n\n'
                'Nothing was added.'
            )
        if not add:
            return messagebox.showinfo('Preset already added',f'All {len(ids)} items from “{label}” are already in the shop.')
        if not messagebox.askyesno(
            'Add preset?',
            f'Add the “{label}” preset to the current shop?\n\n'
            f'Current shop: {len(self.shop_ids)} items\n'
            f'New unique items: {len(add)}\n'
            f'Already present: {skipped}\n'
            f'Result: {new_total} / {MAX_SHOP_ITEMS}'
        ):
            return
        self.shop_ids.extend(add)
        self.refresh_shop()
        self.status.set(f'Added {len(add)} items from {label} ({len(self.shop_ids)}/{MAX_SHOP_ITEMS}).')

    def preset_vanilla(self):
        data=bytearray(base64.b64decode(VANILLA_SHOP_B64));ids=[r[1] for r in parse_shop(data) if r[1] in KNOWN_IDS]
        if not messagebox.askyesno('Replace shop?',f'Restore the embedded Vanilla Shop?\n\nCurrent shop: {len(self.shop_ids)} items\nVanilla shop: {len(ids)} items'):return
        self.shop_ids=ids;self.refresh_shop();self.status.set(f'Vanilla Shop preset loaded ({len(ids)} items).')
    def open_shop(self):
        p=filedialog.askopenfilename(title='Open shopList.slt',filetypes=[('shopList.slt','*.slt'),('All files','*.*')]);
        if not p:return
        try:self.shop_data=bytearray(open(p,'rb').read()); rows=parse_shop(self.shop_data);self.shop_ids=[r[1] for r in rows];self.shop_path=p;self.refresh_shop();self.status.set(f'Loaded {len(self.shop_ids)} shop entries.')
        except Exception as e:messagebox.showerror('Open failed',str(e))
    def vanilla_shop(self):
        p=filedialog.asksaveasfilename(title='Create Vanilla shopList.slt',initialfile='shopList.slt',defaultextension='.slt',filetypes=[('shopList.slt','*.slt')]);
        if not p:return
        open(p,'wb').write(base64.b64decode(VANILLA_SHOP_B64));self.shop_path=p;self.shop_data=bytearray(base64.b64decode(VANILLA_SHOP_B64));self.shop_ids=[r[1] for r in parse_shop(self.shop_data)];self.refresh_shop();self.status.set('Created vanilla shopList.slt.')
    def refresh_available(self):
        if not hasattr(self,'av'):return
        q=self.tsv.get().lower();self.av.delete(0,'end');
        for i in sorted(SHOP_KNOWN_IDS):
            if i in self.shop_ids:continue
            s=f'{i:04d} - {name(i)}';
            if not q or q in s.lower():self.av.insert('end',s)
    def ids_available(self):
        q=self.tsv.get().lower();return [i for i in sorted(KNOWN_IDS) if i not in self.shop_ids and (not q or q in f'{i:04d} - {name(i)}'.lower())]
    def refresh_shop(self):
        self.ins.delete(0,'end');[self.ins.insert('end',f'{i:04d} - {name(i)}') for i in self.shop_ids];self.count.config(text=f'{len(self.shop_ids)} / {MAX_SHOP_ITEMS} items');self.refresh_available()
    def add(self):
        ids=self.ids_available();sel=[ids[i] for i in self.av.curselection()];
        if len(self.shop_ids)+len(sel)>MAX_SHOP_ITEMS:return messagebox.showwarning('Shop limit','A shop can contain at most 255 items.')
        self.shop_ids += [i for i in sel if i not in UNSAFE_IDS];self.refresh_shop()
    def addall(self):
        ids=[i for i in self.ids_available() if i not in UNSAFE_IDS];room=MAX_SHOP_ITEMS-len(self.shop_ids);self.shop_ids+=ids[:room];self.refresh_shop()
    def remove(self):
        for i in reversed(self.ins.curselection()):del self.shop_ids[i]
        self.refresh_shop()
    def move(self,d):
        s=self.ins.curselection();
        if len(s)!=1:return
        i=s[0];j=i+d
        if 0<=j<len(self.shop_ids):self.shop_ids[i],self.shop_ids[j]=self.shop_ids[j],self.shop_ids[i];self.refresh_shop();self.ins.selection_set(j)
    def clear(self):
        if messagebox.askyesno('Clear shop','Remove all items from this shop?'):self.shop_ids=[];self.refresh_shop()
    def save_shop(self):
        if not self.shop_path:return self.save_shop_as()
        try:write_shop(self.shop_path,self.shop_data,self.shop_ids);self.shop_data=bytearray(open(self.shop_path,'rb').read());self.status.set('shopList.slt saved; backup created if possible.')
        except Exception as e:messagebox.showerror('Save failed',str(e))
    def save_shop_as(self):
        p=filedialog.asksaveasfilename(title='Save shopList.slt As',initialfile='shopList.slt',defaultextension='.slt',filetypes=[('shopList.slt','*.slt')]);
        if not p:return
        try:write_shop(p,self.shop_data,self.shop_ids);self.shop_path=p;self.shop_data=bytearray(open(p,'rb').read());self.status.set('shopList.slt saved.')
        except Exception as e:messagebox.showerror('Save failed',str(e))

if __name__=='__main__':App().mainloop()
