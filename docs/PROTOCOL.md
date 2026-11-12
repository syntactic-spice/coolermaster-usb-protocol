# MM712 configuration protocol

Status legend: **[confirmed]** seen consistently in captures or probe tests and
explained; **[hypothesis]** fits the data so far but needs a targeted test.

Evidence key: `cap:NN` refers to `captures/NN_*.pcap` (see `captures/index.md`).
`probe` means the fact was checked with our own tool (`probe/mm712.py`, written
from this document) talking to the mouse directly, with MasterPlus closed. Every
report it sent and received is in `probe/logs/`.
Captures were made with MasterPlus+ 196.0341.0412. Everything was observed over
the 2.4 GHz dongle unless it is marked as cable (§1.1, cap:b0..b4, cap:d1).

## 1. Transport

Dongle `2516:01B7`, bcdDevice `0x0155`. It has 5 HID interfaces, and every
endpoint is 32-byte interrupt with bInterval 1:

| Intf | Class/proto | Endpoints | Role |
|---|---|---|---|
| 0 | HID boot keyboard | 0x81 IN | key events from remapped buttons |
| 1 | HID boot mouse | 0x82 IN | pointer reports |
| 2 | HID (no subclass) | 0x83 IN | consumer / system control (2 collections) |
| 3 | HID vendor | 0x84 IN, 0x04 OUT | **configuration protocol** [confirmed] |
| 4 | HID vendor | 0x85 IN, 0x05 OUT | never used by MasterPlus in any capture; not needed by a driver; deliberately not probed (could be a firmware-update channel) |

`cap:00`

### 1.1 Wired [confirmed]

Over the USB cable the mouse enumerates as `2516:0169` "MM712 Hybrid Mouse",
bcdDevice `0x0262` (different from the dongle's `0x0155`). It has the same 5
interfaces and endpoint numbers, but every endpoint is **64 bytes**. Interface 3
carries the same command set, with 64-byte reports (cap:b0..b4).

Differences from the dongle:

- Report size 64 → larger pages (§2.1).
- `58 81 01` (device info) is not sent over the cable; it looks dongle-specific.
- Status report byte 11/12 differ (§4.1).

In these captures the dongle was still plugged in while the cable was
connected.

### 1.2 HID report descriptors [confirmed]

Captured during re-enumeration (cap:d0 dongle, cap:d1 cable). Interfaces 0..2
are identical on both connections.

**Interface 3 (configuration).** No report ID. One input and one output
report of N bytes, where N = 32 over the dongle and 64 over the cable:

```
06 0a ff  09 01  a1 01            Usage Page 0xff0a, Usage 0x01, Collection (Application)
  09 02  a1 00                    Usage 0x02, Collection (Physical)
    06 00 ff  09 03 09 04         Usage Page 0xff00, Usages 0x03, 0x04
    15 80 25 7f 35 00 46 ff 00    Logical -128..127, Physical 0..255
    75 08 95 NN  81 02            Input:  NN × 8 bits   (NN = 0x20 dongle, 0x40 cable)
    09 05 09 06                   Usages 0x05, 0x06
    15 80 25 7f 35 00 46 ff 00
    75 08 95 NN  91 02            Output: NN × 8 bits
  c0
c0
```

**Interface 4** has the same descriptor, except that over the cable its
top-level usage is `0xff0a:0x02`. Over the dongle it is `0xff0a:0x01`, the
same as interface 3. So interface 3 must be selected by **interface number**,
not by usage page/usage.

Consequences for a driver:

- No report ID. With Linux hidraw (and hidapi), a write is the report number
  `0x00` followed by the N data bytes. A read returns the N data bytes with no
  prefix. (Verified with hidapi on Windows by the probe tool; still to be
  verified on Linux.)
- The report size N is not the same on both connections, so it must be taken
  from the descriptor or the PID, not hard-coded.

**Other interfaces** (both connections), for reference:

- **Interface 0, keyboard**, no report ID, 18-byte input:
  - modifiers (8 bits, `e0..e7`) and a reserved byte;
  - a 112-bit key bitmap for usages `04..73`, then 16 bits for `85..94`;
  - LED output, 5 bits.
- **Interface 1, mouse**, no report ID, 12-byte input:
  - 8 buttons (1 byte);
  - X, Y as signed 16-bit relative values;
  - wheel (signed 8-bit) and AC Pan (signed 8-bit);
  - 5 vendor bytes (usage page `0xff00`, usage `0xf1`).
- **Interface 2**, two report IDs:
  - ID 1: consumer control, one 16-bit usage (`0..0x380`);
  - ID 2: system control, 3 bits: bit 0 = Sleep (`0x82`), bit 1 = Power Down
    (`0x81`), bit 2 = Wake Up (`0x83`).

## 2. Framing [confirmed]

- Every message is one report (32 bytes over the dongle, 64 bytes over the
  cable): an interrupt OUT on interface 3 with no HID report ID. Byte 0 is the
  command.
- The device replies on interface 3 IN with byte 0 = command + 1. For single
  reports the rest of the reply usually echoes the request (writes) or carries
  the data (reads).
- Single-report requests: `CMD 81 SUB ARG...`. Unused bytes are zero.
- The device also sends **unsolicited** `0x47` status reports (§4.1).

### 2.1 Paged blocks [confirmed]

Larger structures are read and written as a series of pages. `PG` below is
`0x80 | page_count` on page 0 and the page number on later pages.

**Write** (SUB `02`), one report per page, every page in order:

```
CMD  PG  02  [SLOT]  data...
```

The device echoes each page back as `CMD+1 PG 02 [SLOT] data...`.

**Read** (SUB `01`), one request per page:

```
request:  CMD    81  01  [SLOT]  PAGE
reply:    CMD+1  PG  01  data...            (no SLOT echo; data from byte 3)
```

The page count comes from the page-0 reply.

- SLOT (macro slot) is present only for block `0x4e`. Blocks `0x4a`
  (performance) and `0x48` (buttons) have no SLOT, so their data starts at
  byte 3 in both directions.
- Macro writes have the slot at byte 3, so their data starts at byte 4. Macro
  read replies have no slot byte, so their data starts at byte 3.
- Data stops at byte 21 on the dongle (32-byte reports; bytes 22..31 are
  zero) and at byte 63 on the cable (64-byte reports). Why the dongle leaves
  10 bytes unused is unknown.

| Block | Size | Dongle (32-byte reports) | Cable (64-byte reports) |
|---|---|---|---|
| `0x4a` performance | 76 | 4 pages × 19 | 2 pages × 61 |
| `0x48` buttons | 33 | 2 pages × 19 | 1 page × 61 (`PG` = `0x81`) |
| `0x4e` macro slot, write | 648 | 36 pages × 18 | 11 pages × 60 |
| `0x4e` macro slot, read | up to 648 | pages × 19, only as many as the macro needs | not tested over the cable |

### 2.2 Commit [confirmed]

Every MasterPlus change ends with `54 81 01 00` (reply `55 81 01 00`).

Checked with probe:

- Writes take effect immediately and read back without the commit.
- Switching the active profile (`44 81 01 n`) **discards uncommitted
  changes**: the mouse reloads the profile from its stored copy. Polling
  written as 500 Hz without commit read back as 1000 Hz after switching
  1 → 0.
- So `54 81 01` saves the active profile, and a driver must commit before
  switching profile.
- Power cycle (probe): saved stage 7 = 19100 (committed) and unsaved polling =
  500 Hz (not committed), then switched the mouse off and on with the cable
  unplugged. Afterwards stage 7 read 19100 and polling 1000 Hz. **Committed
  changes persist; uncommitted ones are lost at power-off.**

No handshake is needed. The probe tool opens interface 3 and sends commands
straight away, without the `58`/`46` sequence MasterPlus uses at startup.

### 2.3 Typical write sequence (MasterPlus)

`44 81 02` (get active profile) → read the block → write the whole block with
one field changed → `54 81 01` (commit). cap:10, cap:20.

## 3. Command summary

| Cmd | Sub | Arg | Meaning | Status |
|---|---|---|---|---|
| `44` | `02` | - | get active profile → reply byte 3 = profile 0..4 | confirmed |
| `44` | `01` | n | set active profile n; device then sends a `0x47` status report | confirmed |
| `46` | `00` | - | request `0x47` status report | confirmed |
| `48` | `01`/`02` | page | read/write button map block (§4.4) | confirmed |
| `48` | `04` | idx, type, value | set a single button entry; idx 0..7 normal layer, 8..15 combo layer | confirmed (cap:66, cap:96) |
| `48` | `05` | - | read Combo enable → reply byte 3 = 0/1 | confirmed (probe) |
| `48` | `06` | 0/1 | set Combo enable; block byte 0 follows immediately. MasterPlus sends it before every button-block write | confirmed (cap:90, cap:91, probe) |
| `4a` | `01`/`02` | page | read/write performance block (§4.2) | confirmed |
| `4a` | `03` | - | read the first 15 bytes of the performance block (single report) | confirmed |
| `4a` | `04` | 15 bytes | write those 15 bytes | confirmed (cap:10-17) |
| `4c` | `03` | mode | read lighting parameters for a mode (§4.5) | confirmed |
| `4c` | `04` | mode, params | write lighting parameters for a mode; the device then sends a `0x47` | confirmed |
| `4c` | `07` | - | read active lighting mode | confirmed |
| `4c` | `08` | mode | set active lighting mode | confirmed |
| `4c` | `05` | n | read LED palette entry n (0..7) → reply bytes 3..5 = R G B (§4.5). Global, same on every profile | confirmed (probe) |
| `4e` | `01` | slot, page | read macro slot (§4.6) | confirmed (probe) |
| `4e` | `02` | page, slot | write macro slot (36 pages dongle / 11 cable) | confirmed (cap:66, probe) |
| `4e` | `06` | `00` | sent after some macro assignments; unknown | - |
| `50` | `05` | slot / `ff` | delete macro slot 0..11 of the active profile; `ff` = all slots. MasterPlus sends `ff` before rewriting the macros it needs | confirmed (probe) |
| `54` | `01` | - | commit / save | confirmed |
| `58` | `01` | - | device info → `59 81 01 01 cd 55 0f 00 00 04 00 00 50 03`; dongle only | hypothesis |
| `5c` | `01` | - | read button debounce time (ms) | confirmed |
| `5c` | `02` | ms | write button debounce time, 1..6 ms | confirmed (cap:34-37) |

## 4. Data layouts

### 4.1 Status report `0x47` [partial]

`47 81 50 03 00 00 f2 9b 1e 00 BB CC WW PP SS ff LM LP`

Bytes 2..9 (`50 03 00 00 f2 9b 1e 00`) and 15 (`ff`) were the same in every
report on both connections; their meaning is unknown.

| Byte | Meaning |
|---|---|
| 10 | battery % [confirmed]: dongle 25 (`0x19`); cable charging 42 → 43; dongle charging 52 → 51 (cap:00, cap:b0, cap:c0). The value reads about 10 points higher while charging (probe: 63 % charging → 53 % right after unplugging) |
| 11 | charging: `01` charging, `00` not [confirmed: `01` on cable and on dongle while charging, `00` on dongle unplugged] |
| 12 | link: `01` wireless (dongle), `00` cable [confirmed: `01` on dongle charging or not, `00` on cable] |
| 13 | active profile 0..4 [confirmed] |
| 14 | active DPI stage index, 0-based, the same as performance byte 1 [confirmed (probe): followed byte 1 through 0..6 on profile 0; matched byte 1 on all 5 profiles. Enabled mask, polling and LED settings did not move it] |
| 16 | active LED mode, as `4c 81 07` [confirmed (probe): followed mode changes 0..3; matched all 5 profiles] |
| 17 | PRESET byte of the active LED mode (§4.5) [confirmed (probe): followed mode changes and PRESET writes] |

The device sent a `0x47` on its own about 11 s after MasterPlus finished, when
the battery % changed (cap:b0 frame 749). So battery changes are reported
unsolicited.

### 4.2 Performance block (`0x4a`, 76 bytes)

Offsets into the concatenated block. Bytes 0..14 are also the "short" block
for `4a 81 03` / `4a 81 04`.

| Off | Size | Meaning | Values / evidence |
|---|---|---|---|
| 0 | 1 | flags: bit0 angle snapping, bit1 high lift-off distance, bit2 unknown (set on profile 0 only) | `04` default, `05` snap on (cap:24), `06` LOD high (cap:26) [confirmed] |
| 1 | 1 | active DPI stage, 0-based (mirrored in status byte 14) | cap:30, cap:31, probe [confirmed] |
| 2 | 1 | `ff` | ? |
| 3 | 1 | `01` in profile 0, `00` in profiles 1-4 | ? |
| 4-6 | 3 | `00 00 01` | ? |
| 7 | 1 | polling rate: 1=125, 2=250, 3=500, 4=1000 Hz | cap:20-23 [confirmed] |
| 8 | 1 | `00` | ? |
| 9 | 1 | OS pointer sensitivity 1..11 (only stored; applied by host) | cap:38 [confirmed] |
| 10 | 1 | OS double-click speed 1..11 (only stored; applied by host) | cap:3a [confirmed] |
| 11 | 1 | wireless low-power threshold, % (5..95) | cap:15-17 [confirmed] |
| 12-13 | 2 | wireless sleep timeout, seconds, u16 LE: 60/120/180/300/600/900; "never" = `0x5c10` | cap:10-14 [confirmed] |
| 14 | 1 | `00` | ? |
| 15 | 1 | enabled DPI stages bitmask, bit n = stage n | `0a`→`0e` enabling stage 3 (cap:32) [confirmed] |
| 16-43 | 28 | DPI table: 7 × (X u16 LE, Y u16 LE). X and Y are independent. The firmware caps values at 38000; anything below that (including 0) is stored as-is, with no step enforced. The MasterPlus UI range is 100..38000 | cap:00, cap:40, probe [confirmed] |
| 44-75 | | `ff ff 00 00 00 ff ff 00 ff 00 ff 00 00 ff ff ff 80 00 ff`, then zeros | ? (unchanged by everything so far) |

A driver should treat the `?` bytes as opaque: read the block, change only
known fields, and write it back.

**Per-profile vs global (probe):**

- **Global:** bytes 11-13 (low-power threshold, sleep timeout). They are
  stored in this per-profile block, but writing them on profile 1 changed the
  values read on profile 0 too.
- **Per-profile:** polling rate (byte 7) and flags (byte 0). Profile 1 set to
  500 Hz with high lift-off; profile 0 stayed at 1000 Hz / low.
- Not tested individually: the DPI table, active stage and enabled mask.
  They differ between profiles in cap:00, so they are per-profile.

Note: once, MasterPlus itself wrote stage 2 as X=800, Y=0 (cap:20-27). It
fixed itself the next time the stage was selected (cap:30). This looks like a
MasterPlus UI bug, not device behaviour.

### 4.3 Button debounce

Separate command `5c`, value in ms (UI range 1..6). It is not part of the
performance block. **Global** (probe: set to 5 on profile 1, read back as 5 on
profile 0).

### 4.4 Button map block (`0x48`, 33 bytes) [confirmed]

```
off 0      : Combo enable (1 = on, 0 = off)             cap:90, cap:91
off 1..16  : normal layer, entries 0..7, 2 bytes each
off 17..32 : Combo (shift) layer, entries 8..15, 2 bytes each
```

While Combo is enabled, the button whose combo-layer entry is `fe 00` acts as
the shift key; the UI then labels it "COMBO" instead of its normal action.
With Combo disabled, the UI shows the normal entry for that button (wheel
click) again (cap:90). [hypothesis: the firmware ignores that button's
normal entry while Combo is on; not tested by pressing]

Entry order (physical button), established by remapping each one (cap:61-65,
cap:92, cap:94):

| Normal idx | Combo idx | Button | Default normal | Default combo |
|---|---|---|---|---|
| 0 | 8 | left | `a5 00` | `00 00` |
| 1 | 9 | right | `a6 00` | `00 00` |
| 2 | 10 | middle (wheel click) | `a7 00` | `fe 00` (Combo shift key) |
| 3 | 11 | back (rear side) | `a9 00` | `fd 2a` (LED mode) |
| 4 | 12 | forward (front side) | `aa 00` | `fd 20` (LED colour) |
| 5 | 13 | bottom button | `fd 15` (DPI cycle +) | `00 00` |
| 6 | 14 | wheel up | `ad 01` | `ad 01` |
| 7 | 15 | wheel down | `ad ff` | `ad ff` |

#### Entry encoding (type, value) [confirmed unless marked]

Mouse buttons and wheel:

| Type | Value | Meaning | Evidence |
|---|---|---|---|
| `00` | `00` | disabled | cap:64, cap:92 |
| `a5` | `00` | left click | cap:62 |
| `a6` | `00` | right click | default |
| `a7` | `00` | middle click | cap:61 |
| `a9` | `00` | browser back (button 4) | cap:63 |
| `aa` | `00` | browser forward (button 5) | default |
| `ad` | `01` / `ff` | wheel up / down (signed step) | default |
| `fe` | `00` | Combo (shift) key | default |

Multimedia / launch / system (value always `00`). The "Sends" column is what
the mouse reported on interface 2 when the button was pressed: consumer usage
for report ID 1, system-control bit for report ID 2 (§1.2).

| Type | Sends | Evidence |
|---|---|---|
| `e8` | consumer `0x00e9` Volume Up | probe |
| `e9` | consumer `0x00ea` Volume Down | probe |
| `ea` | consumer `0x00e2` Mute | probe |
| `eb` | stop (UI label) | cap:85 |
| `ec` | consumer `0x00cd` Play/Pause | cap:84, cap:94, probe |
| `ed` | next track (UI label) | cap:86 |
| `ee` | previous track (UI label) | cap:87 |
| `ef` | consumer `0x0225` WWW Forward | probe |
| `f0` | consumer `0x0224` WWW Back | probe |
| `f1` | consumer `0x0221` WWW Search | probe |
| `f2` | consumer `0x022a` WWW Favorites | probe |
| `f3` | consumer `0x0227` WWW Refresh | probe |
| `f4` | consumer `0x0226` WWW Stop | probe |
| `f5` | web browser (UI label) | cap:80 |
| `f6` | e-mail (UI label) | cap:81 |
| `f7` | media player (UI label) | cap:83 |
| `f8` | consumer `0x0194` My Computer | probe |
| `f9` | calculator (UI label) | cap:82 |
| `fa` | **system Sleep** (report ID 2, `02 01`, usage `0x82`) | probe |
| `fb` | **system Power Down** (`02 02`, usage `0x81`) | probe |
| `fc` | **system Wake Up** (`02 04`, usage `0x83`) | probe |

Only `e8`..`ea`, `ec`, `ef`..`f4`, `f8` and `fa`..`fc` were tested by pressing
the button; the other UI-labelled codes were not re-checked that way.

**`fa`..`fc` act on the host.** Windows maps them to the sleep/power button
actions. Probe results: `probe/logs/volume-codes-20261112-043616.txt` and
`…-060514.txt`. Raw reports: the `MEDIA` lines in `probe/logs/20261112.log`.

Special functions, type `fd`:

| Value | Meaning | Evidence |
|---|---|---|
| `03`..`07` | switch to profile 1..5 | cap:76-7a |
| `0b` / `0c` | profile cycle up / down | cap:7b, cap:7c |
| `0d`..`13` | jump to DPI stage n = value − `0c` (1..7); `0e` = stage 2 and `10` = stage 4 seen [hypothesis for the other stages] | cap:70, cap:71 (UI only offers enabled stages) |
| `15` / `16` | DPI cycle up / down | cap:74, cap:75 |
| `17` | sensor on/off | cap:88 |
| `20` | change LED colour (combo default; not offered in the menu) | default + UI label |
| `2a` | change LED mode (combo default; not offered in the menu) | default + UI label |
| `2c` / `2d` | DPI + / DPI - | cap:72, cap:73 |

Macros, type `ff`: value = macro slot (§4.6). Keyboard keys/combos and rapid
fire are both implemented by MasterPlus as macros (cap:66, cap:8a, cap:96).

### 4.5 Lighting [confirmed]

Single-zone (logo). Modes: `0` static, `1` breathing, `2` colour cycle, `3` off.

Write parameters: `4c 81 04 MODE PRESET BRIGHT SPEED R G B ff`
(cap:50-5h), followed by `4c 81 08 MODE` (select mode) and the commit.
Read: `4c 81 03 MODE` → `4d 81 03 PRESET BRIGHT SPEED R G B ff`.

- PRESET: a per-mode byte that is stored as written (probe: `ff` survived a
  reload from flash). MasterPlus always writes `ff`. Values seen on profiles
  MasterPlus never wrote are `06` and `07`, varying by profile and mode.
  [hypothesis: an index into the LED palette below, used by the "change LED
  colour" button; `ff` = custom colour. Supported by profile 0's static mode
  having `06` with colour `ff00ff`, which is palette entry 6, but profile 0's
  breathing mode had `07` (white) with colour `ff8000`.] A driver should read
  it and write it back unchanged.
- BRIGHT: 0..255 (half = `7e`).
- SPEED: 0..4, slowest to fastest; larger values are clamped to 4 (probe).
  MasterPlus's 5 UI ticks map to 0..3 plus `02` for the fastest tick, which
  looks like a MasterPlus bug.
- R, G, B: 0..255.
- Off (mode 3) sends only `4c 81 08 03`.

**Palette** (probe): `4c 81 05 n` returns a fixed colour in reply bytes
3..5. MasterPlus reads entry 6 at startup. The palette was the same on profiles
0 and 3, so it is global:

| n | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| RGB | `ff0000` | `ff8000` | `ffff00` | `00ff00` | `00ffff` | `0000ff` | `ff00ff` | `ffffff` |

Indexes above 7 return arbitrary entries (8 → white, `ff` → cyan). No palette
write command has been seen.

### 4.6 Macros

#### Storage and assignment [confirmed]

- MasterPlus always uses **slot = button entry index** (back button → slot 3,
  combo-layer right button → slot 9). Then it sets the entry to `ff <slot>`
  with `48 81 04 <idx> ff <slot>` and commits (cap:66, cap:96, cap:a0).
- Write: `4e PG 02 <slot> data`, 648 bytes per slot. Over the dongle that is
  36 pages of 18 bytes (page 0 = `0xa4`); over the cable, 11 pages of 60
  bytes (page 0 = `0x8b`, cap:b3).
- **12 slots, 0..11, per profile** (probe). A macro written to slot 10 on
  profile 0 was absent on profile 1. Writes to slot ≥ 12 are echoed but not
  stored, and reads of slot ≥ 12 return slot 11.
- The button entry holds the slot number, so a driver can choose any free
  slot. MasterPlus's slot = entry index convention only works for entries
  0..11 [hypothesis: an entry pointing at an arbitrary slot works; not yet
  verified by pressing the button].
- **Read** (probe): `4e 81 01 <slot> <page>`.
  - Reply byte 1 is `0x80 | page_count` on page 0 and the page number after
    that. Byte 2 is `01`, and data starts at **byte 3** with no slot echo (19
    bytes per page over the dongle).
  - Only the used part is returned (3 pages for a 2-event macro).
  - An empty slot returns a single all-zero page, `4f 81 01 00`.
  - MasterPlus's startup reads are `4e 81 01 <slot>` without a page byte,
    which is page 0. They all came back empty: in cap:00 no macros had been
    written yet, and before cap:b0 MasterPlus had deleted its test macros
    with `50 81 05 ff` (below) when the buttons were reassigned.
- **Delete** (probe): `50 81 05 <slot>` deletes one slot; `50 81 05 ff`
  deletes all 12 slots of the active profile.
  - MasterPlus sends `50 81 05 ff` before writing any macro, then rewrites
    only the macros that are still assigned.
  - Delete is subject to the same commit rule as other writes.
- Macros created in the MasterPlus Macros tab live only in MasterPlus until
  they are assigned to a button. Deleting one there sends nothing (cap:a5).
- MasterPlus's delete-all leaves nothing behind. A probe round trip (write
  mode 2 with 4 events and delays of 15/300/20/1000 ms, then read back) returned
  exactly what was written.

#### Slot layout [confirmed for bytes 0, 35, 36..; name start confirmed, name length hypothesis]

Offsets into the 648-byte concatenated data:

| Off | Size | Meaning | Evidence |
|---|---|---|---|
| 0 | 1 | play mode: `01` run once, `02` hold to loop, `03` toggle loop | cap:a1-a3 |
| 1 | 1 | `00` | ? |
| 2..34 | ≤ 33 | name, ASCII, NUL-terminated (MasterPlus uses it to show the assignment, e.g. `(KB):L_CTRL+L_SHIFT+A+B`, `RF( LEFT CLICK ) * 3`, `T1`). The longest name seen is 23 characters; the end of the field is inferred from where the event count starts | cap:66, cap:8a, cap:96, cap:a0 |

Bytes 33..34 were `b7 b9` over the dongle and `b7 b6` over the cable: leftover
host memory inside the name field, not a constant (cap:b3).
| 35 | 1 | number of events | `02`, `04`, `06`, `08` (cap:66, cap:a0, cap:8a, cap:96) |
| 36.. | 4 × n | events | |

Room for (648 − 36) / 4 = 153 events, consistent with MasterPlus's
`maxMacroEvent: 152` in its profile export.

**MasterPlus does not zero the buffer.** Bytes after the name's NUL and after
the last event contain host memory left over in the buffer. A driver should
write zeros there.

#### Event format [confirmed]

`CODE STATE DELAY_LO DELAY_HI`

- CODE: HID keyboard usage (`04` = A, `05` = B, `1b` = X, `1c` = Y,
  `e0` = LCtrl, `e1` = LShift), or a mouse-button code from §4.4 (`a5` = left).
- STATE: `01` = press, `00` = release.
- DELAY: u16 LE, milliseconds to wait after the event (cap:a0: 64, 358, 185, 3).

Keyboard combos are pressed in order and released in reverse (cap:96).
Rapid fire "×3" = 3 press/release pairs with 20 ms delays (cap:8a).

## 5. Profiles [confirmed]

- 5 profiles (0..4). Per-profile blocks (`0x4a`, `0x48`, `0x4c`, `0x4e`)
  address the **active** profile; there is no profile argument.
- To read or write profile n: `44 81 01 n`, then use the blocks, then switch
  back. This is exactly what MasterPlus does at startup (cap:00).
- **Commit (`54 81 01`) before switching away** from a profile you changed,
  or the changes are lost (§2.2).
- Not everything reached through the per-profile commands is per-profile.
  These are **global** (probe):
  - debounce (`5c`);
  - low-power threshold and sleep timeout (performance bytes 11..13);
  - the LED palette (`4c 81 05`).

## 6. Open questions

Not needed for a basic driver (preserve, don't interpret):

- Interface 4's role (deliberately not probed).
- Performance bytes 2, 3, 4..6, 8, 14, flag bit 2, and the tail 44..75.
- Status report bytes 2..9 and 15; the `58 81 01` device-info reply
  (dongle only).
- `4e 81 06 00`, which MasterPlus sends after some macro assignments.

Need a button press or other manual step:

- Whether a button entry can point at a macro slot other than its own index.
- Macro byte 1.
- LED PRESET meaning (palette-index hypothesis, §4.5). Test by pressing the
  "change LED colour" Combo button and reading the PRESET and RGB bytes.
- Whether the firmware ignores the Combo shift button's normal entry (§4.4).
- Cable connection with the dongle unplugged; macro reads over the cable.

Need Linux:

- Confirm the hidraw write/read format (§1.2) and that interface 3 is
  reachable via hidraw with the kernel's default bindings.
