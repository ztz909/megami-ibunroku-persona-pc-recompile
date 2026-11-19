# Megami Ibunroku Persona – native PC version

The 1996 PlayStation RPG **Megami Ibunroku Persona** (the original *Revelations: Persona*), recompiled into a
native Windows program with [psxrecomp](#credits) and playable in English thanks to
[Redeted](#credits)'s fan translation and quality-of-life patch.

It is not an emulator: the game's MIPS code was translated to C and compiled for your PC.

> **No game data is included.** You need your own copy of the game (Japan, SLPS-00500, first release).

## Download and play

1. Download the latest `Persona-PC-v*.zip` from **[Releases](../../releases)** and unpack it anywhere you can
   write to (not Program Files).
2. Run `Persona.exe`. If Windows says "Windows protected your PC", click **More info → Run anyway** (the exe is
   not code-signed).
3. The first time, choose your disc image (`.cue` or `.bin`). The original Japanese disc is patched with the
   English translation automatically, into a copy; your file is not changed. The choice is remembered.

Requirements: Windows 10/11 64-bit, OpenGL graphics. No PlayStation BIOS needed (the free OpenBIOS is
included), no extra runtimes.

## Features

- English translation and QoL patch by Redeted, applied automatically on first start.
- **Options menu (F10):** windowed / borderless / fullscreen, internal resolution up to 4x, smooth picture,
  texture filtering, steadier 3D (geometry correction), CRT colour models, scanlines, volume, skip movies.
- **Controls:** keyboard and any controller at the same time, plug and play; rebind keys and buttons in the
  options menu; both menus work with a controller (Guide / Select+L1+R1 for options).
- **Save states (F7)** next to the normal memory-card saves.
- **Debug menu (F9):** warp to 268 named places, back to title, the game's own hidden battle cheats.

Default keyboard: arrows move, X Cross, S Circle, Z Square, A Triangle, Q/W/E/R L1/R1/L2/R2, Enter Start,
Right Shift Select. Alt+Enter fullscreen, keypad +/- volume.

## Which disc?

| Your disc image | Works? |
|---|---|
| Original Japanese release, SLPS-00500, `.bin` 699,705,888 bytes | yes – patched automatically |
| Already patched with Redeted's `Persona-TL-QoL.xdelta` (714,083,664 bytes) | yes |
| "Rev 1" release, translation-only patch, other games | no – the exe explains and asks again |

## Building from source

See [BUILDING.md](BUILDING.md). You need your own patched disc image and the psxrecomp CLI.

## Legal

This is an unofficial, non-commercial fan project, not affiliated with or endorsed by ATLUS or SEGA.
Megami Ibunroku Persona © 1996 ATLUS. The repository and the downloads contain no game data; the exe contains
code recompiled from the game, and only runs with a disc image you supply. Please support the official
releases.

The download may only be shared for free: psxrecomp's licence (PolyForm Noncommercial 1.0.0) does not allow
commercial use.

## Credits

- **Zacharias Tzifopoulos** – this native PC port: recompilation setup, options and debug menus, controller
  support, automatic disc patching.
- **Claude** (Anthropic's AI assistant, in Claude Code) – helped with the reverse engineering, code and docs.
- **Redeted** – the English translation and quality-of-life patch (MIT). The download includes their
  `Persona-TL-QoL.xdelta` unchanged.
- **psxrecomp** by Matthew Stan – the PlayStation static recompiler and runtime (PolyForm Noncommercial 1.0.0).
- **OpenBIOS** from the PCSX-Redux project (MIT).
- SDL3, libchdr, LZMA SDK, zlib, zstd, miniz – see `release/THIRD_PARTY_NOTICES.txt`.

## License

This project's own code (the menus, disc patcher and tools): MIT, see [LICENSE](LICENSE). The built exe as a
whole also falls under psxrecomp's noncommercial licence.
