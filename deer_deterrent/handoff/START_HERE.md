> **Current November 23 firmware and test status:** [Read the updated handoff](CURRENT_STATE_2026-11-23.md). The older descriptions below are historical and may describe the superseded growth-only detector.

# Team handoff: read this first

Prepared November 1, 2026. Work and recorded indoor tests: October 29-31. Repository: https://github.com/dlim0/26-ECSE395-dsl79/tree/main/deer_deterrent

## What the team is inheriting

A standalone, battery-tested prototype that wakes an OV5640 camera on PIR motion, evaluates foreground area growth locally on an ESP32-S3, and activates RGB flashes plus a passive-buzzer signal. It does not recognize deer. No laptop/Wi-Fi classifier is required by the current firmware.

The last successful normal upload used PlatformIO environment `classifier_test` on COM5. Despite its legacy name, this environment runs the **10% + growth** algorithm, not the recognition model. The separately selected `camera_diagnostic` bypasses PIR and repeatedly flashes/captures; do not leave it installed for normal testing. The TFT is intentionally off because its SPI pins drive RGB.

## Read by role

| Team need | File |
|---|---|
| Understand what happened and why we pivoted | [PARTS_AND_FINDINGS.md](PARTS_AND_FINDINGS.md) |
| Reconnect hardware | [WIRING.md](../WIRING.md) |
| Build, flash, calibrate or record images | [RUNBOOK.md](RUNBOOK.md) |
| Understand exact trigger thresholds | [Current firmware README](../firmware/motion-size/README.md) and [approach_gate.hpp](../firmware/motion-size/src/approach_gate.hpp) |
| Review proof and limitations | [Test results](../tests/README.md), then open `tests/index.html` locally |
| Troubleshoot or plan next work | [KNOWN_ISSUES.md](KNOWN_ISSUES.md) |
| Document outdoor testing | [OUTDOOR_TEST_LOG.csv](OUTDOOR_TEST_LOG.csv) |

## Findings to carry forward

- The deer model executed on-device but did not recognize the presented full-body/close-up deer images at its 0.85 threshold. We did not prove the cause or retrain it.
- Size-only detection worked for some indoor surrogates, but persistent background changes near 5.5% caused repeated alarms.
- Current growth gate rejected a stationary object around 16.3%, accepted an approaching object growing from 15.0% to 32.646%, and rejected a small visible object whose maximum was 7.458%.
- These are single-scene indoor surrogate trials, not deer/bird accuracy statistics. A nearby small object can look large; a distant deer can look small.
- User confirmed the complete setup operates on battery. Duration/current were not measured. Outdoor testing was planned to be self-documented; no outdoor results were supplied for this handoff.
- Earlier sound-and-light operation was confirmed by the user. The buzzer was later unplugged because jumpers ran out; the growth tests verify alarm commands/light behavior, not a newly verified audible buzzer.

## Quick start without changing code

Use the current wiring, mount the camera, power on with an empty view, and allow startup reference learning plus 60-second PIR warmup. PIR must go LOW before a new HIGH can trigger. Do not move the camera after calibration. The test detector expects a gradual approach over multiple frames; a large stationary object should not alarm.

For saved galleries, extract the complete shared-drive ZIP and open `deer_deterrent/tests/index.html`. Keep images/JSON beside each gallery's index.html. Upload the complete ZIP rather than isolated HTML files.
