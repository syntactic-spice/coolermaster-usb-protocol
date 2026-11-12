#!/usr/bin/env python3
"""Talk to the Cooler Master MM712 configuration interface directly.

Written from docs/PROTOCOL.md only. Every report sent and received is
appended to probe/logs/<date>.log so results can be cited as evidence.

Usage (from probe/):  uv run mm712.py <command> [args]   (see --help)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import pathlib
import sys
import time

import hid

VID = 0x2516
PIDS = {0x01B7: ("dongle", 32), 0x0169: ("cable", 64)}
CONFIG_INTERFACE = 3

LOG_DIR = pathlib.Path(__file__).resolve().parent / "logs"

# Block sizes in bytes (PROTOCOL.md 2.1)
PERF_SIZE = 76
BUTTON_SIZE = 33
MACRO_SIZE = 648


class ProtocolError(Exception):
    pass


class MM712:
    def __init__(self, path: bytes, pid: int, log):
        self.kind, self.report_size = PIDS[pid]
        self.pid = pid
        self.dev = hid.device()
        self.dev.open_path(path)
        self.log = log
        self.unsolicited: list[bytes] = []

    # ---- device discovery -------------------------------------------------
    @classmethod
    def open(cls, log, prefer: str | None = None) -> "MM712":
        found = [d for d in hid.enumerate(VID)
                 if d["product_id"] in PIDS and d["interface_number"] == CONFIG_INTERFACE]
        if prefer:
            found = [d for d in found if PIDS[d["product_id"]][0] == prefer]
        if not found:
            raise SystemExit("MM712 configuration interface not found")
        d = found[0]
        # The OS device path contains a machine-specific instance ID; don't log it.
        log(f"# open {PIDS[d['product_id']][0]} {d['product_id']:04x} interface {CONFIG_INTERFACE}")
        return cls(d["path"], d["product_id"], log)

    def close(self):
        self.dev.close()

    # ---- raw reports ------------------------------------------------------
    @property
    def data_end(self) -> int:
        """Index one past the last data byte in a report (PROTOCOL.md 2.1)."""
        return 22 if self.report_size == 32 else 64

    def send(self, msg: bytes):
        if len(msg) > self.report_size:
            raise ValueError("message longer than report")
        buf = bytes(msg) + bytes(self.report_size - len(msg))
        self.log("OUT " + _hex(buf))
        # No report IDs on this interface: hidapi wants a leading 0.
        n = self.dev.write(b"\x00" + buf)
        if n < 0:
            raise ProtocolError(f"write failed: {self.dev.error()}")

    def recv(self, timeout_ms: int = 500) -> bytes | None:
        data = self.dev.read(self.report_size, timeout_ms)
        if not data:
            return None
        b = bytes(data)
        self.log(" IN " + _hex(b))
        return b

    def request(self, msg: bytes, timeout_ms: int = 500) -> bytes:
        """Send one report, return the reply whose byte 0 is msg[0] + 1.

        Unsolicited status reports (0x47) are kept in self.unsolicited unless
        they are the reply being waited for.
        """
        self.send(msg)
        want = (msg[0] + 1) & 0xFF
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            r = self.recv(max(1, int((deadline - time.monotonic()) * 1000)))
            if r is None:
                break
            if r[0] == want:
                return r
            if r[0] == 0x47:
                self.unsolicited.append(r)
        raise ProtocolError(f"no reply to {_hex(msg[:4])}")

    # ---- paged blocks (PROTOCOL.md 2.1) -----------------------------------
    def _page_payload(self, has_idx: bool) -> int:
        return self.data_end - (4 if has_idx else 3)

    def read_block(self, cmd: int, idx: int | None = None) -> bytes:
        has_idx = idx is not None
        start = 4 if has_idx else 3
        out = bytearray()
        page, count = 0, None
        while count is None or page < count:
            # Read requests carry the page number in byte 3 (no slot form seen).
            r = self.request(bytes([cmd, 0x81, 0x01, page]))
            if page == 0:
                if not r[1] & 0x80:
                    raise ProtocolError(f"page 0 reply without count: {_hex(r[:4])}")
                count = r[1] & 0x7F
            elif r[1] != page:
                raise ProtocolError(f"expected page {page}, got {_hex(r[:4])}")
            out += r[start:self.data_end]
            page += 1
        return bytes(out)

    def write_block(self, cmd: int, data: bytes, idx: int | None = None) -> None:
        has_idx = idx is not None
        per = self._page_payload(has_idx)
        pages = [data[i:i + per] for i in range(0, len(data), per)]
        for n, chunk in enumerate(pages):
            b1 = (0x80 | len(pages)) if n == 0 else n
            head = bytes([cmd, b1, 0x02] + ([idx] if has_idx else []))
            msg = head + chunk
            r = self.request(msg)
            if r[1:len(msg)] != msg[1:]:
                raise ProtocolError(f"page {n} echo mismatch: {_hex(r[:len(msg)])}")

    # ---- commands (PROTOCOL.md 3) -----------------------------------------
    def get_profile(self) -> int:
        return self.request(b"\x44\x81\x02")[3]

    def set_profile(self, n: int) -> None:
        r = self.request(bytes([0x44, 0x81, 0x01, n]))
        if r[3] != n:
            raise ProtocolError(f"set profile echo {_hex(r[:5])}")

    def status(self) -> bytes:
        return self.request(b"\x46\x81\x00")

    def commit(self) -> bytes:
        return self.request(b"\x54\x81\x01\x00")

    def read_perf(self) -> bytes:
        return self.read_block(0x4A)

    def write_perf(self, data: bytes) -> None:
        assert len(data) == PERF_SIZE
        self.write_block(0x4A, data)

    def read_buttons(self) -> bytes:
        return self.read_block(0x48)

    def write_buttons(self, data: bytes) -> None:
        assert len(data) == BUTTON_SIZE
        self.write_block(0x48, data)

    def set_button(self, idx: int, typ: int, val: int) -> bytes:
        return self.request(bytes([0x48, 0x81, 0x04, idx, typ, val]))

    def get_debounce(self) -> int:
        return self.request(b"\x5c\x81\x01")[3]

    def set_debounce(self, ms: int) -> bytes:
        return self.request(bytes([0x5C, 0x81, 0x02, ms]))

    def get_led_mode(self) -> int:
        return self.request(b"\x4c\x81\x07")[3]

    def set_led_mode(self, mode: int) -> bytes:
        return self.request(bytes([0x4C, 0x81, 0x08, mode]))

    def get_led_params(self, mode: int) -> bytes:
        return self.request(bytes([0x4C, 0x81, 0x03, mode]))[3:10]

    def set_led_params(self, mode, bright, speed, r, g, b, preset: int | None = None) -> bytes:
        """Byte 4 is a per-mode value the device sets itself (colour preset index?);
        keep the current one unless told otherwise."""
        if preset is None:
            preset = self.get_led_params(mode)[0]
        return self.request(bytes([0x4C, 0x81, 0x04, mode, preset, bright, speed, r, g, b, 0xFF]))

    def read_macro(self, slot: int) -> bytes:
        """Read the used part of a macro slot; b'' if empty (PROTOCOL.md 4.6)."""
        out = bytearray()
        page, count = 0, None
        while count is None or page < count:
            r = self.request(bytes([0x4E, 0x81, 0x01, slot, page]))
            if page == 0:
                count = r[1] & 0x7F if r[1] & 0x80 else 0
                if count == 1 and not any(r[3:]):
                    return b""
            out += r[3:self.data_end]
            page += 1
        return bytes(out)

    def delete_macro(self, slot: int) -> bytes:
        """slot 0..11, or 0xff for all slots of the active profile."""
        return self.request(bytes([0x50, 0x81, 0x05, slot]))

    def write_macro(self, slot: int, mode: int, name: str, events: list[tuple[int, int, int]]) -> None:
        data = bytearray(MACRO_SIZE)
        data[0] = mode
        nb = name.encode("ascii")[:30]
        data[2:2 + len(nb)] = nb
        data[35] = len(events)
        for i, (code, state, delay) in enumerate(events):
            o = 36 + 4 * i
            data[o:o + 4] = bytes([code, state, delay & 0xFF, delay >> 8])
        self.write_block(0x4E, bytes(data), idx=slot)


# ---- decoding helpers (PROTOCOL.md 4) --------------------------------------
POLL = {1: 125, 2: 250, 3: 500, 4: 1000}
LED_MODES = {0: "static", 1: "breathing", 2: "cycle", 3: "off"}


def parse_perf(b: bytes) -> dict:
    dpi = [(int.from_bytes(b[16 + 4 * i:18 + 4 * i], "little"),
            int.from_bytes(b[18 + 4 * i:20 + 4 * i], "little")) for i in range(7)]
    return {
        "flags": f"{b[0]:02x}", "angle_snap": bool(b[0] & 1), "lod_high": bool(b[0] & 2),
        "active_stage": b[1], "polling_hz": POLL.get(b[7], f"?{b[7]}"),
        "os_sens": b[9], "os_dblclick": b[10], "lowpower_pct": b[11],
        "sleep_s": int.from_bytes(b[12:14], "little"),
        "enabled_mask": f"{b[15]:02x}", "dpi": dpi,
        "unknown": {"2": f"{b[2]:02x}", "3": f"{b[3]:02x}", "4-6": _hex(b[4:7]),
                    "8": f"{b[8]:02x}", "14": f"{b[14]:02x}", "44-75": _hex(b[44:76])},
    }


def parse_status(r: bytes) -> dict:
    return {"battery_pct": r[10], "charging": r[11], "wireless": r[12], "profile": r[13],
            "b14": r[14], "b16": r[16], "b17": r[17]}


def _hex(b: bytes) -> str:
    return " ".join(f"{x:02x}" for x in b)


def _parse_hex(s: str) -> bytes:
    return bytes.fromhex(s.replace(":", " "))


# ---- CLI --------------------------------------------------------------------
def make_logger(tag: str, verbose: bool):
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"{_dt.date.today():%Y%m%d}.log"
    fh = path.open("a", encoding="utf-8")
    fh.write(f"\n## {_dt.datetime.now():%Y-%m-%d %H:%M:%S} {tag}\n")

    def log(line: str):
        fh.write(f"{time.monotonic():.3f} {line}\n")
        fh.flush()
        if verbose:
            print(line)
    return log


def cmd_dump(dev: MM712, a):
    p = dev.get_profile()
    print(f"connection: {dev.kind} pid {dev.pid:04x}, report {dev.report_size} bytes")
    print(f"active profile: {p}")
    print("status:", parse_status(dev.status()))
    perf = dev.read_perf()
    print("perf raw:", _hex(perf))
    for k, v in parse_perf(perf).items():
        print(f"  {k}: {v}")
    btn = dev.read_buttons()
    print("buttons raw:", _hex(btn))
    print("  combo enabled:", btn[0])
    print("  normal:", [_hex(btn[1 + 2 * i:3 + 2 * i]) for i in range(8)])
    print("  combo: ", [_hex(btn[17 + 2 * i:19 + 2 * i]) for i in range(8)])
    print("debounce ms:", dev.get_debounce())
    print("led mode:", LED_MODES.get(dev.get_led_mode()))
    for m in range(4):
        print(f"  led params {LED_MODES[m]}:", _hex(dev.get_led_params(m)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true", help="print every report")
    ap.add_argument("--via", choices=["dongle", "cable"], help="pick a connection when both are present")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dump", help="read and decode the active profile")
    sub.add_parser("status", help="request a 0x47 status report")
    p = sub.add_parser("profile", help="get or set the active profile")
    p.add_argument("n", nargs="?", type=int)
    p = sub.add_parser("raw", help="send raw report(s) and print the replies")
    p.add_argument("hex", nargs="+", help="one quoted hex string per report")
    p.add_argument("--listen", type=float, default=0.3, help="seconds to keep reading after each send")
    p = sub.add_parser("perf", help="read-modify-write performance bytes: OFFSET=HEXBYTES ...")
    p.add_argument("assign", nargs="+")
    p.add_argument("--no-commit", action="store_true")
    p = sub.add_parser("dpi", help="set DPI stage (1-based) X [Y]")
    p.add_argument("stage", type=int)
    p.add_argument("x", type=int)
    p.add_argument("y", type=int, nargs="?")
    p.add_argument("--no-commit", action="store_true")
    p = sub.add_parser("button", help="set button entry IDX TYPE VALUE (hex)")
    p.add_argument("idx", type=int)
    p.add_argument("type")
    p.add_argument("value")
    p.add_argument("--no-commit", action="store_true")
    p = sub.add_parser("debounce", help="get or set debounce ms")
    p.add_argument("ms", nargs="?", type=int)
    p.add_argument("--no-commit", action="store_true")
    p = sub.add_parser("led", help="set LED: MODE [BRIGHT SPEED RRGGBB]")
    p.add_argument("mode", type=int)
    p.add_argument("bright", type=int, nargs="?")
    p.add_argument("speed", type=int, nargs="?")
    p.add_argument("rgb", nargs="?")
    p.add_argument("--no-commit", action="store_true")
    p = sub.add_parser("macro", help="write macro SLOT MODE NAME EVENTS (code:state:delay,...; hex code)")
    p.add_argument("slot", type=int)
    p.add_argument("mode", type=int)
    p.add_argument("name")
    p.add_argument("events")
    p.add_argument("--no-commit", action="store_true")
    p = sub.add_parser("macro-read", help="read macro SLOT (0..11) of the active profile")
    p.add_argument("slot", type=int)
    p = sub.add_parser("macro-delete", help="delete macro SLOT (0..11, or 255 for all)")
    p.add_argument("slot", type=int)
    p.add_argument("--no-commit", action="store_true")
    sub.add_parser("commit", help="send the commit command")
    a = ap.parse_args(argv)

    log = make_logger(" ".join(sys.argv[1:]), a.verbose)
    dev = MM712.open(log, a.via)
    try:
        if a.cmd == "dump":
            cmd_dump(dev, a)
        elif a.cmd == "status":
            print(parse_status(dev.status()))
        elif a.cmd == "profile":
            if a.n is not None:
                dev.set_profile(a.n)
            print("active profile:", dev.get_profile())
        elif a.cmd == "raw":
            for h in a.hex:
                dev.send(_parse_hex(h))
                end = time.monotonic() + a.listen
                while time.monotonic() < end:
                    r = dev.recv(50)
                    if r is not None:
                        print(" IN", _hex(r))
        elif a.cmd == "perf":
            b = bytearray(dev.read_perf())
            for item in a.assign:
                off, val = item.split("=")
                vb = _parse_hex(val)
                b[int(off):int(off) + len(vb)] = vb
            dev.write_perf(bytes(b))
            if not a.no_commit:
                dev.commit()
            print(parse_perf(dev.read_perf()))
        elif a.cmd == "dpi":
            b = bytearray(dev.read_perf())
            o = 16 + 4 * (a.stage - 1)
            y = a.x if a.y is None else a.y
            b[o:o + 4] = a.x.to_bytes(2, "little") + y.to_bytes(2, "little")
            dev.write_perf(bytes(b))
            if not a.no_commit:
                dev.commit()
            print("dpi table now:", parse_perf(dev.read_perf())["dpi"])
        elif a.cmd == "button":
            print(_hex(dev.set_button(a.idx, int(a.type, 16), int(a.value, 16))))
            if not a.no_commit:
                dev.commit()
            print("buttons now:", _hex(dev.read_buttons()))
        elif a.cmd == "debounce":
            if a.ms is not None:
                print(_hex(dev.set_debounce(a.ms)))
                if not a.no_commit:
                    dev.commit()
            print("debounce ms:", dev.get_debounce())
        elif a.cmd == "led":
            if a.bright is not None:
                rgb = bytes.fromhex(a.rgb)
                print(_hex(dev.set_led_params(a.mode, a.bright, a.speed, *rgb)))
            print(_hex(dev.set_led_mode(a.mode)))
            if not a.no_commit:
                dev.commit()
            print("led mode:", dev.get_led_mode(), "params:", _hex(dev.get_led_params(a.mode)))
        elif a.cmd == "macro":
            ev = []
            for e in a.events.split(","):
                c, s, d = e.split(":")
                ev.append((int(c, 16), int(s), int(d)))
            dev.write_macro(a.slot, a.mode, a.name, ev)
            if not a.no_commit:
                dev.commit()
            print("macro written")
        elif a.cmd == "macro-read":
            m = dev.read_macro(a.slot)
            if not m:
                print("empty")
            else:
                name = m[2:33].split(b"\0")[0].decode("ascii", "replace")
                n = m[35]
                ev = [(m[36 + 4 * i], m[37 + 4 * i], int.from_bytes(m[38 + 4 * i:40 + 4 * i], "little"))
                      for i in range(n)]
                print(f"mode {m[0]} name {name!r} events {n}:")
                for c, s, d in ev:
                    print(f"  {c:02x} {'down' if s else 'up'} {d} ms")
        elif a.cmd == "macro-delete":
            print(_hex(dev.delete_macro(a.slot)))
            if not a.no_commit:
                dev.commit()
        elif a.cmd == "commit":
            print(_hex(dev.commit()))
        if dev.unsolicited:
            print("unsolicited status:", [parse_status(r) for r in dev.unsolicited])
    finally:
        dev.close()


if __name__ == "__main__":
    main()
