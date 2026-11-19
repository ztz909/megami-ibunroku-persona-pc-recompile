# Building

The exe is generated from the game's own program, so building it needs **your own disc image**, patched with
Redeted's `Persona-TL-QoL.xdelta`. Nothing from the game is in this repository.

## What you need

- Windows 10/11 64-bit, Visual Studio 2022 or newer with "Desktop development with C++", CMake and Ninja.
  (`PersonaRedeted/build_msvc.cmd` and `build_release.cmd` call Visual Studio's `vcvars64.bat`; adjust the path
  in them to your installation.)
- Python 3.10 or newer.
- The **psxrecomp CLI for Windows** (`psxrecomp-cli-windows-x86_64`): its `framework/` folder and its tools
  `libexec/psxrecomp-game.exe` and `libexec/psxrecomp-bios.exe`.
- **mkpsxiso** (`dumpsxiso.exe`) to extract the game program from the disc image.
- Your disc image of Megami Ibunroku Persona (SLPS-00500, first release) and Redeted's
  `Persona-TL-QoL.xdelta` (from their releases).
- For packaging only: Redeted's repository cloned into `third_party/redeted/` (its licence goes into the
  download) and `Persona-TL-QoL.xdelta` in the repository root.

## Steps

All paths are relative to the repository root.

1. **Patch the disc** (any xdelta tool, or the included one):

   ```
   python tools/xdelta_apply.py "original.bin" Persona-TL-QoL.xdelta "Persona-TL-QoL.bin"
   ```

   It must print `CRC32 7C27C06C`. Make a `.cue` next to it:

   ```
   FILE "Persona-TL-QoL.bin" BINARY
     TRACK 01 MODE2/2352
       INDEX 01 00:00:00
   ```

2. **Extract the game program** from the patched image and put it where the recompiler expects it:

   ```
   dumpsxiso -x PersonaRedeted/extracted "Persona-TL-QoL.bin"
   copy PersonaRedeted\extracted\SLPS_005.00 PersonaRedeted\input\SLPS_005.00
   ```

3. **Set up the framework:** copy the psxrecomp CLI's `framework/` folder to `PersonaRedeted/psxrecomp/`, then
   add this project's menu, controller and disc hooks to it:

   ```
   python tools/patch_framework.py PersonaRedeted/psxrecomp
   ```

4. **Recompile the game** (writes `PersonaRedeted/generated/`; the function list is
   `PersonaRedeted/seeds/functions.txt`):

   ```
   <psxrecomp-cli>/libexec/psxrecomp-game.exe --config game.toml --project-root PersonaRedeted
   ```

   (run from inside `PersonaRedeted/`). If it asks for the disc, set `disc = "..."` in
   `PersonaRedeted/game.toml` to your patched `.cue`.

5. **Recompile OpenBIOS** (the free BIOS the release uses), from inside `PersonaRedeted/psxrecomp/`:

   ```
   <psxrecomp-cli>/libexec/psxrecomp-bios.exe --config bios/OpenBIOS.toml
   ```

6. **Build:** `PersonaRedeted\build_release.cmd` → `PersonaRedeted/build_release/`.
   (`build_msvc.cmd` is the developer build: it expects a retail BIOS recompiled from your own dump with
   `psxrecomp-bios --config bios/SCPH1001.toml --rom <your SCPH1001.BIN>`.)

7. **Package:** `python tools/make_release.py` → `release/Persona-PC/` and `release/Persona-PC-v<version>.zip`
   with its SHA-256. The version is in `release/VERSION`, the player README in `release/README_PLAYERS.txt`.

## Where things are

| | |
|---|---|
| `PersonaRedeted/mods/` | the C code built into the exe: options menu (F10), debug menu (F9), disc check + xdelta patcher, shared drawing |
| `tools/patch_framework.py` | adds host menus, host settings, controller input, key capture and the disc hook to psxrecomp |
| `tools/xdelta_apply.py` | reference xdelta3 patcher (the C version is `mods/xdelta_decode.c`) |
| `tools/warp_points.py` | makes `mods/warp_points.h` and `research/WARP_POINTS.md` from the patched disc's map files |
| `tools/make_release.py` | the player download |
| `tools/export_public.py` | how this public repository is cut from the full working copy (allow list + checks) |
| `research/` | notes on the game's debug features, main loop, warping and door data |
