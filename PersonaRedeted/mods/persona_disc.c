/* persona_disc.c - which disc image the exe runs, and patching the original one (route A release).
 *
 * The exe is recompiled from the disc patched with Redeted's Persona-TL-QoL.xdelta, so it needs exactly that
 * image. Every image the runtime is about to use goes through persona_disc_prepare() first (disc hook added by
 * tools/patch_framework.py):
 *   - already patched (714,083,664 bytes)      -> used as it is
 *   - the original first release (699,705,888)  -> patched once with Persona-TL-QoL.xdelta (shipped next to
 *                                                  the exe) into <exe dir>/disc/, the original is not touched
 *   - anything else                              -> explained, and the file picker opens again
 * The runtime remembers the image it ends up with in disc.cfg next to the exe.
 */
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif
#include "mod_plugins.h"
#include "xdelta_decode.h"

#define PATCH_FILE      "Persona-TL-QoL.xdelta"
#define ORIGINAL_SIZE   699705888LL      /* SLPS-00500 first release, CRC32 360EB310 */
#define PATCHED_SIZE    714083664LL      /* + Persona-TL-QoL.xdelta, CRC32 7C27C06C */
#define PATCHED_CRC     0x7C27C06Cu
#define OUT_DIR         "disc"
#define OUT_NAME        "Persona-TL-QoL"
#define TITLE           "Megami Ibunroku Persona"

static const char PROMPT[] =
    "Select your Megami Ibunroku Persona disc image (.cue or .bin).\n\n"
    "Use the original Japanese disc, first release (SLPS-00500): the English translation by Redeted is "
    "applied automatically the first time, into a copy. A disc image already patched with Redeted's "
    "Persona-TL-QoL patch works too.\n\n"
    "You only need to do this once.";

static void message(const char* text, int error) {
#ifdef _WIN32
    MessageBoxA(NULL, text, TITLE, MB_OK | (error ? MB_ICONERROR : MB_ICONINFORMATION));
#else
    fprintf(stderr, "%s\n", text);
#endif
}

static int ask(const char* text) {
#ifdef _WIN32
    return MessageBoxA(NULL, text, TITLE, MB_OKCANCEL | MB_ICONINFORMATION) == IDOK;
#else
    fprintf(stderr, "%s\n", text);
    return 1;
#endif
}

static long long file_size(const char* path) {
    struct _stat64 st;
    return _stat64(path, &st) == 0 ? (long long)st.st_size : -1;
}

static int ends_with(const char* s, const char* tail) {
    size_t a = strlen(s), b = strlen(tail);
    return a >= b && _stricmp(s + a - b, tail) == 0;
}

/* the .bin a .cue names (FILE "x.bin" BINARY, relative to the .cue); any other file: itself */
static int image_bin(const char* disc, char* bin, size_t n) {
    char line[1024];
    FILE* f;
    if (!ends_with(disc, ".cue")) {
        snprintf(bin, n, "%s", disc);
        return 1;
    }
    if (!(f = fopen(disc, "r"))) return 0;
    bin[0] = 0;
    while (fgets(line, sizeof line, f)) {
        char* q1 = strchr(line, '"');
        char* q2 = q1 ? strchr(q1 + 1, '"') : NULL;
        if (strstr(line, "FILE") && q2) {
            const char* slash = strrchr(disc, '\\');
            const char* slash2 = strrchr(disc, '/');
            size_t dir = slash2 > slash ? (size_t)(slash2 - disc + 1) : slash ? (size_t)(slash - disc + 1) : 0;
            *q2 = 0;
            if (strchr(q1 + 1, ':')) snprintf(bin, n, "%s", q1 + 1);          /* absolute path in the .cue */
            else snprintf(bin, n, "%.*s%s", (int)dir, disc, q1 + 1);
            break;
        }
    }
    fclose(f);
    return bin[0] != 0;
}

static int write_cue(const char* cue) {
    FILE* f = fopen(cue, "w");
    if (!f) return 0;
    fprintf(f, "FILE \"" OUT_NAME ".bin\" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n");
    return fclose(f) == 0;
}

/* patch the original into <exe dir>/disc/; out = the new .cue */
static int patch_original(const char* bin, char* out, int size) {
    char dir[1024], patch[1024], out_bin[1100], part[1110], out_cue[1100], text[2048], err[256];
    uint32_t crc = 0;
    err[0] = 0;
    if (!psx_mod_host_path(OUT_DIR, dir, sizeof dir) || !psx_mod_host_path(PATCH_FILE, patch, sizeof patch)) return 0;
    snprintf(out_bin, sizeof out_bin, "%s\\" OUT_NAME ".bin", dir);
    snprintf(part, sizeof part, "%s.part", out_bin);
    snprintf(out_cue, sizeof out_cue, "%s\\" OUT_NAME ".cue", dir);

    if (file_size(out_bin) == PATCHED_SIZE && (file_size(out_cue) > 0 || write_cue(out_cue))) {
        snprintf(out, (size_t)size, "%s", out_cue);              /* patched before */
        return 1;
    }
    if (file_size(patch) <= 0) {
        snprintf(text, sizeof text, "The translation patch is missing:\n%s\n\nPlease unpack the whole download "
                 "again (the patch file must stay next to the exe).", patch);
        message(text, 1);
        return 0;
    }
    snprintf(text, sizeof text,
             "This is the original Japanese disc.\n\nThe English translation (Redeted's Persona-TL-QoL patch) "
             "will now be applied to a copy, saved in:\n%s\n\nYour own disc image is not changed. This needs "
             "about 700 MB of free space and takes a few seconds.", dir);
    if (!ask(text)) return 0;
    CreateDirectoryA(dir, NULL);
    if (!xdelta_apply_file(bin, patch, part, &crc, err, sizeof err, NULL, NULL) || crc != PATCHED_CRC) {
        DeleteFileA(part);
        snprintf(text, sizeof text, "Patching failed: %s\n\nMake sure the disc image is the first release of "
                 "Megami Ibunroku Persona (SLPS-00500) and that there is enough free space.",
                 crc != PATCHED_CRC && !err[0] ? "the result does not match" : err);
        message(text, 1);
        return 0;
    }
    if (!MoveFileExA(part, out_bin, MOVEFILE_REPLACE_EXISTING) || !write_cue(out_cue)) {
        snprintf(text, sizeof text, "Could not save the patched disc in\n%s", dir);
        message(text, 1);
        return 0;
    }
    snprintf(out, (size_t)size, "%s", out_cue);
    return 1;
}

static int persona_disc_prepare(const char* disc, char* out, int size) {
    char bin[1024], text[1024];
    if (!image_bin(disc, bin, sizeof bin)) {
        snprintf(text, sizeof text, "Could not read the disc image:\n%s", disc);
        message(text, 1);
        return 0;
    }
    const long long n = file_size(bin);
    if (n == PATCHED_SIZE) {
        snprintf(out, (size_t)size, "%s", disc);
        return 1;
    }
    if (n == ORIGINAL_SIZE) return patch_original(bin, out, size);
    snprintf(text, sizeof text,
             "This disc image can't be used:\n%s (%lld bytes)\n\nPlease select either\n"
             "- the original Japanese disc, first release (SLPS-00500, 699,705,888 bytes), or\n"
             "- a disc already patched with Redeted's Persona-TL-QoL patch (714,083,664 bytes).\n\n"
             "The later \"Rev 1\" release and the translation-only patch are not supported.", bin, n);
    message(text, 1);
    return 0;
}

PSX_MOD_CONSTRUCTOR(register_persona_disc) {
    psx_mod_register_disc_prepare(persona_disc_prepare, PROMPT);
}
