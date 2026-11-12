#!/usr/bin/env python3
"""Print the MM712 vendor-interface reports from a USB capture.

Usage: decode.py CAPTURE [--all] [--tshark PATH]

Shows each 32-byte (dongle) or 64-byte (cable) report on the configuration interface (OUT ep 0x04,
IN ep 0x84) as hex, one per line, with trailing zero bytes trimmed. By default
repeated identical request/reply pairs are shown only once; --all shows
everything in order.
"""
import argparse
import os
import shutil
import subprocess
import sys

OUT_EP, IN_EP = "0x04", "0x84"


def find_tshark():
    """$TSHARK, then PATH, then the usual Windows install locations."""
    if os.environ.get("TSHARK"):
        return os.environ["TSHARK"]
    found = shutil.which("tshark")
    if found:
        return found
    candidates = [os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Wireshark", "tshark.exe")]
    if os.environ.get("USERPROFILE"):
        candidates.append(os.path.join(os.environ["USERPROFILE"], "scoop", "apps", "wireshark", "current", "tshark.exe"))
    for c in candidates:
        if os.path.isfile(c):
            return c
    return "tshark"


def reports(path, tshark):
    # 32-byte reports over the dongle, 64-byte reports over the cable.
    flt = f"(usb.data_len == 32 || usb.data_len == 64) && (usb.endpoint_address == {OUT_EP} || usb.endpoint_address == {IN_EP})"
    cmd = [tshark, "-r", path, "-Y", flt,
           "-T", "fields", "-E", "separator=\t",
           "-e", "frame.number", "-e", "frame.time_relative", "-e", "usb.endpoint_address",
           "-e", "usb.capdata", "-e", "usbhid.data"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    for line in res.stdout.splitlines():
        cols = line.split("\t")
        frame, t, ep = cols[0], float(cols[1]), cols[2]
        data = next((c for c in cols[3:] if c), "")
        yield int(frame), t, ("OUT" if ep == OUT_EP else " IN"), bytes.fromhex(data.replace(":", ""))


def fmt(b):
    end = len(b)
    while end > 4 and b[end - 1] == 0:
        end -= 1
    return " ".join(f"{x:02x}" for x in b[:end])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--tshark", default=find_tshark())
    a = ap.parse_args()
    seen = set()
    for frame, t, d, b in reports(a.capture, a.tshark):
        key = (d, b)
        if not a.all and key in seen:
            continue
        seen.add(key)
        print(f"{frame:5d} {t:8.3f} {d} {fmt(b)}")


if __name__ == "__main__":
    sys.exit(main())
