# Deer deterrent MVP

**Start with [the team handoff](handoff/START_HERE.md).** Current device: Adafruit ESP32-S3 TFT Feather + OV5640 + PIR + RGB, with optional passive buzzer. Last flashed October 31, 2026; handoff organized November 1.

| Location | Purpose |
|---|---|
| [handoff](handoff/START_HERE.md) | Current state, findings by part, runbook, known issues and outdoor-test template |
| [firmware/motion-size](firmware/motion-size/README.md) | Current 10%-plus-growth firmware and optional camera diagnostic |
| [experiments/deer-classifier](experiments/deer-classifier/README.md) | Earlier recognition model, diagnostic source, score logs and failed recognition result |
| [experiments/camera-wifi-bringup](experiments/camera-wifi-bringup/README.md) | Historical Arduino Wi-Fi camera/PIR-burst prototype; not the current firmware |
| [tests](tests/README.md) | Test results and original local photo galleries |
| [tools](tools/) | USB recorder, requirements and transfer checks |
| [WIRING.md](WIRING.md) | Current wiring; replaces older prototype diagrams |
| [SOURCES.md](SOURCES.md) | Attribution and evidence provenance |

Current trigger: PIR starts up to ten photos; five spatially associated frames must show at least 25% net growth and two percentage points of image-area gain, with the last three at least 10% of the image. At least two growth steps must exceed the per-step floor. Confirmation produces 5.5 seconds of white flashes and the buzzer signal. No timed cooldown follows confirmation; unconfirmed windows pause two minutes. This is an approaching foreground-region heuristic, **not deer recognition**.

Stationary large object rejected; approaching object triggered; visible small-object repeat rejected in recorded indoor trials. User confirmed battery-only operation. Current draw, runtime and outdoor accuracy have not been measured here; outdoor observations have not yet been supplied. The buzzer was physically unplugged during the later tests, though the firmware still drives GPIO10. TFT and Wi-Fi are disabled in current firmware.

Download/clone the repository, then open `tests/index.html` locally for all saved sessions. GitHub displays HTML source rather than running the gallery. Existing Lab 5 and the collaborator's upstream repository are preserved.
