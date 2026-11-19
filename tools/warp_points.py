"""List the places the game itself puts the party (door / entrance records), for the F9 debug menu warp.

  python tools/warp_points.py [extracted dir]     default: PersonaRedeted/extracted (the patched disc)

Writes
  research/WARP_POINTS.md              every arrival point, readable (names, map / floor / X / Y / direction)
  PersonaRedeted/mods/warp_points.h    the same as a C table for the debug menu's WARP LIST page

Sources (details: research/DEBUG_MENU.md):
  * dungeon door records, D0x/Dxx.BIN: per floor a list of 18-byte records {x, y, type, -, u16 story bit,
    u16 dest[2], floor, x, y, dir, ...} ending with a zero record. type 0 = other dungeon / floor, 1 = story
    event, 2 = overworld (2D map), 3 = movie / special. dest[1] is used once the story bit is set.
    Pointer: word (c0+c1+c2+c3+1+floors+floor) of the Dxx.BIN offset table, c* = count bytes of Dxx M.BIN.
  * overworld entrance records, S2D.BIN: table 0x800B0A5C[2D map] -> pointers to 20-byte records
    {-, -, type, chapter mask, u16 dest, -, -, floor, dir, x, y, ...}; type 0 = 2D map, 1 = dungeon, 2 = story event.
A destination taken from these records is a tile the game itself places the party on, so it cannot be inside a wall.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "third_party", "redeted", "tools"))
import etext   # noqa: E402  (Redeted's glyph table: decodes the English dungeon names of the patched disc)

OVL = 0x800643C4
S2D_ENTRANCES = 0x800B0A5C
DIRS = "N E S W".split()   # record direction value, as the game stores it (meaning not verified)
FW = {chr(0xFF01 + i): chr(0x21 + i) for i in range(94)}
FW["　"] = " "


# Story context per dungeon file (D<n>.BIN). The ROUTE grouping and the order follow the story event numbers
# each area's doors start (they run in story order, see "Areas in story order" in the output) and which version
# of the overworld has an entrance; the place names are the Japanese names of the map files / Redeted's glossary.
# The descriptions are general knowledge of the game, not checked in game: treat them as a guide.
COMMON, SEBEC, SNOW = "Start (both routes)", "SEBEC route", "Snow Queen quest"
AREAS = {
    0x00: (COMMON, "St. Hermelin High School (prologue)", "the school at the very start of the game"),
    0x24: (COMMON, "St. Hermelin High School", "the school in the early story, after the prologue"),
    0x02: (COMMON, "Mikage General Hospital", "the hospital, earlier version (first visit)"),
    0x03: (COMMON, "Mikage General Hospital", "the hospital, later version"),
    0x04: (COMMON, "Mikage police station", "has the holding cell"),
    0x01: (COMMON, "Joy-dori", "shopping street (Peace Diner, shops); a hub, open on almost every overworld version"),
    0x05: (COMMON, "Mikage Sun Mall", "shopping mall; a hub, open on every overworld version"),
    0x06: (COMMON, "Mikage subway station", "the subway (boss: Yog-Sothoth Jr.)"),
    0x07: (COMMON, "Abandoned factory tunnel", "underground passage on the way to SEBEC"),
    0x08: (COMMON, "SEBEC building", "the SEBEC company building, 1F-5F"),
    0x09: (COMMON, "SEBEC underground lab", "below SEBEC (the Deva System)"),
    0x0A: (SEBEC, "St. Hermelin High School", "the school later in the story (two versions of 1F-3F)"),
    0x0B: (SEBEC, "St. Hermelin High School (changed)", "the school in its changed, otherworldly state"),
    0x0D: (SEBEC, "Mikage subway (west / east)", "the subway again, later overworld versions"),
    0x0E: (SEBEC, "Black Market", "on the overworld version with the Castle and the Haunted Mansion (map 4)"),
    0x0F: (SEBEC, "Kama Palace", "10 basement floors, reached from the Black Market"),
    0x11: (SEBEC, "Lost Forest", "the forest"),
    0x15: (SEBEC, "Lost Forest (inner part)", "the deeper part of the forest"),
    0x12: (SEBEC, "Mana Castle", "the castle, 1F-5F"),
    0x13: (SEBEC, "Haunted Mansion", "on overworld map 4"),
    0x14: (SEBEC, "Deva Yuga", "Kandori's castle, 1F-6F"),
    0x16: (SEBEC, "Araya cave (Araya Shrine)", "9 basement floors; entrance only on overworld map 6"),
    0x0C: (SEBEC, "Mikage ruins", "8 basement floors; entrance on overworld maps 3, 5 and 6 (route not certain)"),
    0x17: (SEBEC, "Avidya world", "the last area of the SEBEC route"),
    0x23: (SEBEC, "Avidya world", "second file of the same area"),
    0x18: (SNOW, "Ice Castle 1F", "the Snow Queen's castle, first floor"),
    0x19: (SNOW, "Demon Mountain", "1F-7F"),
    0x1A: (SNOW, "Tower of Hypnos", "1F-8F"),
    0x1B: (SNOW, "Anti-Dream world", "one floor, events between Hypnos and Nemesis"),
    0x1C: (SNOW, "Tower of Nemesis", "1F-8F"),
    0x1D: (SNOW, "Tower of Thanatos", "1F-7F"),
    0x1E: (SNOW, "Tartarus", "one floor, events after Thanatos"),
    0x1F: (SNOW, "Ice Castle 2F-4F", "the Snow Queen's castle, climbing up"),
    0x21: (SNOW, "Ice Castle 5F-8F", ""),
    0x22: (SNOW, "Ice Castle 9F-11F", "the top of the castle"),
}
OVERWORLD = {   # 2D map file -> when it is used (SLPS 0x80015784 swaps 0 -> 1 -> 2 and 3 -> 5 -> 6 by story flags)
    0: "Mikage-cho; the game shows version 0, 1 or 2 by story progress",
    1: "Mikage-cho, after story flag 0x14", 2: "Mikage-cho, after story flag 0x27",
    3: "Mikage-cho, SEBEC route; the game shows version 3, 5 or 6 by story progress",
    4: "Mikage-cho, SEBEC route (Castle, Haunted Mansion, Black Market)",
    5: "Mikage-cho, SEBEC route, after flag 0x67", 6: "Mikage-cho, SEBEC route, after flag 0x6E (Araya)",
}
STORY_EVENT_MAX = 500   # door scripts above this look like shop / room messages, not story (they do not follow the order)


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def floor_counts(ext):
    slps = open(os.path.join(ext, "SLPS_005.00"), "rb").read()
    o = 0x8004DA08 - (0x80010000 - 0x800)
    return list(slps[o:o + 0x30])


def dungeon(ext, n):
    d = os.path.join(ext, f"D0{n >> 3}")
    return (open(os.path.join(d, f"D{n:02X}M.BIN"), "rb").read(),
            open(os.path.join(d, f"D{n:02X}.BIN"), "rb").read())


def floor_name(m, f):
    off = u32(m, 8 + 4 * f)
    s = "".join(etext.glyph.get(struct.unpack_from("<H", m, off + 2 * i)[0], "?") for i in range(10))
    return " ".join("".join(FW.get(c, c) for c in s).split())


def doors(m, d, f):
    hs = u32(m, 0)
    c = m[hs:hs + 8]
    p = u32(d, 4 * (c[0] + c[1] + c[2] + c[3] + 1 + c[4] + f))
    out = []
    while len(out) < 64:
        r = d[p:p + 18]
        # the list has no count of its own: it ends where the next structure starts (a mostly zero record,
        # sometimes with a leading word); real records have x/y < 64, type < 4 and byte 3 = 0
        if r[0] >= 64 or r[1] >= 64 or r[2] > 3 or r[3] or not any(r[2:16]):
            break
        out.append(dict(x=r[0], y=r[1], type=r[2] & 7, bit=struct.unpack_from("<H", r, 4)[0],
                        dest=struct.unpack_from("<2H", r, 6), floor=r[10], dx=r[11], dy=r[12], dir=r[13] & 7))
        p += 18
    return out


def s2d_entrances(ext):
    s = open(os.path.join(ext, "S2D.BIN"), "rb").read()
    ok = lambda p: OVL <= p < OVL + len(s)   # noqa: E731
    res = {}
    for m in range(7):
        t = u32(s, S2D_ENTRANCES + 4 * m - OVL)
        lst = []
        for i in range(256):
            r = u32(s, t + 4 * i - OVL)
            if not ok(r):
                continue
            rec = s[r - OVL:r - OVL + 20]
            if rec[2] > 7:
                break
            if rec[2] in (0, 1, 2):
                lst.append(dict(id=i, type=rec[2], mask=rec[3], dest=struct.unpack_from("<H", rec, 4)[0],
                                floor=rec[8], dir=rec[9], x=rec[10], y=rec[11]))
        res[m] = lst
    return res


def main(argv):
    ext = os.path.abspath(argv[1]) if len(argv) > 1 else os.path.join(ROOT, "PersonaRedeted", "extracted")
    counts = floor_counts(ext)
    names = {}                       # (dungeon, floor) -> name
    dng_doors = {}
    for n, fc in enumerate(counts):
        if not fc or fc >= 0x25:
            continue
        try:
            m, d = dungeon(ext, n)
        except FileNotFoundError:
            continue
        for f in range(fc):
            names[(n, f)] = floor_name(m, f) or f"Dungeon {n:02X}"
            dng_doors[(n, f)] = doors(m, d, f)
    s2d = s2d_entrances(ext)

    # arrival points: (kind, map, floor, x, y, dir) -> set of "how you get there"
    arrive = {}
    outside = {}                     # 2D arrival point -> dungeon whose door leads there (first one found)
    # where a new game starts (SLPS 0x800114F8: map 0, X 0x68, Y 0x69, direction 0)
    arrive[("2D", 0, 0, 0x68, 0x69, 0)] = ["new game start (SLPS 0x800114F8)"]

    def add(key, how):
        arrive.setdefault(key, []).append(how)

    for (n, f), lst in dng_doors.items():
        for r in lst:
            for k, dest in enumerate(dict.fromkeys(r["dest"])):
                via = f"door at {r['x']},{r['y']} of {names[(n, f)]} [{n:02X} F{f}]" + (" (later story)" if k else "")
                if r["type"] == 2 and (r["dx"] or r["dy"]):
                    add(("2D", dest, 0, r["dx"], r["dy"], r["dir"]), via)
                    outside.setdefault(("2D", dest, 0, r["dx"], r["dy"], r["dir"]), n)
                elif r["type"] == 0 and (dest, r["floor"]) in names:
                    add(("3D", dest, r["floor"], r["dx"], r["dy"], r["dir"]), via)
    for m2, lst in s2d.items():
        for r in lst:
            if r["type"] == 1 and (r["dest"], r["floor"]) in names:
                add(("3D", r["dest"], r["floor"], r["x"], r["y"], r["dir"]), f"entrance {r['id']} on 2D map {m2}")
            elif r["type"] == 0:
                add(("2D", r["dest"], 0, r["x"], r["y"], r["dir"]), f"path {r['id']} on 2D map {m2}")

    def label(k, short=False):
        kind, mp, fl, x, y, dr = k
        if kind == "3D":
            return names[(mp, fl)]
        froms = list(dict.fromkeys(h.split(" of ")[-1].split(" [")[0] for h in arrive[k] if " of " in h))
        if short:
            froms = froms[:1]
        if k == ("2D", 0, 0, 0x68, 0x69, 0):
            return "New game start"
        return ("Outside " + "/".join(froms)) if froms else f"2D map {mp}"

    keys = sorted(arrive, key=lambda k: (k[0] != "2D", k[1], k[2], k[3], k[4]))

    # story event numbers each area's doors start, and which overworld versions have an entrance to it
    events, entrances = {}, {}
    for (n, f), lst in dng_doors.items():
        for r in lst:
            if r["type"] == 1:
                events.setdefault(n, set()).update(e for e in r["dest"] if 0 < e < STORY_EVENT_MAX)
    for m2, lst in s2d.items():
        for r in lst:
            if r["type"] == 1:
                entrances.setdefault(r["dest"], set()).add(m2)

    def story(k):
        kind, mp = k[0], k[1]
        if kind == "3D":
            route, place, _ = AREAS.get(mp, ("?", f"Dungeon {mp:02X}", ""))
            return f"{route}: {place}"
        if k == ("2D", 0, 0, 0x68, 0x69, 0):
            return "Start of the game (town)"
        if k in outside:
            route, place, _ = AREAS.get(outside[k], ("?", "?", ""))
            return f"Town, outside {place} [{route}]"
        return "Town"

    md = ["# Warp points (generated by tools/warp_points.py - do not edit)", "",
          "Every place below is a spot the game itself puts the party on (taken from door / entrance records), "
          "so warping there with the F9 menu should never leave you inside a wall. The F9 menu's WARP LIST page "
          "has the same list in the same order (# = the number the menu shows top right); the WARP page takes the "
          "numbers by hand.", "",
          "**Story point** says where the place belongs in the game. The story has a common start, then splits "
          "into two routes: the **SEBEC route** (the main story) and the **Snow Queen quest** (set in the school). "
          "Warping into a later part of the story than your save does not move the story forward: events, doors "
          "and party members still follow your save's story flags, so a place can look empty or have doors that "
          "do nothing. The section *Areas in story order* below explains each area.", "",
          "* **2D** = overworld map (S2D). Map numbers 0-6 are the overworld map files 2DLTS0n; the game swaps "
          "0 -> 1 -> 2 and 3 -> 5 -> 6 by itself as the story goes on, so the numbers below can show a different "
          "stage of the same town. X/Y = 0-199.",
          "* **3D** = first-person area / dungeon (DNG). Map = dungeon file D<map>.BIN (hex), floor 0 = first floor.",
          "* Dir = the direction value the game stores (0-3); which way it faces was not checked.",
          "* A warp only starts from the overworld or from a first-person area (not during story scenes, battles "
          "or menus).", "",
          "| # | Name | Story point | Kind | Map | Floor | X | Y | Dir | Reached by |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for i, k in enumerate(keys):
        kind, mp, fl, x, y, dr = k
        hows = arrive[k]
        md.append(f"| {i + 1} | {label(k)} | {story(k)} | {kind} | {mp if kind == '2D' else f'{mp:02X} ({mp})'} | "
                  f"{fl if kind == '3D' else '-'} | {x} | {y} | {dr} | {'; '.join(hows[:3])}"
                  f"{f' (+{len(hows) - 3} more)' if len(hows) > 3 else ''} |")

    md += ["", "## Overworld map versions", "",
           "All seven are the town of Mikage-cho. The game picks the version from the story flags; warping to map 0 "
           "or 3 lands on whichever stage your save has reached.", "",
           "| 2D map | When | Area entrances on it |", "|---|---|---|"]
    for m2, note in OVERWORLD.items():
        ent = sorted(n for n, ms in entrances.items() if m2 in ms)
        md.append(f"| {m2} | {note} | " + ", ".join(AREAS.get(n, ('', f'{n:02X}', ''))[1] for n in ent) + " |")

    md += ["", "## Areas in story order", "",
           "Sorted by the first story event number the area's doors start (the game numbers its story scripts in "
           "story order, so this is a good guide to when you get there; scripts above 500 are left out, they look like "
           "shop and room messages). The areas at the end start no story scripts below 500.", "",
           "| Map (hex) | Route | Place | What it is | Floors | Story events (first-last) | Entrance on 2D map |",
           "|---|---|---|---|---|---|---|"]
    order = sorted((n for n, fc in enumerate(counts) if (n, 0) in names),
                   key=lambda n: (min(events.get(n) or {9999}), n))
    for n in order:
        route, place, note = AREAS.get(n, ("?", f"Dungeon {n:02X}", ""))
        ev = sorted(events.get(n, ()))
        evs = f"{ev[0]}-{ev[-1]}" if len(ev) > 1 else (str(ev[0]) if ev else "-")
        fl = ", ".join(f"F{f}: {names[(n, f)]}" for f in range(counts[n]))
        md.append(f"| {n:02X} ({n}) | {route} | {place} | {note} | {fl} | {evs} | "
                  f"{', '.join(map(str, sorted(entrances.get(n, ())))) or '-'} |")
    out_md = os.path.join(ROOT, "research", "WARP_POINTS.md")
    open(out_md, "w", encoding="utf-8", newline="\n").write("\n".join(md) + "\n")

    h = ["/* generated by tools/warp_points.py - do not edit (see research/WARP_POINTS.md) */", "#pragma once",
         "/* from_dungeon: for a 2D point, the dungeon (D<n>.BIN) whose door leads there; 0xFF = none */",
         "typedef struct { const char* name; unsigned char is_3d; unsigned short map; unsigned char floor, x, y, dir, "
         "from_dungeon; } WarpPoint;", "static const WarpPoint k_warp_points[] = {"]
    for k in keys:
        kind, mp, fl, x, y, dr = k
        nm = "".join(c if 32 <= ord(c) < 127 and c != '"' and c != "\\" else "?" for c in label(k, True)).upper()[:28]
        h.append(f'    {{"{nm}", {int(kind == "3D")}, {mp}, {fl}, {x}, {y}, {dr}, {outside.get(k, 0xFF)}}},')
    h += ["};", f"#define WARP_POINT_COUNT {len(keys)}", ""]
    out_h = os.path.join(ROOT, "PersonaRedeted", "mods", "warp_points.h")
    open(out_h, "w", encoding="utf-8", newline="\n").write("\n".join(h))
    print(f"{len(keys)} warp points -> {out_md}, {out_h}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
