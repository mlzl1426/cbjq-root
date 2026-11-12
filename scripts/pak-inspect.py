#!/usr/bin/env python3
"""Inspect a UE4 pak file: version, mount point, entry list, texture pixel formats.

Usage:
    python pak-inspect.py <file.pak> [--limit N] [--formats]

Reads the pak index only (plus the first compressed block of a few asset
entries for --formats), so it works on multi-GB paks without unpacking them.
"""
import argparse
import collections
import hashlib
import os
import re
import struct
import sys
import zlib

MAGIC = bytes.fromhex("e1126f5a")


class Pak:
    def __init__(self, path):
        self.path = path
        self.fh = open(path, "rb")
        self.size = os.path.getsize(path)
        self._read_footer()
        self._read_index()

    def _read_footer(self):
        fh = self.fh
        tail = min(self.size, 1 << 20)
        fh.seek(self.size - tail)
        buf = fh.read(tail)
        i = buf.rfind(MAGIC)
        if i < 0:
            raise SystemExit("not a UE pak: magic 0x5A6F12E1 not found")
        self.version = struct.unpack_from("<I", buf, i + 4)[0]
        self.index_offset, self.index_size = struct.unpack_from("<QQ", buf, i + 8)
        if self.index_offset + self.index_size > self.size:
            raise SystemExit(
                "index outside file (offset=%d size=%d file=%d); "
                "this looks like a chunked pak — inspect the last chunk instead"
                % (self.index_offset, self.index_size, self.size)
            )

    def _read_index(self):
        self.fh.seek(self.index_offset)
        idx = self.fh.read(self.index_size)
        pos = 0
        self.mount, pos = _fstring(idx, pos)
        count, = struct.unpack_from("<i", idx, pos)
        pos += 4
        self.entries = []
        for _ in range(count):
            name, pos = _fstring(idx, pos)
            off, size, usize = struct.unpack_from("<qqq", idx, pos)
            pos += 24
            method, = struct.unpack_from("<I", idx, pos)
            pos += 4
            if self.version < 2:          # v1 keeps a timestamp
                pos += 8
            pos += 20                     # sha1 of the (compressed) payload
            blocks = []
            if self.version >= 3:
                nblocks, = struct.unpack_from("<i", idx, pos)
                pos += 4
                for _ in range(nblocks):
                    a, b = struct.unpack_from("<qq", idx, pos)
                    pos += 16
                    blocks.append((a, b))
                pos += 1                  # flags (bEncrypted)
                pos += 4                  # compression block size
            self.entries.append(
                dict(name=name, offset=off, size=size, usize=usize,
                     method=method, blocks=blocks)
            )

    def read_entry(self, e):
        self.fh.seek(e["offset"])
        raw = self.fh.read(e["size"])
        if e["method"] == 0:
            return raw
        out = b""
        for a, b in e["blocks"] or [(e["offset"], e["offset"] + e["size"])]:
            self.fh.seek(a)
            out += zlib.decompress(self.fh.read(b - a))
        return out


def _fstring(buf, pos):
    n, = struct.unpack_from("<i", buf, pos)
    if n <= 0 or n > 4096:
        raise SystemExit("bad FString length %d at %d — unsupported index layout" % (n, pos))
    pos += 4
    return buf[pos:pos + n - 1].decode("utf-8", "replace"), pos + n


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pak")
    ap.add_argument("--limit", type=int, default=8, help="entries to print")
    ap.add_argument("--formats", action="store_true",
                    help="decode the first block of .uasset/.uexp and list PF_* formats")
    args = ap.parse_args()

    p = Pak(args.pak)
    print("file      :", args.pak)
    print("bytes     :", p.size)
    print("sha256    :", sha256(args.pak))
    print("pak ver   :", p.version)
    print("mount     :", repr(p.mount))
    print("entries   :", len(p.entries))
    ext = collections.Counter(os.path.splitext(e["name"])[1] for e in p.entries)
    print("by ext    :", dict(ext.most_common()))
    for e in p.entries[: args.limit]:
        print("  %10d  %s" % (e["usize"], e["name"]))

    if args.formats:
        seen = collections.Counter()
        for e in p.entries:
            if not e["name"].endswith((".uasset", ".uexp")):
                continue
            try:
                raw = p.read_entry(e)
            except Exception as ex:  # noqa: BLE001 - best effort, keep going
                continue
            for m in re.findall(rb"PF_[A-Za-z0-9_]+", raw):
                seen[m.decode()] += 1
            if sum(seen.values()) > 64:
                break
        print("pixel fmt :", dict(seen.most_common()) or "none found")


if __name__ == "__main__":
    sys.exit(main())
