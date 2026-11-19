Megami Ibunroku Persona - native PC version (English), version {VERSION}
==========================================================================

The 1996 PlayStation game Megami Ibunroku Persona, recompiled to run natively on Windows, in English with
Redeted's fan translation and quality-of-life patch.

This download contains NO game data. You need your own copy of the game.


WHAT YOU NEED
-------------
- Windows 10 or 11, 64-bit, and a graphics card with OpenGL support.
- A disc image of your own copy of Megami Ibunroku Persona (Japan, SLPS-00500), FIRST RELEASE, as BIN/CUE:
  the .bin is 699,705,888 bytes. The later "Rev 1" release is not supported.
  (A disc image already patched with Redeted's Persona-TL-QoL patch works too.)
- About 700 MB of free space next to the game, for the translated copy of the disc.


STARTING THE GAME
-----------------
1. Unpack the whole folder anywhere you can write to (e.g. Documents or Desktop, not Program Files).
2. Double-click Persona.exe.
   Windows may warn "Windows protected your PC" (the exe is not code-signed, as usual for fan projects):
   click "More info", then "Run anyway". Some antivirus programs are wary of new unsigned exes too.
3. The first time, it asks for your disc image: choose the .cue (or .bin) file.
   If it is the original Japanese disc, the English translation is applied to a copy in the "disc" folder
   (a few seconds). Your own file is not changed.
4. That's it: the disc is remembered (disc.cfg), so next time the game starts straight away.

To use a different disc image later, delete disc.cfg.


CONTROLS
--------
A controller works out of the box (Xbox, PlayStation, Switch Pro and most others); plug it in any time.
Keyboard:
  Arrow keys       move                     Enter          Start
  X                Cross                    Right Shift    Select
  S                Circle                   Q / W          L1 / R1
  Z                Square                   E / R          L2 / R2
  A                Triangle
Change keys and buttons in the options menu (F10, page CONTROLS).
The game's own button setup (confirm / cancel ...) is in its System > Config menu.


MENUS AND KEYS
--------------
  F10           Options: screen mode, resolution, picture, volume, skip movies, controls.
                Controller: Guide/PS button, or Select + L1 + R1.
  F7            Save states (quick save / load slots). They only work with this exact version of the game:
                use the in-game saves for anything you want to keep.
  Alt + Enter   Fullscreen on / off
  Keypad + / -  Volume
  F9            Debug menu (warp anywhere, battle cheats). Controller: Select + L2 + R2.
                Use with care: warping ahead of the story can leave your save in a strange state.


SAVES AND SETTINGS
------------------
In-game saves are kept on the virtual memory cards card1.mcd and card2.mcd next to Persona.exe.
Settings are in settings.toml, keybinds.ini, input.ini and persona_options.txt in the same folder.
Back up the .mcd files when you move or update the game. To update: unpack the new version into a new
folder and copy card1.mcd and card2.mcd (and disc.cfg + the disc folder, if you like) over.

Check your download: release notes list the SHA-256 of the zip (PowerShell: Get-FileHash <zip>).


CREDITS
-------
- Native PC port (recompilation, menus, disc patcher): Zacharias Tzifopoulos,
  developed with the help of Claude (Anthropic's AI assistant, in Claude Code).
- Megami Ibunroku Persona (c) 1996 ATLUS. This is an unofficial, non-commercial fan project, not affiliated
  with or endorsed by ATLUS or SEGA. Please support the official releases.
- English translation and QoL patch: Redeted (MIT licence) - Persona-TL-QoL.xdelta is their patch.
- Recompiler and runtime: psxrecomp by Matthew Stan (PolyForm Noncommercial 1.0).
- BIOS: OpenBIOS from the PCSX-Redux project (MIT).
- Libraries: SDL3, libchdr, LZMA SDK, zlib, zstd, miniz and others: see the licenses folder.

This download may be shared for free only (no sale, no paid access): psxrecomp's licence does not allow
commercial use.
