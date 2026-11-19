"""Copy the publishable part of this project into public_repo/ (e.g. for GitHub), and check it.

Usage: python tools/export_public.py

Only the files listed below are copied (an allow list, so nothing new slips in by accident). Never part of it:
the disc images and anything extracted or generated from them (extracted/, input/, generated/, build*/), the
Sony BIOS and its recompiled code, translation/ (holds the original Japanese script), Redeted's patch file,
the psxrecomp framework (its own project: BUILDING.md says where to get it) and route B (PersonaRecomp/).
game.toml loses the developer's disc path. Afterwards every file is scanned for Japanese text, large or binary
files, forbidden names and personal paths (a Windows user folder); any hit stops with an error.
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "public_repo")
TEMPLATES = os.path.join(ROOT, "release", "public")       # files that only exist in the public repo

FILES = [
    # the native PC build (route A)
    "PersonaRedeted/CMakeLists.txt", "PersonaRedeted/CMakePresets.json", "PersonaRedeted/build_msvc.cmd",
    "PersonaRedeted/build_release.cmd", "PersonaRedeted/build.ps1", "PersonaRedeted/build.sh",
    "PersonaRedeted/game.toml", "PersonaRedeted/seeds/functions.txt", "PersonaRedeted/seeds/patch_seeds.txt",
    # tools
    "tools/patch_framework.py", "tools/make_release.py", "tools/xdelta_apply.py", "tools/warp_points.py",
    "tools/export_public.py",
    # docs
    "research/DEBUG_MENU.md", "research/WARP_POINTS.md",
    # release texts
    "release/README_PLAYERS.txt", "release/CHANGELOG.md", "release/VERSION", "release/LICENSE_THIS_PROJECT.txt",
    "release/THIRD_PARTY_NOTICES.txt",
]
DIRS = ["PersonaRedeted/mods"]                                # every file in these
FROM_TEMPLATES = {"README.md": "README.md", "BUILDING.md": "BUILDING.md", "gitignore": ".gitignore",
                  "LICENSE": "LICENSE", "RELEASE_NOTES.md": "release/RELEASE_NOTES.md"}

FORBIDDEN = re.compile(r"\.(bin|cue|iso|chd|img|mcd|pst|xdelta|exe|dll|zip)$|SCPH\d+_|(^|/)(extracted|input|"
                       r"generated|translation|build[^/]*)/", re.I)
JAPANESE = re.compile("[\u3040-\u30ff\u4e00-\u9fff\uff00-\uffef]")
PERSONAL = re.compile(r"[A-Za-z]:[/\\]Users[/\\]", re.I)          # a developer's own paths


def sanitize_game_toml(text):
    return re.sub(r'(?m)^disc\s*=.*$',
                  '# disc = "C:/path/to/your Persona-TL-QoL patched .cue"   '
                  '(optional; without it the exe asks and remembers it in disc.cfg)', text)


def check(out):
    problems = []
    for d, _, files in os.walk(out):
        for f in files:
            full = os.path.join(d, f)
            rel = os.path.relpath(full, out).replace(os.sep, "/")
            if rel.startswith(".git/"):
                continue
            if FORBIDDEN.search(rel):
                problems.append(f"{rel}: forbidden kind of file")
            if os.path.getsize(full) > 2_000_000:
                problems.append(f"{rel}: larger than 2 MB")
            raw = open(full, "rb").read()
            if b"\0" in raw:
                problems.append(f"{rel}: binary file")
                continue
            text = raw.decode("utf-8", "replace")
            m = JAPANESE.search(text)
            if m:
                problems.append(f"{rel}: Japanese text ({m.group(0)!r} ...)")
            m = PERSONAL.search(text)
            if m:
                problems.append(f"{rel}: personal path ({m.group(0)} ...)")
    return problems


def main():
    if os.path.exists(OUT):                                   # keep a .git folder if the repo was set up there
        for name in os.listdir(OUT):
            if name != ".git":
                p = os.path.join(OUT, name)
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    copies = [(rel, rel) for rel in FILES]
    for d in DIRS:
        copies += [(f"{d}/{f}", f"{d}/{f}") for f in sorted(os.listdir(os.path.join(ROOT, d)))]
    copies += [(os.path.relpath(os.path.join(TEMPLATES, s), ROOT), dst) for s, dst in FROM_TEMPLATES.items()]
    for src, dst in copies:
        s, o = os.path.join(ROOT, src), os.path.join(OUT, dst)
        os.makedirs(os.path.dirname(o), exist_ok=True)
        if dst == "PersonaRedeted/game.toml":
            open(o, "w", encoding="utf-8", newline="\n").write(sanitize_game_toml(open(s, encoding="utf-8").read()))
        else:
            shutil.copyfile(s, o)
    problems = check(OUT)
    if problems:
        print("NOT publishable:\n  " + "\n  ".join(problems))
        return 1
    print(f"{len(copies)} files -> {OUT}; check passed (no game data, Japanese text or binaries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
