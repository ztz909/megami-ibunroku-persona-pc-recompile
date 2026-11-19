"""Apply an xdelta3 (VCDIFF, RFC 3284) patch, e.g. Redeted's Persona-TL-QoL.xdelta. Reference for the C patcher.

Usage: xdelta_apply.py <source .bin> <patch .xdelta> <output .bin>

Supports what xdelta3 writes: the VCDIFF format with the default code table, xdelta3's application header,
per-window Adler-32 checksums and secondary compression of the data / instruction / address sections
(only LZMA, which is what Redeted's patches use: one xz stream per section kind running through all windows). Prints the CRC32 of the output.
"""
import lzma
import struct
import sys
import zlib

RUN, ADD, COPY, NOOP = 3, 1, 2, 0


def code_table():
    """RFC 3284 5.6 default instruction code table: (type1, size1, mode1, type2, size2, mode2)."""
    t = [(RUN, 0, 0, NOOP, 0, 0)]
    t += [(ADD, s, 0, NOOP, 0, 0) for s in range(18)]
    for m in range(9):
        t.append((COPY, 0, m, NOOP, 0, 0))
        t += [(COPY, s, m, NOOP, 0, 0) for s in range(4, 19)]
    for m in range(6):
        t += [(ADD, a, 0, COPY, c, m) for a in range(1, 5) for c in range(4, 7)]
    for m in range(6, 9):
        t += [(ADD, a, 0, COPY, 4, m) for a in range(1, 5)]
    t += [(COPY, 4, m, ADD, 1, 0) for m in range(9)]
    assert len(t) == 256
    return t


class Reader:
    def __init__(self, b, p=0):
        self.b, self.p = b, p

    def byte(self):
        v = self.b[self.p]
        self.p += 1
        return v

    def varint(self):
        v = 0
        while True:
            c = self.byte()
            v = (v << 7) | (c & 0x7F)
            if not c & 0x80:
                return v

    def take(self, n):
        v = self.b[self.p:self.p + n]
        self.p += n
        return v


def section(raw, compressed, streams, kind):
    """A data / inst / addr section. Secondary-compressed sections of one kind form ONE xz stream across all
    windows (header only in the first window, sync-flushed after each window, never finished): keep a
    decoder per kind and take exactly the announced number of bytes from it each window."""
    if not compressed:
        return raw
    r = Reader(raw)
    size = r.varint()
    dec = streams.setdefault(kind, lzma.LZMADecompressor(format=lzma.FORMAT_XZ))
    out = dec.decompress(raw[r.p:])
    if len(out) != size:
        raise ValueError(f"secondary {kind} section: {len(out)} bytes, expected {size}")
    return out


def apply(src, patch, out):
    table = code_table()
    p = Reader(open(patch, "rb").read())
    if p.take(4) != b"\xd6\xc3\xc4\x00":
        raise ValueError("not a VCDIFF / xdelta3 file")
    hdr = p.byte()
    secondary = p.byte() if hdr & 1 else 0
    if hdr & 2:
        raise ValueError("custom code tables are not supported")
    if hdr & 4:
        p.take(p.varint())
    if secondary not in (0, 2):
        raise ValueError(f"secondary compressor {secondary} not supported (only LZMA = 2)")
    fs = open(src, "rb")
    fo = open(out, "wb")
    crc, total, windows = 0, 0, 0
    streams = {}
    while p.p < len(p.b):
        wi = p.byte()
        src_seg = b""
        if wi & 3:
            sl, sp = p.varint(), p.varint()
            if wi & 1:
                fs.seek(sp)
                src_seg = fs.read(sl)
            else:
                raise ValueError("VCD_TARGET windows are not supported")
            if len(src_seg) != sl:
                raise ValueError("source file too short")
        p.varint()                                   # length of the delta encoding
        tlen = p.varint()
        di = p.byte()
        ld, li, la = p.varint(), p.varint(), p.varint()
        adler = struct.unpack(">I", p.take(4))[0] if wi & 4 else None
        data = section(p.take(ld), di & 1, streams, "data")
        inst = Reader(section(p.take(li), di & 2, streams, "inst"))
        addr = Reader(section(p.take(la), di & 4, streams, "addr"))
        dpos = 0
        near, nslot, same = [0] * 4, 0, [0] * (3 * 256)
        t = bytearray()
        sl = len(src_seg)
        while inst.p < len(inst.b):
            code = table[inst.byte()]
            for typ, size, mode in ((code[0], code[1], code[2]), (code[3], code[4], code[5])):
                if typ == NOOP:
                    continue
                if size == 0:
                    size = inst.varint()
                if typ == ADD:
                    t += data[dpos:dpos + size]
                    dpos += size
                elif typ == RUN:
                    t += bytes([data[dpos]]) * size
                    dpos += 1
                else:
                    here = sl + len(t)
                    if mode == 0:
                        a = addr.varint()
                    elif mode == 1:
                        a = here - addr.varint()
                    elif mode < 6:
                        a = near[mode - 2] + addr.varint()
                    else:
                        a = same[(mode - 6) * 256 + addr.byte()]
                    near[nslot] = a
                    nslot = (nslot + 1) % 4
                    same[a % (3 * 256)] = a
                    if a + size <= sl:
                        t += src_seg[a:a + size]
                    else:
                        for k in range(size):             # may overlap the bytes being written
                            q = a + k
                            t.append(src_seg[q] if q < sl else t[q - sl])
        if len(t) != tlen:
            raise ValueError(f"window {windows}: {len(t)} bytes, expected {tlen}")
        if adler is not None and zlib.adler32(bytes(t)) != adler:
            raise ValueError(f"window {windows}: Adler-32 mismatch")
        fo.write(t)
        crc = zlib.crc32(t, crc)
        total += len(t)
        windows += 1
    fo.close()
    print(f"{windows} windows, {total} bytes, CRC32 {crc:08X}")
    return crc


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    apply(*sys.argv[1:])
