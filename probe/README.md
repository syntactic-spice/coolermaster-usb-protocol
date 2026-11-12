# MM712 probe

A small test tool that talks to the MM712 configuration interface directly,
written from `docs/PROTOCOL.md`. It is used to check facts the captures can't
settle: limits, commit behaviour, and per-profile vs global settings.

Close MasterPlus+ before using it, so the two don't interleave requests.

```
uv run mm712.py dump                 # decode the active profile
uv run mm712.py status               # battery / charging / link
uv run mm712.py profile [N]          # get / set active profile (0..4)
uv run mm712.py perf 7=03            # read-modify-write performance bytes
uv run mm712.py dpi 4 1600 [Y]       # set DPI stage (1-based)
uv run mm712.py led 1 255 0 ff8000   # LED mode [brightness speed RRGGBB]
uv run mm712.py button 3 a9 00       # set button entry
uv run mm712.py macro 9 1 name "04:1:20,04:0:20"
uv run mm712.py macro-read 9
uv run mm712.py macro-delete 9
uv run mm712.py raw "44 81 02"       # send raw reports, print replies
```

Writes are committed unless `--no-commit` is given. Every report sent and
received is appended to `logs/<date>.log`.
