"""Put together the player download: release/Persona-PC/ and release/Persona-PC-v<version>.zip (+ .sha256.txt).

Usage: python tools/make_release.py        (after PersonaRedeted\\build_release.cmd)

Contents (no game data: the player supplies their own disc; the exe patches it with Redeted's xdelta):
  Persona.exe                  the release build (bundled OpenBIOS, static C runtime)
  game.toml                    PersonaRedeted/game.toml without the developer's disc path and BIOS profile
  bios/openbios.bin + licence  copied there by the build
  Persona-TL-QoL.xdelta        Redeted's translation + QoL patch (from the project root)
  README.txt                   for players (release/README_PLAYERS.txt, {VERSION} filled in)
  CHANGELOG.md                 release/CHANGELOG.md
  licenses/                    every licence the exe and the download fall under
The version comes from release/VERSION. The SHA-256 of the zip goes into <zip>.sha256.txt (for release notes).
"""
import hashlib
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROJ = os.path.join(ROOT, "PersonaRedeted")
BUILD = os.path.join(PROJ, "build_release")
DEPS = os.path.join(BUILD, "_deps")
OUT = os.path.join(ROOT, "release", "Persona-PC")
PATCH = os.path.join(ROOT, "Persona-TL-QoL.xdelta")

LICENSES = [   # (source, name in licenses/)
    (os.path.join(ROOT, "release", "LICENSE_THIS_PROJECT.txt"), "LICENSE_THIS_PROJECT.txt"),
    (os.path.join(PROJ, "psxrecomp", "LICENSE"), "psxrecomp_LICENSE_PolyForm-Noncommercial.txt"),
    (os.path.join(PROJ, "psxrecomp", "THIRD_PARTY_ATTRIBUTION.md"), "psxrecomp_THIRD_PARTY_ATTRIBUTION.md"),
    (os.path.join(PROJ, "psxrecomp", "bios", "OpenBIOS.LICENSE"), "OpenBIOS_LICENSE.txt"),
    (os.path.join(ROOT, "third_party", "redeted", "LICENSE"), "Redeted_translation_LICENSE_MIT.txt"),
    (os.path.join(DEPS, "sdl3-src", "LICENSE.txt"), "SDL3_LICENSE_zlib.txt"),
    (os.path.join(DEPS, "psx_libchdr-src", "LICENSE.txt"), "libchdr_LICENSE_BSD-3.txt"),
    (os.path.join(DEPS, "psx_libchdr-src", "deps", "lzma-25.01", "LICENSE"), "LZMA-SDK_LICENSE.txt"),
    (os.path.join(DEPS, "psx_zlib-src", "LICENSE"), "zlib_LICENSE.txt"),
    (os.path.join(ROOT, "release", "THIRD_PARTY_NOTICES.txt"), "THIRD_PARTY_NOTICES.txt"),
]


def release_game_toml():
    """The developer's game.toml without the disc path (the exe asks for the disc and remembers it in
    disc.cfg) and without the recompiler's BIOS profile (the release build has only OpenBIOS)."""
    out = []
    for line in open(os.path.join(PROJ, "game.toml"), encoding="utf-8"):
        if re.match(r"\s*(disc|bios_config)\s*=", line):
            continue
        if re.match(r"\s*window_title\s*=", line):
            line = 'window_title = "Megami Ibunroku Persona"\n'
        out.append(line)
    return "".join(out)


def main():
    exe = os.path.join(BUILD, "Megami_Ibunroku_Persona_Recompiled.exe")
    need = [exe, os.path.join(BUILD, "bios", "openbios.bin"), PATCH, os.path.join(ROOT, "release", "VERSION"),
            os.path.join(ROOT, "release", "README_PLAYERS.txt"),
            os.path.join(ROOT, "release", "CHANGELOG.md")] + [s for s, _ in LICENSES]
    missing = [p for p in need if not os.path.exists(p)]
    if missing:
        print("missing:\n  " + "\n  ".join(missing))
        print("(build first with PersonaRedeted\\build_release.cmd)")
        return 1
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "licenses"))
    shutil.copyfile(exe, os.path.join(OUT, "Persona.exe"))
    shutil.copytree(os.path.join(BUILD, "bios"), os.path.join(OUT, "bios"))
    shutil.copyfile(PATCH, os.path.join(OUT, os.path.basename(PATCH)))
    version = open(os.path.join(ROOT, "release", "VERSION"), encoding="utf-8").read().strip()
    readme = open(os.path.join(ROOT, "release", "README_PLAYERS.txt"), encoding="utf-8").read()
    open(os.path.join(OUT, "README.txt"), "w", encoding="utf-8", newline="\r\n").write(  # Notepad-friendly
        readme.replace("{VERSION}", version))
    shutil.copyfile(os.path.join(ROOT, "release", "CHANGELOG.md"), os.path.join(OUT, "CHANGELOG.md"))
    open(os.path.join(OUT, "game.toml"), "w", encoding="utf-8", newline="\n").write(release_game_toml())
    for src, name in LICENSES:
        shutil.copyfile(src, os.path.join(OUT, "licenses", name))

    zpath = os.path.join(ROOT, "release", f"Persona-PC-v{version}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for d, _, files in os.walk(OUT):
            for f in files:
                full = os.path.join(d, f)
                z.write(full, os.path.join("Persona-PC", os.path.relpath(full, OUT)))
    sha = hashlib.sha256(open(zpath, "rb").read()).hexdigest().upper()
    open(zpath + ".sha256.txt", "w", encoding="utf-8").write(f"{sha}  {os.path.basename(zpath)}\n")
    print(f"{OUT}\n{zpath} ({os.path.getsize(zpath) / 1e6:.1f} MB)\nSHA-256 {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
