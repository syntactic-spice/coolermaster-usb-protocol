#!/usr/bin/env python3
"""Find which button-action codes send volume up/down/mute.

Puts each candidate one-byte action code on the forward (front side) button,
asks you to press it, and records what the mouse reports on its consumer /
system-control interface (interface 2). The forward button is restored to
"browser forward" (aa 00) at the end, even on Ctrl-C.

Run from probe/ with MasterPlus closed:  uv run volume_codes.py
"""
from __future__ import annotations

import datetime as dt
import sys
import time

import hid

from mm712 import LOG_DIR, MM712, PIDS, VID, make_logger

TEST_BUTTON = 4          # forward (front side button)
RESTORE = (0xAA, 0x00)   # browser forward
BUTTON_NAME = "FORWARD (front side)"
CONTROL = 0xEC  # play/pause, known (cap:84)
# fa/fb/fc send System Sleep / Power Down / Wake Up, so they are not in the
# default list; pass them explicitly with the power buttons set to "Do nothing"
# (see logs/volume-codes-20261112-060514.txt).
CANDIDATES = [0xE8, 0xE9, 0xEA, 0xEF, 0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF8]
WAIT_S = 20.0

CONSUMER_NAMES = {
    0x00E2: "Mute", 0x00E9: "Volume Up", 0x00EA: "Volume Down", 0x00CD: "Play/Pause",
    0x00B7: "Stop", 0x00B5: "Next Track", 0x00B6: "Previous Track", 0x0183: "Media Player",
    0x018A: "E-mail", 0x0192: "Calculator", 0x0196: "Web Browser", 0x0194: "My Computer",
    0x0221: "WWW Search", 0x0223: "WWW Home", 0x0224: "WWW Back", 0x0225: "WWW Forward",
    0x0226: "WWW Stop", 0x0227: "WWW Refresh", 0x022A: "WWW Favorites",
}
# Bit order from the interface-2 report descriptor: usages 0x82, 0x81, 0x83.
SYSTEM_NAMES = {1: "Sleep", 2: "Power Down", 4: "Wake Up"}


def open_media_interfaces(pid: int) -> list[hid.device]:
    devs = []
    for d in hid.enumerate(VID, pid):
        if d["interface_number"] == 2:
            h = hid.device()
            h.open_path(d["path"])
            h.set_nonblocking(True)
            devs.append(h)
    return devs


def describe(report: bytes) -> str:
    if not report:
        return "?"
    rid = report[0]
    if rid == 1 and len(report) >= 3:
        u = int.from_bytes(report[1:3], "little")
        if u == 0:
            return "consumer release"
        return f"consumer 0x{u:04x} {CONSUMER_NAMES.get(u, '(unknown)')}"
    if rid == 2 and len(report) >= 2:
        bits = report[1] & 0x07
        if bits == 0:
            return "system release"
        return "system " + ", ".join(n for b, n in SYSTEM_NAMES.items() if bits & b)
    return "raw " + report.hex(" ")


def wait_for_press(media: list[hid.device], log) -> list[str]:
    seen: list[str] = []
    end = time.monotonic() + WAIT_S
    while time.monotonic() < end:
        for h in media:
            r = h.read(16)
            if r:
                b = bytes(r)
                log(f" MEDIA {b.hex(' ')}")
                seen.append(describe(b))
        if seen and any("release" in s for s in seen):
            time.sleep(0.2)
            break
        time.sleep(0.005)
    return seen


def main():
    # Optional: hex codes to test instead of CANDIDATES, e.g. `uv run volume_codes.py fb fc`
    codes = [int(x, 16) for x in sys.argv[1:]] or CANDIDATES
    risky = [c for c in codes if c >= 0xFA]
    if risky:
        print("WARNING: codes", " ".join(f"{c:02x}" for c in risky), "may send system Power Down / Sleep / Wake.")
        print("Set Windows' power button and sleep button actions to 'Do nothing' first,")
        print("or the PC may sleep or shut down when the button is pressed.")
        if input("Type 'yes' to continue: ").strip().lower() != "yes":
            sys.exit("aborted")
    log = make_logger("volume_codes " + " ".join(f"{c:02x}" for c in codes), False)
    dev = MM712.open(log)
    media = open_media_interfaces(dev.pid)
    if not media:
        sys.exit("could not open interface 2 (media keys)")
    results: list[tuple[int, list[str]]] = []
    print(f"Connected via {dev.kind}. Each step: press and release the {BUTTON_NAME} button once.")
    print(f"If nothing happens within {WAIT_S:.0f} s the step is recorded as 'nothing'.")
    print("Some steps may change the system volume or pause media.\n")
    input("Press Enter to start ...")
    try:
        for code in [CONTROL] + codes:
            dev.set_button(TEST_BUTTON, code, 0x00)
            label = "control (play/pause)" if code == CONTROL else "candidate"
            print(f"[{code:02x}] {label}: press the forward button now ...", flush=True)
            seen = wait_for_press(media, log)
            shown = ", ".join(s for s in seen if "release" not in s) or "nothing on interface 2"
            print(f"      -> {shown}")
            results.append((code, seen))
            if any("Mute" in s for s in seen):
                print("      Mute toggled. Press the forward button once more to unmute ...", flush=True)
                wait_for_press(media, log)
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        out = LOG_DIR / f"volume-codes-{dt.datetime.now():%Y%m%d-%H%M%S}.txt"
        with out.open("w", encoding="utf-8") as fh:
            for code, seen in results:
                fh.write(f"{code:02x}: {'; '.join(seen) if seen else 'nothing'}\n")
        print(f"\nResults written to {out}")
        try:
            dev.set_button(TEST_BUTTON, *RESTORE)
            dev.commit()
            print("Forward button restored to browser forward (aa 00).")
        except Exception as e:  # e.g. the device stopped answering after a system sleep
            print(f"Could not restore the forward button ({e}).")
            print("It was never saved: power-cycle the mouse to discard the test code.")
        for h in media:
            h.close()
        dev.close()
    input("Press Enter to close.")


if __name__ == "__main__":
    main()
