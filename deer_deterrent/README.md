# Bird Feeder Project

The current main-board program is the `vibration_fusion` environment in [firmware/motion-size](firmware/motion-size/README.md). An Adafruit ESP32-S3 TFT Feather uses PIR motion to open a short wait for a feeder vibration notification, then compares OV5640 pictures with a learned empty view. Two qualifying pictures start the light and sound response. The decision measures foreground change; it does not identify deer.

## Current operating sequence

1. Mount the camera and keep its view empty while the program settles and learns twelve reference frames. Allow the 60-second PIR warm-up. A LOW lasting 500 ms rearms the sensor; a subsequent HIGH lasting 100 ms opens a ten-second vibration window.
2. A fresh feeder notification received during that window starts up to ten camera frames. A largest grayscale region covering at least 7% of the analysis grid qualifies. If calibration selected dark-scene color assistance, a combined grayscale/color region covering at least 10% also qualifies. Two consecutive qualifying frames may use either route.
3. Confirmation drives three 1.5-second 8 kHz output pulses with 0.5-second gaps and white flashes at 5 Hz over 5.5 seconds. A 4.5-second cooldown follows output completion. A rejected ten-frame burst has no timed post-miss pause; another attempt requires a new qualified PIR event and vibration notification.

Color assistance is selected from the learned reference and remains fixed until recalibration or reset. It is not an automatic day/night schedule. The [firmware guide](firmware/motion-size/README.md) gives the image rule, diagnostics and event meanings.

## Where to work

[FinalReportCode](FinalReportCode/START_HERE.md) records the last device implementation for ECSE395, its findings, limitations and outdoor observations. The operating guides and recording tools describe that program; host software checks do not establish additional field results.

| Location | Purpose |
|---|---|
| [Start here](FinalReportCode/START_HERE.md) | Current program, hardware references and evidence boundaries |
| [Runbook](FinalReportCode/RUNBOOK.md) | Explicit build target, Windows workflow, recording and controlled checks |
| [Motion firmware](firmware/motion-size/README.md) | All supported environments and current detection behavior |
| [Vibration interface](firmware/motion-size/VIBRATION_TEST.md) | Feeder-to-main-board HTTP contract and verification target |
| [Recording tools](tools/README.md) | Raw serial, frame/score association, session files and host checks |
| [Evidence guide](tests/README.md) and [session index](tests/index.html) | Current night record and earlier detector sessions |
| [November 23 account](FinalReportCode/CURRENT_STATE_2026-11-23.md) | Preserved account of that firmware/hardware session and its limits |
| [Parts and findings](FinalReportCode/PARTS_AND_FINDINGS.md) and [known issues](FinalReportCode/KNOWN_ISSUES.md) | October and November changes, current limitations and proposed future work |
| [Outdoor observation log](FinalReportCode/OUTDOOR_TEST_LOG.csv) | Four labeled November accounts, distinguishing saved serial evidence from reported observations |
| [Camera/RGB pin map](WIRING.md) and [source camera setup](firmware/motion-size/src/app_main.cpp) | Existing wiring reference and the program's actual pin assignments |
| [Sources](SOURCES.md) | Project attribution and preserved evidence provenance |

The feeder-side Feather V2 firmware is not included in this repository. Its required message is documented in the vibration interface. The dated handoff describes the separate PIR supply with shared ground; older power and output observations apply to their recorded configurations.

## What the saved night record shows

The November 23 session retains eighteen pictures and frame records. Frames 52 and 53 qualify through grayscale, and the software alarm starts on frame 53. The assisted score remains below 10% throughout, so this record does not demonstrate an assisted-only activation. It supplies no deer-detection rate, deterrence result or battery runtime. See the [evidence guide](tests/README.md) for the recorded sequence, partial boundaries and the original gallery's outdated confirmation caption.

The [earlier classifier](experiments/deer-classifier/README.md), [Arduino camera bring-up](experiments/camera-wifi-bringup/README.md), [motion history](firmware/motion-size/HISTORY.md) and [earlier test history](tests/HISTORY.md) remain historical material. Select the current fusion environment explicitly when building. Download or clone the repository to open HTML galleries locally with their neighboring images and metadata.
