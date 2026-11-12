#!/usr/bin/env python3
"""Turn a stock client APK into one that talks to a local server, fully signed.

One command, no Android SDK required beyond `apksigner` + JDK:

    python build-client.py <stock.apk> --ca server-ca.pem --keystore my.jks

What it does, in place, without touching any game asset:
    1. assets/sdk_config.properties  ->  point SDK endpoints at 127.0.0.1
    2. res/raw/<custom>.cer          ->  replace with the server CA (same entry name)
    3. rewrite the zip, keeping every other entry byte-identical
    4. 4 KB-align stored .so entries   (extractNativeLibs=false requires it)
    5. sign v1+v2+v3 with your own key

Output: <input>.local.apk, ready to install.

Requires: python 3.8+, java, apksigner (build-tools). Nothing else.
"""
import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib

SIG_L = b"PK\x03\x04"
SIG_C = b"PK\x01\x02"
SIG_E = b"PK\x05\x06"
PROPS = "assets/sdk_config.properties"
PAGE = 4096

# 只改这几条；其余（埋点、活动、CDN）保持原样，否则会把资源下载也指到本机
LOCAL_KEYS = ("XgAuthUrl", "SeasunAuthUrl", "clientPushDataUrl")


def is_sig(name):
    if not name.startswith("META-INF/"):
        return False
    base = name[len("META-INF/"):]
    if "/" in base:                      # META-INF/maven/..., META-INF/proguard/... 是普通资源
        return False
    return base == "MANIFEST.MF" or base.upper().endswith((".SF", ".RSA", ".DSA", ".EC"))


def align_extra(pos, namelen, align):
    """Pad the local-header extra field so the entry's data starts at `align`.

    A padding block is 2 bytes id + 2 bytes length, so a needed gap of 1-3
    bytes can only be covered by advancing a whole extra alignment period.
    """
    if align <= 1:
        return b""
    pad = (align - (pos + 30 + namelen) % align) % align
    if pad == 0:
        return b""
    if pad < 4:
        pad += align
    return b"\x00\x00" + struct.pack("<H", pad - 4) + b"\x00" * (pad - 4)


def rewrite_props(raw, port):
    text = raw.decode("utf-8")
    local = "http\\://127.0.0.1\\:%d" % port
    for key in LOCAL_KEYS:
        text = re.sub(rf"^{key}\s*=.*$", f"{key}={local}", text, flags=re.M)
    return text.encode("utf-8")


def find_custom_ca(names):
    for n in sorted(names):
        if n.startswith("res/raw/") and n.lower().endswith((".cer", ".crt", ".pem")):
            if "mikusb" in n or "miku" in n or "local" in n:
                return n
    return None


def rebuild(src_path, out_path, replacements):
    """Copy every entry; swap the ones in `replacements` (name -> bytes)."""
    src = open(src_path, "rb")
    src.seek(-22, 2)
    eocd = src.read(22)
    if eocd[:4] != SIG_E:
        raise SystemExit("not a zip/apk: EOCD not found")
    (_, _, _, _, _, cd_size, cd_off, _) = struct.unpack("<IHHHHIIH", eocd)
    src.seek(cd_off)
    cd = src.read(cd_size)

    entries, p = [], 0
    while p < len(cd):
        if cd[p:p + 4] != SIG_C:
            raise SystemExit("bad central directory at %d" % p)
        (_, _vm, _vn, flags, method, mtime, mdate, crc, csize, usize,
         nlen, elen, clen, _dsk, _ia, eattr, lho) = struct.unpack_from("<IHHHHHHIIIHHHHHII", cd, p)
        name = cd[p + 46:p + 46 + nlen].decode("utf-8", "replace")
        entries.append(dict(name=name, method=method, mtime=mtime, mdate=mdate,
                            crc=crc, csize=csize, usize=usize, eattr=eattr, lho=lho))
        p += 46 + nlen + elen + clen

    out = open(out_path, "wb")
    written = []
    for e in entries:
        if is_sig(e["name"]):
            continue
        name_b = e["name"].encode("utf-8")
        pos = out.tell()
        replaced = e["name"] in replacements
        # 替换条目按 stored 写入；其余沿用原始压缩方式
        stored = True if replaced else (e["method"] == 0)
        # zipalign -p 4 的规则：stored 的 .so 页对齐，其余 stored 条目 4 字节对齐
        if stored:
            align = PAGE if e["name"].endswith(".so") else 4
        else:
            align = 1
        extra = align_extra(pos, len(name_b), align)

        if replaced:
            data = replacements[e["name"]]
            method, csize, usize = 0, len(data), len(data)
            crc = zlib.crc32(data) & 0xFFFFFFFF
            payload = data
        else:
            method, crc, csize, usize = e["method"], e["crc"], e["csize"], e["usize"]
            # local header extra length can differ from the central one; re-read it
            src.seek(e["lho"])
            head = src.read(30)
            (_, _, _, _, _, _, _, _, _, lnlen, lelen) = struct.unpack("<IHHHHHIIIHH", head)
            src.seek(e["lho"] + 30 + lnlen + lelen)
            payload = None

        hdr_off = pos
        out.write(SIG_L + struct.pack("<HHHHHIIIHH", 20, 0, method, e["mtime"], e["mdate"],
                                      0, 0, 0, len(name_b), len(extra)))
        out.write(name_b)
        out.write(extra)
        if payload is not None:
            out.write(payload)
        else:
            left = csize
            while left:
                chunk = src.read(min(left, 1 << 23))
                if not chunk:
                    raise SystemExit("short read: " + e["name"])
                out.write(chunk)
                left -= len(chunk)
        end = out.tell()
        out.seek(hdr_off + 14)
        out.write(struct.pack("<III", crc, csize, usize))
        out.seek(end)
        written.append(dict(name=e["name"], method=method, mtime=e["mtime"], mdate=e["mdate"],
                            crc=crc, csize=csize, usize=usize, eattr=e["eattr"], off=hdr_off))
        print("  %12d  %s" % (usize, e["name"]), flush=True)

    cd_start = out.tell()
    for w in written:
        nb = w["name"].encode("utf-8")
        out.write(SIG_C + struct.pack("<HHHHHHIIIHHHHHII", 0x031E, 20, 0, w["method"],
                                      w["mtime"], w["mdate"], w["crc"], w["csize"], w["usize"],
                                      len(nb), 0, 0, 0, 0, w["eattr"], w["off"]))
        out.write(nb)
    cd_end = out.tell()
    out.write(SIG_E + struct.pack("<HHHHIIH", 0, 0, len(written), len(written),
                                  cd_end - cd_start, cd_start, 0))
    out.close()


def find_apksigner(explicit):
    if explicit:
        return explicit
    for cand in ("apksigner", "apksigner.bat"):
        if shutil.which(cand):
            return shutil.which(cand)
    for root in (os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT")):
        if not root:
            continue
        bt = os.path.join(root, "build-tools")
        if os.path.isdir(bt):
            for ver in sorted(os.listdir(bt), reverse=True):
                for cand in ("apksigner.bat", "apksigner"):
                    p = os.path.join(bt, ver, cand)
                    if os.path.isfile(p):
                        return p
    raise SystemExit("apksigner not found: pass --apksigner or set ANDROID_HOME")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("apk", help="stock client APK (unmodified upstream)")
    ap.add_argument("--ca", required=True, help="server root CA, PEM or DER")
    ap.add_argument("--port", type=int, default=21580, help="local SDK port")
    ap.add_argument("--keystore", required=True, help=".jks / .keystore for re-signing")
    ap.add_argument("--ks-alias", default="miku")
    ap.add_argument("--ks-pass", default=None, help="defaults to $KS_PASS")
    ap.add_argument("--apksigner", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ca = open(args.ca, "rb").read()
    if ca[:2] != b"0\x82":
        import base64
        body = re.search(rb"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----", ca, re.S)
        if not body:
            raise SystemExit("--ca is neither DER nor PEM certificate")
        ca = base64.b64decode(re.sub(rb"\s+", b"", body.group(1)))
    print("server CA: %d bytes DER" % len(ca))

    z = zipfile.ZipFile(args.apk)
    names = set(z.namelist())
    if PROPS not in names:
        raise SystemExit("%s not found in APK" % PROPS)
    ca_entry = find_custom_ca(names)
    if not ca_entry:
        raise SystemExit("no custom CA under res/raw/; this APK cannot trust a local server")

    print("props    :", PROPS)
    print("CA entry :", ca_entry)
    replacements = {
        PROPS: rewrite_props(z.read(PROPS), args.port),
        ca_entry: ca,
    }

    out = args.out or (os.path.splitext(args.apk)[0] + ".local.apk")
    unsigned = out + ".unsigned"
    print("\n== rewrite zip ==")
    rebuild(args.apk, unsigned, replacements)

    pw = args.ks_pass or os.environ.get("KS_PASS")
    if not pw:
        raise SystemExit("keystore password required: --ks-pass or $KS_PASS")
    signer = find_apksigner(args.apksigner)
    env = os.environ.copy()
    env["KS_PASS"] = pw

    print("\n== sign ==")
    subprocess.run([signer, "sign",
                    "--ks", args.keystore,
                    "--ks-pass", "env:KS_PASS",
                    "--key-pass", "env:KS_PASS",
                    "--ks-key-alias", args.ks_alias,
                    "--v1-signing-enabled", "true",
                    "--v2-signing-enabled", "true",
                    "--v3-signing-enabled", "true",
                    "--out", out, unsigned], check=True, env=env)
    os.remove(unsigned)
    subprocess.run([signer, "verify", "--print-certs", out], check=True)
    print("\nOK -> %s (%d bytes)" % (out, os.path.getsize(out)))
    print("Install it, then follow docs/00-quickstart.md steps 1-3.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
