# Debug features in the game, and our F9 debug menu

Found 2026-10-31 by reading the Japanese S2D.BIN / BTLP.BIN with capstone (no emulator run). All
addresses below are the same on the Redeted-patched disc (checked byte for byte where code is used).

## The developers' overworld debug menu (S2D.BIN, switched off)
- Strings at S2D file offset 0x7B8.. (RAM 0x80064B7C..): `ADV MODE`, `BATTLE`, `3D DNG`, `2D MAP`,
  `MAIN INFO`, `SOUND CHECK`, `MAP EDIT`, and the scene-change items `TO 2D`, `TO 3D`, `TO ADV`, `TO BTL`,
  `MAP NUM`, `FLOOR NUM`, `DIRECTION`, `X POSITION`, `Y POSITION`, `EVENT BIT`, `ENC`, `EXIT`
  (label pointer table 0x800A55A4).
- Page variable `0x800A5438` (0 = off, 1-4 = debug pages); page handlers via table 0x80064E9C
  (dispatcher at 0x8008A58C, inside the per-frame function 0x8008A438). Page input handlers via the
  5-way switch at 0x8008F978; the scene-change page's input is 0x8008C288 (12 items, table 0x80064F1C).
- **The switch:** the overworld input code at 0x8008DD94 opens the next page when the pressed buttons
  match the halfword at `0x800B15FC`; the halfword at `0x800B15F8` toggles `0x800B161C` the same way.
  Both are 0 in the retail game, so nothing ever matches. Setting them (game's own pad-bit format,
  not worked out yet) should bring the real menu back.
- Scene-change semantics (handlers at 0x8008C2BC..0x8008C424):
  | item | effect |
  |---|---|
  | TO 2D / TO 3D / TO BTL | `0x800A540C` (s16 next mode) = 0 / 1 / 2, `0x800B6660` = 0 |
  | TO ADV | 0x80098A74(map number) (sets 0x800A8A28 if the number is in an 8-entry list at 0x800A8A08), then next mode = 3 |
  | MAP NUM | u16 `0x801F5350` (0-0xFFFF) |
  | X / Y POSITION | u8 `0x801F5352` / `0x801F5353` (0-199) |
  | FLOOR NUM | u8 `0x801F5354` |
  | DIRECTION | u8 `0x801F5355` |
  | EVENT BIT | editor at 0x8008C0E0 (not traced) |
  | ENC | toggles u32 `0x800B1620` |
  | EXIT | next page |
- The S2D main loop (entry 0x8008A0E0) runs while `0x800A540C` == -1 (check at 0x8008A408).
- SLPS_005.00 has a table of {file name, entry point} records at 0x8001004C..: DNG 0x80064D50,
  BTLP 0x8007FF28, S2D 0x8008A0E0, ADV 0x8007DCC8, CASINO 0x80065DB0, NAME 0x800643C8.
- Every overlay starts with a u32 id at 0x800643C4: 4 DNG, 5 BTLP, 6 S2D, 7 ADV, 8 CASINO, 9 NAME.

## The SLPS main loop (0x8001128C, loop head 0x800113F0)
- Next state = s32 `0x80055C5C` (gp 0x80055BF4 + 0x68); jump table 0x80010118 indexed by state + 1:
  -1 title (logos, OPEN.EXE; on every visit after the first it also stops sound and clears 0x801F0000-0x801F7FFF),
  0 DNG, 1 BTLP, 2 S2D, 3 ADV, 4 CASINO, 5 NAME, 6 movie (MOVIE.EXE id `0x801F15C2`; >= 0x30 END.EXE), then
  the state in `0x801F15C4`. The loaded module sets 0x80055C5C before it returns.
- Title choice `0x801F15B8` (table 0x80010138): 4 = continue (position from the save at 0x801F15A0.. copied to
  0x801F5350.., then DNG).
- Before a module exits it calls the loader of the next one: 0x800150AC dungeon (D0x/Dxx.BIN, DxxS, DxxM by the
  hex map number; copies 0x801F5350.. to 0x801F15A0..; invalid map -> 0, floor >= count -> 0; floor counts u8[]
  at 0x8004DA08), 0x80015784 2D map (2D/2DLTS0<map>.BIN, map 0 -> 1 -> 2 and 3 -> 5 -> 6 by story flags 0x14,
  0x27, 0x67, 0x6E; no file above 6), 0x80015940 story, 0x80015CA8 battle.
- 3D position (also what a save keeps): `0x801F15A0` u16 map, `15A2` u16 floor, `15A4` u8 X, `15A6` u8 Y,
  `15A7` u8 direction (from the target direction through table 0x8004DA38). 0x801F5350.. is the *target*.

## Leaving a 3D area (DNG.BIN)
- Main loop 0x80065240: `jal 0x80067D40` (one step; nonzero = leave) ... exit 0x80065938 (returns to SLPS).
- On a door tile 0x80067D40 calls 0x8006C90C: finds the door record at the party's X/Y, sets 0x80055C5C from
  table 0x80099E74 by type (0 DNG, 1 story, 2 S2D, 3 movie) and the target 0x801F5350.., then takes one of its exit
  paths: 0x80068204 to S2D, 0x8006833C another dungeon, 0x800680F4 story event (0x8006826C = same dungeon, floor
  change in place); all end at the epilogue 0x80068730 with -1.
- The F9 menu writes the target + 0x80055C5C and overwrites 0x80067D64 (right after the step function's prologue,
  originally `lw v0, 0x1580(a1)`) with `j <exit path>`; the next step takes that exit, returns -1 and the main loop
  leaves. The words are gone when the next module loads over the dungeon. (Scripted walks also call 0x80067D40;
  a warp picked during one would exit from there.)
- First attempt (2026-10-31, failed in game: black screen, no music): the patch overwrote the main loop itself at
  0x80065240..0x8006525C. The game is paused inside 0x800659B4, called from 0x80065250, so it returned to
  0x80065258 = the middle of the patch and jumped straight to the loop exit: no fade, and the 2D map's files were
  never requested. Seen in build/overlay_captures.json.d (executed PCs: 0x80065258, then 0x80065938; the exit path
  0x80068204 never ran). Never patch code that a paused call returns into.
- Door records (tools/warp_points.py): Dxx.BIN starts with an offset table; the count bytes c0..c5 sit at the start
  of the DxxM.BIN header block (offset = its first word). Floor f's doors: word (c0+c1+c2+c3+1+floors+f) + file.
  18 bytes each {x, y, type, 0, u16 story bit, u16 target[2], floor, x, y, direction, ...}; no count, the list ends
  where the next structure starts. Most building exits are type 1 (a story script does the move).
- S2D entrances: 0x800B0A5C[2D map] -> pointer array indexed by the tile's trigger id -> 20-byte records
  {-, -, type, chapter mask, u16 target, -, -, floor, direction, X, Y, cond ptr, alt ptr}; type 0 2D move, 1 dungeon,
  2 story event, 3 area name (u32 name pointer), 4 other.
- Back to title: from S2D the 2D->2D change (next mode 0) with 0x80055C5C = -1; from DNG the to-S2D exit path with
  -1. Both run the 2D loader first, so the target map must be 0-6.

## Battle debug flags (BTLP.BIN + SLPS)
- 32 flag bytes at `0x8004E284` (in SLPS, resident). The battle debug menu (0x800A9600, names via
  pointer table 0x800D265C) toggles them; battle code reads flags 0-14.
- Names (Redeted's English of the BTLP strings): 0 always escape, 1 never die, 2 always kill,
  3 enemies don't move, 4 SP doesn't drop, 5 ignore Persona M.Atk/M.Def, 6 no bad status, 7 fix the group,
  8 no game over, 9 "if it becomes 1, don't", 10 demons only defend, 11 "don't run away!!",
  12 "meat dumplings", 13 no event battles, 14 "karinto" (9, 11, 12, 14: developer jokes, effect unknown).

## Our F9 menu (route A: PersonaRedeted/mods/debug_menu.c)
- psxrecomp has no menu API, so `tools/patch_framework.py` adds a small generic one: F9 opens the menu of
  a trusted plugin, the game pauses (same pause loop as the F7 save-state menu), keys go to the plugin,
  its 640x480 image is drawn over the frame (OpenGL renderer only).
- Pages: WARP LIST (back to title, go to 2D map, the named points of research/WARP_POINTS.md), WARP
  (edit map / floor / X / Y / direction, then go to 2D map, 3D dungeon, story event or battle, plus the ENC
  flag) and BATTLE CHEATS (the 15 flags). On the 2D map a warp writes exactly what the scene-change page
  writes; in a 3D area it uses the door-exit paths above. Not from story scenes, battles or menus.
- Verified in game 2026-10-31 (after the step-function fix): warps work. Not checked separately: what
  "TO BTL" fights.

## Ideas for later
- Warp from story scenes (ADV writes 0x80055C5C at 0x8007E7F8; its loop exit not traced).
- Load a memory card save directly (the title's continue path copies the save's position from 0x801F15A0..).
- Unlock the original menu instead/as well (set 0x800B15FC/0x800B15F8 when S2D is loaded).
- EVENT BIT editor (0x8008C0E0) to set story flags.
