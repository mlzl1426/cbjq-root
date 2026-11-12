#!/usr/bin/env python3
"""Check whether a game client APK can talk to a local server as-is
(no repack, no re-sign).

Usage:
    python check-client.py <client.apk> [--ca server-ca.pem]

Only the zip central directory and four small entries are read, so it
works on a 1.5 GB APK without unpacking it.

Checks (all pass = usable directly):
    1. XgAuthUrl / SeasunAuthUrl in assets/sdk_config.properties point at 127.0.0.1
    2. res/xml/network_security_config.xml declares trust-anchors + certificates
    3. a custom CA exists under res/raw/ and matches the server CA fingerprint
    4. package / signature info, for reference only
"""
import argparse
import base64
import hashlib
import re
import sys
import zipfile

CUSTOM_CA_NAMES = ("mikusb_loopback.cer", "miku_ca.cer", "local_ca.cer")


def der_fingerprint(der):
    return ":".join("%02X" % b for b in hashlib.sha256(der).digest())


def pem_to_der(pem):
    body = re.search(
        rb"-----BEGIN CERTIFICATE-----(.+?)-----END CERTIFICATE-----", pem, re.S
    )
    if not body:
        raise SystemExit("not a PEM certificate")
    return base64.b64decode(re.sub(rb"\s+", b"", body.group(1)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("apk")
    ap.add_argument("--ca", help="server CA (PEM); if given, fingerprints are compared")
    args = ap.parse_args()

    z = zipfile.ZipFile(args.apk)
    names = set(z.namelist())
    ok = True

    print("APK       :", args.apk)
    print("entries   :", len(names))

    # 1. SDK endpoints
    print("\n[1] SDK endpoints")
    if "assets/sdk_config.properties" not in names:
        print("    FAIL no assets/sdk_config.properties")
        ok = False
    else:
        props = z.read("assets/sdk_config.properties").decode("utf-8", "replace")
        hits = []
        for key in ("XgAuthUrl", "SeasunAuthUrl", "clientPushDataUrl"):
            m = re.search(rf"^{key}\s*=\s*(.+)$", props, re.M)
            if m:
                hits.append((key, m.group(1).replace("\\:", ":").strip()))
        local = [v for _, v in hits if "127.0.0.1" in v]
        for k, v in hits:
            print(f"    {k:<20} = {v}")
        if hits and len(local) == len(hits):
            print("    OK  all endpoints are 127.0.0.1 -- no repack needed")
        elif local:
            print("    WARN only some endpoints are local")
            ok = False
        else:
            print("    FAIL nothing points at 127.0.0.1 -- this APK must be repacked")
            ok = False

    # 2. trust anchors
    print("\n[2] trust anchors")
    nsc = "res/xml/network_security_config.xml"
    if nsc not in names:
        print("    FAIL no network_security_config.xml")
        ok = False
    else:
        raw = z.read(nsc)
        # binary AXML keeps its string pool as plain text
        has_anchor = b"trust-anchors" in raw
        has_cert = b"certificates" in raw
        has_system = b"system" in raw
        print("    trust-anchors: %s   certificates: %s   system: %s"
              % ("yes" if has_anchor else "NO",
                 "yes" if has_cert else "NO",
                 "yes" if has_system else "NO"))
        if not (has_anchor and has_cert):
            print("    FAIL no trust-anchor declaration; bundled CA will be ignored")
            ok = False

    # 3. bundled CA
    print("\n[3] bundled custom CA")
    found = None
    for n in sorted(names):
        if n.startswith("res/raw/") and n.lower().endswith((".cer", ".crt", ".pem")):
            data = z.read(n)
            der = data if data[:2] == b"0\x82" else pem_to_der(data)
            print("    %s  (%d bytes)" % (n, len(data)))
            print("      fp %s" % der_fingerprint(der))
            if any(c in n for c in CUSTOM_CA_NAMES):
                found = der
    if found is None:
        print("    FAIL no custom CA under res/raw -- local TLS cannot be trusted")
        ok = False
    elif args.ca:
        with open(args.ca, "rb") as f:
            pem = f.read()
        want = der_fingerprint(pem if pem[:2] == b"0\x82" else pem_to_der(pem))
        same = der_fingerprint(found) == want
        print("    server CA  fp %s" % want)
        print("    " + ("OK  fingerprints match" if same
                        else "FAIL fingerprints differ -- handshake will fail"))
        ok = ok and same

    # 4. package info
    print("\n[4] package info")
    sigs = sorted({n.split("/")[1].rsplit(".", 1)[-1]
                   for n in names if n.startswith("META-INF/") and "." in n})
    print("    signatures:", ", ".join(sigs) or "none")

    print("\nRESULT:", "OK  install and play as-is, no repack / re-sign"
          if ok else "FAIL  this APK needs repacking (see docs/04)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
