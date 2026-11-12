# MM712 protocol research

CoolerMaster currently does not provide a Linux version of MasterPlus, and [`libratbag`](https://github.com/libratbag/libratbag) doesn't support their mice either.
This means there is no way to change mouse settings on Linux.

Goal: document the Cooler Master MM712 configuration protocol well enough to write a Linux `libratbag` driver.
This repo contains the reconstructed protocol and USB captures. Both 2.4GHz dongle and USB cable modes are covered.
It doesn't contain any code taken from MasterPlus.

## Devices

| Connection | VID:PID | Notes |
|---|---|---|
| 2.4 GHz dongle | `2516:01B7` | "Cooler Master Mice Dongle", 5 HID interfaces (MI_00..MI_04) |
| Wired (USB-C) | `2516:0169` | "MM712 Hybrid Mouse", 5 HID interfaces (MI_00..MI_04); confirmed by enumeration over the cable (`captures/b0_*`, `captures/d1_*`) |

## Clean-room rules

USB captures will be used as the primary source for discerning the protocol. To confirm our findings, we may check symbol names, function signatures, data
structures, etc. as those define the interface needed for interoperability.

We may **not** copy the vendor's implementation:

- No decompiled or disassembled code goes into this repo, not even as snippets.
- All tools and the eventual driver will be written from scratch from
  `docs/PROTOCOL.md`, which describes interface facts.
- Each documented fact should cite its evidence: a capture file in `captures/`
  (preferred) or "observed in MasterPlus <version>, symbol `X`".

USB captures of our own device are our own data and are committed.

### Note
In the end, we did not end up looking at debug symbols at all. All protocol details were gathered purely from USB captures and experimentation.

## Layout

- `docs/PROTOCOL.md` - the protocol specification (facts only)
- `captures/` - labelled `.pcap` USB captures, one change per file, plus `index.md`
- `tools/` - our own capture/decoding scripts
- `probe/` - Python script that talks to the mouse directly for experimentation