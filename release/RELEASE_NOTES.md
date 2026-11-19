# Persona PC v1.0.0

First release: **Megami Ibunroku Persona** as a native Windows program, in English with Redeted's translation
and quality-of-life patch.

**You need your own disc image** of Megami Ibunroku Persona (Japan, SLPS-00500, first release). No game data
is included.

## How to play

1. Download `Persona-PC-v1.0.0.zip` and unpack it anywhere you can write to (not Program Files).
2. Run `Persona.exe` (Windows SmartScreen: **More info → Run anyway**; the exe is not code-signed).
3. Choose your disc image the first time. The original Japanese disc is patched automatically into a copy.

## What's in it

- English translation + QoL patch by Redeted (their `Persona-TL-QoL.xdelta` is included and applied on first
  start)
- Runs on the bundled OpenBIOS – no PlayStation BIOS, no extra runtimes needed
- Options menu (F10): screen mode, resolution up to 4x, picture options, CRT colour, scanlines, volume, skip
  movies, keyboard and controller rebinding
- Controllers work out of the box, keyboard and controller at the same time
- Save states (F7), debug menu with warps and battle cheats (F9)

## Check your download

SHA-256 of `Persona-PC-v1.0.0.zip`: see `Persona-PC-v1.0.0.zip.sha256.txt` attached to this release
(PowerShell: `Get-FileHash Persona-PC-v1.0.0.zip`).

## Credits

Native PC port: Zacharias Tzifopoulos, with the help of Claude (Anthropic). Translation and QoL patch: Redeted. Recompiler: psxrecomp by Matthew Stan. BIOS: OpenBIOS (PCSX-Redux). Full
list and licences in the `licenses` folder of the download.

Unofficial, non-commercial fan project, not affiliated with ATLUS or SEGA. Free sharing only.
