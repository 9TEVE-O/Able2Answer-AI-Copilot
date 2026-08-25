# Able2Answer Live Bridge

A Max for Live device that reads the Live Set currently open in Ableton Live and
hands a structured snapshot to Abel.

It is deliberately small. It contains no analysis, no thresholds and no advice —
all of that lives in Python, where it can be tested. The bridge's entire job is:

```
Live  →  inspect  →  normalise  →  emit JSON  →  Abel
```

## Read only

v0.1 calls no setter and no LOM function that changes the Live Set. It reads
properties and nothing else. The producer remains the authority over their
session.

## Why two data sources

The bridge reads from `LiveAPI` **and** from Max's `adstatus`, because the Live
Object Model does not expose the audio interface sample rate or buffer size at
all. There is no `live_set` property for either.

Max for Live runs inside Live's own audio engine, so `adstatus sr` and
`adstatus iovs` report the values Live is genuinely running at. That is why the
patch below wires them into inlets 1 and 2.

Until those inlets report, both values stay `null`, and Abel says the sample
rate is unknown rather than assuming 44100. An assumed sample rate presented as
an observation is precisely the failure this project exists to avoid.

## Patch wiring

`able2answer.bridge.js` expects three inlets:

| Inlet | Source | Carries |
|---|---|---|
| 0 | `metro` / `button` | bang — capture a snapshot now |
| 1 | `adstatus sr` | current sample rate, in Hz |
| 2 | `adstatus iovs` | current I/O vector size, in samples |

Outlet 0 emits the snapshot as a single JSON string, which is sent to Abel over
localhost.

```
[button]   [adstatus sr]   [adstatus iovs]
   |             |               |
   +-------------+---------------+
   |             |               |
[js able2answer.bridge.js]
   |
[JSON string]  →  POST http://127.0.0.1:8765/session/snapshot
```

Drive inlet 0 from a `metro` (2000 ms is a reasonable starting point) to keep
the snapshot fresh; Abel treats an observation older than 30 seconds as stale
and will decline to describe the session from it.

## Status: unverified against Live

**This bridge has not been run inside Ableton Live.** It rests on review of the
Live Object Model, not on execution.

The Python side of the boundary is a different matter — `parse_snapshot` is
covered by tests, including tests built from the exact payload shape documented
here. So the contract is tested; the producer of that contract is not yet.

Verifying it needs a machine with Live and Max for Live installed:

1. Create a Max Audio Effect, place it on any track.
2. Wire the patch as above, pointing `js` at `able2answer.bridge.js`.
3. Bang inlet 0 and confirm the emitted JSON matches
   `tests/fixtures/bridge_payload.json` in shape.

Until someone has done that, treat this component as unproven.
