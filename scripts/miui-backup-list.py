#!/usr/bin/env python3
"""List a MIUI local backup (.bak) without extracting it.

MIUI backup layout (format 2, Android Backup 5):
    "MIUI BACKUP\n2\n<pkg> <label>\n102\n0\nANDROID BACKUP\n5\n0\nnone\n"   86 bytes
    then a plain (uncompressed) tar with:
        apps/<pkg>/_manifest      package name, version, signature
        apps/<pkg>/a/base.apk     the APK itself
        apps/<pkg>/r/...          app data
        apps/<pkg>/f/...          files/ (UE4 paks land here)

Usage:
    python miui-backup-list.py <file.bak> [--filter Paks]
"""
import argparse
import sys
import tarfile

HEADER_LEN = 86


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bak")
    ap.add_argument("--filter", default="", help="only print entries containing this text")
    args = ap.parse_args()

    with open(args.bak, "rb") as f:
        head = f.read(HEADER_LEN)
        try:
            lines = head.decode("utf-8").splitlines()
        except UnicodeDecodeError:
            raise SystemExit("not a MIUI backup: header is not UTF-8 text")
        if not lines or lines[0] != "MIUI BACKUP":
            raise SystemExit("not a MIUI backup: first line is %r" % (lines[:1],))
        print("pkg line  :", lines[2] if len(lines) > 2 else "?")
        print("format    :", " / ".join(lines[1:7]))
        f.seek(HEADER_LEN)
        tf = tarfile.open(fileobj=f, mode="r:")
        total = 0
        shown = 0
        for m in tf:
            total += m.size
            if args.filter and args.filter not in m.name:
                continue
            shown += 1
            print("%12d  %s" % (m.size, m.name))
        print("---")
        print("entries   :", shown)
        print("payload   : %.2f MB" % (total / 1048576))


if __name__ == "__main__":
    sys.exit(main())
