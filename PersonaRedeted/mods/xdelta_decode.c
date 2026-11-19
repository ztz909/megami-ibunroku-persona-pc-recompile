/* xdelta_decode.c - apply an xdelta3 patch (see xdelta_decode.h; reference: tools/xdelta_apply.py). */
#include "xdelta_decode.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "LzmaDec.h"    /* libchdr's copy of the LZMA SDK decoder (functions renamed CHDR_LzmaDec_*) */

/* exported by LzmaDec.c (Lzma2Dec.c uses it) but not declared in its header */
void LzmaDec_InitDicAndState(CLzmaDec* p, BoolInt initDic, BoolInt initState);

/* ---- small helpers ---- */
static int fail(char* err, int n, const char* fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    if (err && n > 0) vsnprintf(err, (size_t)n, fmt, ap);
    va_end(ap);
    return 0;
}

uint32_t xdelta_crc32(uint32_t crc, const void* data, size_t n) {
    static uint32_t table[256];
    const uint8_t* p = (const uint8_t*)data;
    if (!table[1])
        for (uint32_t i = 0; i < 256; i++) {
            uint32_t c = i;
            for (int k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320u ^ (c >> 1) : c >> 1;
            table[i] = c;
        }
    crc = ~crc;
    while (n--) crc = table[(crc ^ *p++) & 0xFF] ^ (crc >> 8);
    return ~crc;
}

static uint32_t adler32(const uint8_t* p, size_t n) {
    uint32_t a = 1, b = 0;
    while (n) {
        size_t k = n < 5552 ? n : 5552;
        n -= k;
        while (k--) { a += *p++; b += a; }
        a %= 65521; b %= 65521;
    }
    return b << 16 | a;
}

/* bounded reader over a byte range */
typedef struct { const uint8_t* p; const uint8_t* end; int bad; } Rd;

static unsigned rd_byte(Rd* r) {
    if (r->p >= r->end) { r->bad = 1; return 0; }
    return *r->p++;
}

static uint64_t rd_varint(Rd* r) {          /* VCDIFF: big-endian base-128 */
    uint64_t v = 0;
    for (int i = 0; i < 10; i++) {
        unsigned c = rd_byte(r);
        v = v << 7 | (c & 0x7F);
        if (!(c & 0x80)) return v;
    }
    r->bad = 1;
    return 0;
}

static const uint8_t* rd_take(Rd* r, size_t n) {
    const uint8_t* p = r->p;
    if ((size_t)(r->end - r->p) < n) { r->bad = 1; return NULL; }
    r->p += n;
    return p;
}

/* ---- xz / LZMA2: one stream per section kind, continued across windows ---- */
static void* lz_alloc(ISzAllocPtr p, size_t size) { (void)p; return malloc(size); }
static void lz_free(ISzAllocPtr p, void* a) { (void)p; free(a); }
static const ISzAlloc g_lz_alloc = {lz_alloc, lz_free};

typedef struct {
    int started;            /* xz stream + block header parsed */
    int props_ok;           /* LZMA probabilities allocated */
    CLzmaDec dec;
    uint8_t* dic;
    uint32_t dic_size;
} XzStream;

static uint64_t xz_varint(Rd* r) {          /* xz: little-endian base-128 */
    uint64_t v = 0;
    for (int i = 0; i < 9; i++) {
        unsigned c = rd_byte(r);
        v |= (uint64_t)(c & 0x7F) << (7 * i);
        if (!(c & 0x80)) return v;
    }
    r->bad = 1;
    return 0;
}

static int xz_start(XzStream* s, Rd* r, char* err, int en) {
    static const uint8_t magic[6] = {0xFD, '7', 'z', 'X', 'Z', 0};
    const uint8_t* h = rd_take(r, 12);                     /* stream header: magic, flags, CRC32 */
    if (!h || memcmp(h, magic, 6) != 0) return fail(err, en, "secondary section is not an xz stream");
    const uint8_t* bh = r->p;
    const unsigned hsize = (rd_byte(r) + 1u) * 4u;         /* block header size */
    const unsigned flags = rd_byte(r);
    if (flags & 0x40) xz_varint(r);                        /* compressed size */
    if (flags & 0x80) xz_varint(r);                        /* uncompressed size */
    if ((flags & 3) != 0) return fail(err, en, "xz block with more than one filter");
    if (xz_varint(r) != 0x21 || xz_varint(r) != 1) return fail(err, en, "xz filter is not LZMA2");
    const unsigned code = rd_byte(r);
    if (r->bad || code > 40) return fail(err, en, "bad xz block header");
    s->dic_size = code == 40 ? 0xFFFFFFFFu : (2u | (code & 1u)) << (code / 2 + 11);
    if (s->dic_size < 4096) s->dic_size = 4096;
    r->p = bh;
    if (!rd_take(r, hsize)) return fail(err, en, "short xz block header");
    s->dic = (uint8_t*)malloc(s->dic_size);
    if (!s->dic) return fail(err, en, "out of memory (LZMA dictionary %u bytes)", s->dic_size);
    LzmaDec_Construct(&s->dec);
    s->dec.dic = s->dic;
    s->dec.dicBufSize = s->dic_size;
    s->dec.dicPos = 0;
    s->dec.prop.dicSize = s->dic_size;
    s->started = 1;
    return 1;
}

static void xz_free(XzStream* s) {
    if (s->props_ok) LzmaDec_FreeProbs(&s->dec, &g_lz_alloc);
    free(s->dic);
    memset(s, 0, sizeof *s);
}

/* copy what the decoder put into its circular dictionary since `start` into out */
static size_t dic_take(XzStream* s, size_t start, uint8_t* out) {
    const size_t n = s->dec.dicPos - start;
    memcpy(out, s->dic + start, n);
    return n;
}

/* decode one window's part of the stream (whole LZMA2 chunks: xdelta3 sync-flushes after each window) */
static int xz_window(XzStream* s, Rd* r, uint8_t* out, size_t need, char* err, int en) {
    size_t got = 0;
    if (!s->started && !xz_start(s, r, err, en)) return 0;
    while (r->p < r->end) {
        const unsigned c = rd_byte(r);
        if (c == 0) break;                                       /* end of LZMA2 data */
        if (c == 1 || c == 2) {                                  /* uncompressed chunk (1: dictionary reset) */
            size_t size = ((size_t)rd_byte(r) << 8 | rd_byte(r)) + 1;
            const uint8_t* src = rd_take(r, size);
            if (!src || got + size > need) return fail(err, en, "bad LZMA2 uncompressed chunk");
            LzmaDec_InitDicAndState(&s->dec, c == 1, False);
            while (size) {
                if (s->dec.dicPos == s->dec.dicBufSize) s->dec.dicPos = 0;
                size_t k = s->dec.dicBufSize - s->dec.dicPos;
                if (k > size) k = size;
                memcpy(s->dic + s->dec.dicPos, src, k);          /* = Lzma2Dec's LzmaDec_UpdateWithUncompressed */
                s->dec.dicPos += k;
                if (s->dec.checkDicSize == 0 && s->dec.prop.dicSize - s->dec.processedPos <= k)
                    s->dec.checkDicSize = s->dec.prop.dicSize;
                s->dec.processedPos += (UInt32)k;
                memcpy(out + got, src, k);
                got += k; src += k; size -= k;
            }
            continue;
        }
        if (c < 0x80) return fail(err, en, "bad LZMA2 control byte %02X", c);
        size_t unpack = ((size_t)(c & 0x1F) << 16) + ((size_t)rd_byte(r) << 8 | rd_byte(r)) + 1;
        const size_t pack = ((size_t)rd_byte(r) << 8 | rd_byte(r)) + 1;
        const unsigned mode = c >> 5 & 3;
        if (mode >= 2) {                                         /* new lc/lp/pb */
            const uint8_t pb = (uint8_t)rd_byte(r);
            uint8_t props[5] = {pb, (uint8_t)s->dic_size, (uint8_t)(s->dic_size >> 8), (uint8_t)(s->dic_size >> 16),
                                (uint8_t)(s->dic_size >> 24)};
            if (pb >= 9 * 5 * 5 || LzmaDec_AllocateProbs(&s->dec, props, 5, &g_lz_alloc) != SZ_OK)
                return fail(err, en, "bad LZMA2 properties");
            s->props_ok = 1;
        } else if (!s->props_ok) {
            return fail(err, en, "LZMA2 chunk before properties");
        }
        const uint8_t* src = rd_take(r, pack);
        if (r->bad || got + unpack > need) return fail(err, en, "bad LZMA2 chunk");
        LzmaDec_InitDicAndState(&s->dec, mode == 3, mode != 0);
        size_t left = pack;
        while (unpack) {
            if (s->dec.dicPos == s->dec.dicBufSize) s->dec.dicPos = 0;
            const size_t start = s->dec.dicPos;
            size_t lim = s->dec.dicBufSize - start;
            if (lim > unpack) lim = unpack;
            SizeT in_len = left;
            ELzmaStatus status;
            if (LzmaDec_DecodeToDic(&s->dec, start + lim, src, &in_len, LZMA_FINISH_ANY, &status) != SZ_OK)
                return fail(err, en, "LZMA data error");
            const size_t n = dic_take(s, start, out + got);
            if (n == 0 && in_len == 0) return fail(err, en, "LZMA decoder made no progress");
            got += n; unpack -= n; src += in_len; left -= in_len;
        }
    }
    if (r->bad) return fail(err, en, "truncated LZMA2 data");
    if (got != need) return fail(err, en, "secondary section: %zu bytes, expected %zu", got, need);
    return 1;
}

/* a data / inst / addr section; compressed ones start with the decompressed size */
static uint8_t* section(const uint8_t* raw, size_t len, int compressed, XzStream* s, size_t* out_len,
                        char* err, int en) {
    Rd r = {raw, raw + len, 0};
    if (!compressed) {
        uint8_t* b = (uint8_t*)malloc(len ? len : 1);
        if (b) memcpy(b, raw, len);
        *out_len = len;
        return b;
    }
    const uint64_t size = rd_varint(&r);
    if (r.bad || size > 0x40000000u) { fail(err, en, "bad secondary section size"); return NULL; }
    uint8_t* b = (uint8_t*)malloc(size ? (size_t)size : 1);
    if (!b) { fail(err, en, "out of memory"); return NULL; }
    if (!xz_window(s, &r, b, (size_t)size, err, en)) { free(b); return NULL; }
    *out_len = (size_t)size;
    return b;
}

/* ---- VCDIFF ---- */
enum { NOOP, ADD, COPY, RUN };
typedef struct { uint8_t type1, size1, mode1, type2, size2, mode2; } Code;

static void code_table(Code t[256]) {            /* RFC 3284 5.6 */
    int i = 0;
    t[i++] = (Code){RUN, 0, 0, NOOP, 0, 0};
    for (int s = 0; s < 18; s++) t[i++] = (Code){ADD, (uint8_t)s, 0, NOOP, 0, 0};
    for (int m = 0; m < 9; m++) {
        t[i++] = (Code){COPY, 0, (uint8_t)m, NOOP, 0, 0};
        for (int s = 4; s < 19; s++) t[i++] = (Code){COPY, (uint8_t)s, (uint8_t)m, NOOP, 0, 0};
    }
    for (int m = 0; m < 6; m++)
        for (int a = 1; a < 5; a++)
            for (int c = 4; c < 7; c++) t[i++] = (Code){ADD, (uint8_t)a, 0, COPY, (uint8_t)c, (uint8_t)m};
    for (int m = 6; m < 9; m++)
        for (int a = 1; a < 5; a++) t[i++] = (Code){ADD, (uint8_t)a, 0, COPY, 4, (uint8_t)m};
    for (int m = 0; m < 9; m++) t[i++] = (Code){COPY, 4, (uint8_t)m, ADD, 1, 0};
}

int xdelta_apply_file(const char* source_path, const char* patch_path, const char* out_path,
                      uint32_t* out_crc, char* err, int en, XdeltaProgress progress, void* user) {
    Code table[256];
    XzStream xs[3];
    FILE *fp = NULL, *fs = NULL, *fo = NULL;
    uint8_t *patch = NULL, *src = NULL, *tgt = NULL, *data = NULL, *inst = NULL, *addr = NULL;
    size_t src_cap = 0, tgt_cap = 0;
    uint32_t crc = 0;
    int ok = 0, windows = 0;
    long patch_len;

    memset(xs, 0, sizeof xs);
    code_table(table);
    if (!(fp = fopen(patch_path, "rb"))) { fail(err, en, "cannot open %s", patch_path); goto done; }
    fseek(fp, 0, SEEK_END);
    patch_len = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (patch_len <= 8 || !(patch = (uint8_t*)malloc((size_t)patch_len)) ||
        fread(patch, 1, (size_t)patch_len, fp) != (size_t)patch_len) {
        fail(err, en, "cannot read %s", patch_path);
        goto done;
    }
    if (!(fs = fopen(source_path, "rb"))) { fail(err, en, "cannot open %s", source_path); goto done; }
    if (!(fo = fopen(out_path, "wb"))) { fail(err, en, "cannot write %s", out_path); goto done; }

    Rd p = {patch, patch + patch_len, 0};
    const uint8_t* magic = rd_take(&p, 4);
    if (!magic || memcmp(magic, "\xD6\xC3\xC4\x00", 4) != 0) { fail(err, en, "not an xdelta3 / VCDIFF file"); goto done; }
    const unsigned hdr = rd_byte(&p);
    const unsigned secondary = hdr & 1 ? rd_byte(&p) : 0;
    if (hdr & 2) { fail(err, en, "custom code tables are not supported"); goto done; }
    if (hdr & 4) rd_take(&p, (size_t)rd_varint(&p));
    if (secondary != 0 && secondary != 2) { fail(err, en, "secondary compressor %u not supported", secondary); goto done; }

    while (!p.bad && p.p < p.end) {
        const unsigned wi = rd_byte(&p);
        uint64_t sl = 0, sp = 0;
        if (wi & 2) { fail(err, en, "VCD_TARGET windows are not supported"); goto done; }
        if (wi & 1) { sl = rd_varint(&p); sp = rd_varint(&p); }
        rd_varint(&p);                                           /* length of the delta encoding */
        const uint64_t tlen = rd_varint(&p);
        const unsigned di = rd_byte(&p);
        const uint64_t ld = rd_varint(&p), li = rd_varint(&p), la = rd_varint(&p);
        uint32_t want_adler = 0;
        if (wi & 4) {
            const uint8_t* a = rd_take(&p, 4);
            if (a) want_adler = (uint32_t)a[0] << 24 | (uint32_t)a[1] << 16 | (uint32_t)a[2] << 8 | a[3];
        }
        const uint8_t* rd_ = rd_take(&p, (size_t)ld);
        const uint8_t* ri = rd_take(&p, (size_t)li);
        const uint8_t* ra = rd_take(&p, (size_t)la);
        if (p.bad || sl > 0x10000000u || tlen > 0x10000000u) { fail(err, en, "corrupt patch (window %d)", windows); goto done; }

        if (sl > src_cap) { free(src); src_cap = (size_t)sl; if (!(src = (uint8_t*)malloc(src_cap))) { fail(err, en, "out of memory"); goto done; } }
        if (tlen > tgt_cap) { free(tgt); tgt_cap = (size_t)tlen; if (!(tgt = (uint8_t*)malloc(tgt_cap))) { fail(err, en, "out of memory"); goto done; } }
        if (sl) {
            if (_fseeki64(fs, (long long)sp, SEEK_SET) != 0 || fread(src, 1, (size_t)sl, fs) != (size_t)sl) {
                fail(err, en, "the disc image is too short (not the right version?)");
                goto done;
            }
        }
        size_t nd, ni, na;
        free(data); free(inst); free(addr);
        data = inst = addr = NULL;
        if (!(data = section(rd_, (size_t)ld, di & 1, &xs[0], &nd, err, en)) ||
            !(inst = section(ri, (size_t)li, di & 2, &xs[1], &ni, err, en)) ||
            !(addr = section(ra, (size_t)la, di & 4, &xs[2], &na, err, en)))
            goto done;

        Rd ir = {inst, inst + ni, 0}, ar = {addr, addr + na, 0};
        size_t dpos = 0, t = 0;
        uint64_t near_[4] = {0, 0, 0, 0}, same[3 * 256];
        int nslot = 0;
        memset(same, 0, sizeof same);
        while (ir.p < ir.end && !ir.bad && !ar.bad) {
            const Code c = table[rd_byte(&ir)];
            for (int half = 0; half < 2; half++) {
                const unsigned type = half ? c.type2 : c.type1;
                const unsigned mode = half ? c.mode2 : c.mode1;
                uint64_t size = half ? c.size2 : c.size1;
                if (type == NOOP) continue;
                if (size == 0) size = rd_varint(&ir);
                if (t + size > tlen) { fail(err, en, "corrupt patch: window %d overruns", windows); goto done; }
                if (type == ADD) {
                    if (dpos + size > nd) { fail(err, en, "corrupt patch: data overrun"); goto done; }
                    memcpy(tgt + t, data + dpos, (size_t)size);
                    dpos += (size_t)size;
                } else if (type == RUN) {
                    if (dpos >= nd) { fail(err, en, "corrupt patch: data overrun"); goto done; }
                    memset(tgt + t, data[dpos++], (size_t)size);
                } else {
                    const uint64_t here = sl + t;
                    uint64_t a;
                    if (mode == 0) a = rd_varint(&ar);
                    else if (mode == 1) a = here - rd_varint(&ar);
                    else if (mode < 6) a = near_[mode - 2] + rd_varint(&ar);
                    else a = same[(mode - 6) * 256 + rd_byte(&ar)];
                    near_[nslot] = a;
                    nslot = (nslot + 1) & 3;
                    same[a % (3 * 256)] = a;
                    if (a >= here) { fail(err, en, "corrupt patch: copy from the future"); goto done; }
                    if (a + size <= sl) {
                        memcpy(tgt + t, src + a, (size_t)size);
                    } else {
                        for (uint64_t k = 0; k < size; k++) {          /* may overlap the bytes being written */
                            const uint64_t q = a + k;
                            tgt[t + k] = q < sl ? src[q] : tgt[q - sl];
                        }
                    }
                }
                t += (size_t)size;
            }
        }
        if (ir.bad || ar.bad || t != tlen) { fail(err, en, "corrupt patch: window %d decodes to %zu of %llu bytes",
                                                   windows, t, (unsigned long long)tlen); goto done; }
        if ((wi & 4) && adler32(tgt, t) != want_adler) {
            fail(err, en, "checksum mismatch in window %d: this is not the disc image the patch was made for", windows);
            goto done;
        }
        if (fwrite(tgt, 1, t, fo) != t) { fail(err, en, "cannot write the patched image (disk full?)"); goto done; }
        crc = xdelta_crc32(crc, tgt, t);
        windows++;
        if (progress) progress((int)((p.p - patch) * 100 / patch_len), user);
    }
    if (p.bad) { fail(err, en, "the patch file is truncated"); goto done; }
    if (out_crc) *out_crc = crc;
    ok = 1;
done:
    if (fo && fclose(fo) != 0 && ok) ok = fail(err, en, "cannot write the patched image (disk full?)");
    if (fs) fclose(fs);
    if (fp) fclose(fp);
    for (int i = 0; i < 3; i++) xz_free(&xs[i]);
    free(patch); free(src); free(tgt); free(data); free(inst); free(addr);
    return ok;
}
