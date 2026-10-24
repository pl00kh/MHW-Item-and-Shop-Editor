# MHW Item & Shop Editor

A small editor for **Monster Hunter: World / Iceborne** `itemData.itm`
and `shopList.slt` files.

## Features

- Edit item buy and sell prices
- Create a vanilla `itemData.itm`
- Edit the shop list
- Create a vanilla `shopList.slt`
- Built-in shop presets for consumables/ammo, LR/HR/MR materials,
  Guiding Lands materials, tickets/coins/events, and jewels
- Automatic `.bak` backups
- Fully offline embedded item database
- PyInstaller-compatible Windows build

## Project structure

```text
MHW_Item_and_Shop_Editor/
├─ main.py          # Application logic and Tkinter UI
├─ mhw_data.py      # Embedded item database and vanilla binary templates
├─ Editor.ico       # Application icon
├─ README.md
└─ .gitignore
```

The large static item tables are intentionally kept in `mhw_data.py`. This keeps
`main.py` much easier to read without introducing an internet dependency.

## Run from source

Python 3.8 or newer is recommended.

```powershell
py main.py
```

No third-party Python packages are required to run the editor.

## Build the Windows EXE

Place your existing `Editor.ico` next to `main.py`, then run:

```powershell
py -m PyInstaller --onefile --windowed --icon="Editor.ico" --add-data="Editor.ico;." --name "MHW Item and Shop Editor" "main.py"
```

The finished executable will be created in:

```text
dist\MHW Item and Shop Editor.exe
```

PyInstaller itself is only needed for building the EXE.

## Notes

- The editor keeps the full binary structure of the game files intact.
- Displayed item prices use the in-game value; the editor handles the game's
  stored price conversion internally.
- Shop presets respect the game's shop-entry limit.
- Unknown/unavailable or explicitly blocked shop entries are excluded from
  automatic presets.

## Disclaimer

This is a community-made modding utility and is not affiliated with or endorsed
by Capcom.
