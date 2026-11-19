/* xdelta_decode.h - apply an xdelta3 patch (VCDIFF, RFC 3284) to a file.
 *
 * Covers what xdelta3 writes and Redeted's patches use: the default code table, xdelta3's application
 * header, per-window Adler-32 checksums, and LZMA secondary compression (one xz / LZMA2 stream per section
 * kind running through all windows). Decoding uses the LZMA SDK decoder psxrecomp already links (libchdr).
 * Reference implementation: tools/xdelta_apply.py.
 */
#pragma once
#include <stdint.h>

/* progress: called now and then with 0..100 (may be NULL) */
typedef void (*XdeltaProgress)(int percent, void* user);

/* Returns 1 on success (out_crc = CRC-32 of the whole output), 0 on failure (err = reason). The output file
 * is written as given; the caller decides where (and renames it into place when done). */
int xdelta_apply_file(const char* source_path, const char* patch_path, const char* out_path,
                      uint32_t* out_crc, char* err, int err_size, XdeltaProgress progress, void* user);

uint32_t xdelta_crc32(uint32_t crc, const void* data, size_t n);
