# Deer deterrent MVP

Current direction: PIR-triggered camera capture, a large foreground-change filter, and a buzzer. This detects large changes in the scene; it does not identify deer.

| Folder | Contents |
|---|---|
| [firmware/motion-size](firmware/motion-size/) | Current ESP32-S3 firmware: camera, PIR, size filter, buzzer and TFT |
| [experiments/deer-classifier](experiments/deer-classifier/) | Earlier on-device recognition attempt, unchanged model, score logs and outcome |
| [tests](tests/README.md) | Test sequence, observations and links to the saved image galleries |
| [tests/captures](tests/captures/) | Original JPEGs, metadata, event logs and local HTML galleries |
| [tools](tools/) | USB photo recorder and transfer integrity checks |

See [WIRING.md](WIRING.md) for the working pin map and [SOURCES.md](SOURCES.md) for upstream attribution.

## Current behavior

Keep the view empty during startup reference learning. PIR wakes the camera for up to ten frames. A largest changed region ≥5% in three consecutive frames confirms a large target. The buzzer plays three 1.5-second pulses with 0.5-second gaps.

Confirmed target: no timed cooldown; finish the alarm, observe PIR LOW, then accept the next HIGH. No confirmation in ten frames: two-minute cooldown. Camera errors abort and wait for a new PIR transition. The display shows test status.

The 5% phone/person comparison succeeded with the earlier one-second alarm. Display readability is confirmed. The newer three-pulse alarm and no-cooldown repeat-trigger behavior were built/flashed but still need a physical repeat test. See [tests/README.md](tests/README.md).

To view images offline, open **tests/index.html** locally and select a capture session. No ESP32 connection is needed. These files are prepared locally for review; nothing has been committed or pushed.
