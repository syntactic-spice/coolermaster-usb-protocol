#!/usr/bin/env python3
"""Find what status-report byte 14 tracks.

Changes one setting at a time WITHOUT committing, requests a status report
after each, and prints bytes 14..17. Uncommitted changes are then discarded by
switching to another profile and back (PROTOCOL.md 2.2).

Run from probe/ with MasterPlus closed:  uv run status_b14.py
"""
from mm712 import MM712, make_logger


def main():
    log = make_logger("status_b14", False)
    dev = MM712.open(log, "dongle")
    home = dev.get_profile()
    perf0 = dev.read_perf()
    mode0 = dev.get_led_mode()

    def st(label):
        r = dev.status()
        print(f"{label:34s} b14={r[14]:02x} b15={r[15]:02x} b16={r[16]:02x} b17={r[17]:02x}")

    def perf(**changes):
        b = bytearray(perf0)
        for off, val in changes.items():
            b[int(off[1:])] = val
        dev.write_perf(bytes(b))

    try:
        st("baseline")
        for stage in range(7):
            perf(o1=stage)
            st(f"active stage index {stage}")
        perf()
        for mask in (0x01, 0x03, 0x7F):
            perf(o15=mask)
            st(f"enabled mask {mask:02x}")
        perf()
        for rate in (1, 2, 3):
            perf(o7=rate)
            st(f"polling code {rate}")
        perf()
        for m in (0, 2, 3):
            dev.set_led_mode(m)
            st(f"led mode {m}")
        dev.set_led_mode(mode0)
        p = dev.get_led_params(mode0)
        for speed in (1, 4):
            dev.set_led_params(mode0, p[1], speed, p[3], p[4], p[5], preset=p[0])
            st(f"led speed {speed}")
        for bright in (0x10, 0x80):
            dev.set_led_params(mode0, bright, p[2], p[3], p[4], p[5], preset=p[0])
            st(f"led brightness {bright:02x}")
    finally:
        other = 1 if home != 1 else 0
        dev.set_profile(other)
        dev.set_profile(home)
        ok = dev.read_perf() == perf0 and dev.get_led_mode() == mode0
        st("after discard (profile switch)")
        print("restored:", ok)
        dev.close()


if __name__ == "__main__":
    main()
