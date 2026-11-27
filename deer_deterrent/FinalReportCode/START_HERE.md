# FinalReportCode: program, findings and course evidence

This folder records the last device implementation for ECSE395 and the observations available for it. Improvements proposed in the findings and known issues remain future work unless a separate record establishes that they were implemented and tested.

Use `vibration_fusion` for the integrated main-board program. It qualifies PIR motion, waits for a fresh feeder vibration message and then checks camera pictures against an empty reference. Grayscale area of at least 7%, or a dark-enabled grayscale/color union of at least 10%, qualifies a frame. Two consecutive qualifying frames start the output cycle. This is foreground-change detection, not deer identification.

## Read by task

| Task | Current guide or evidence |
|---|---|
| Build the intended program and record a controlled run | [Runbook](RUNBOOK.md) |
| Check the exact image rule, timing, commands or diagnostic selection | [Firmware guide](../firmware/motion-size/README.md) and [source](../firmware/motion-size/src/app_main.cpp) |
| Connect the feeder notification path | [Vibration interface](../firmware/motion-size/VIBRATION_TEST.md) |
| Interpret received bytes, measurements, dual scores and incomplete observations | [Recording tools](../tools/README.md) |
| Review the retained night run and older sessions | [Evidence guide](../tests/README.md) and [local gallery index](../tests/index.html) |
| Read the preserved hardware/test account | [November 23 record](CURRENT_STATE_2026-11-23.md) |
| Trace the October and November changes by component | [Parts and findings](PARTS_AND_FINDINGS.md) |
| Review current limitations and proposed future work | [Known issues](KNOWN_ISSUES.md) |
| Distinguish recorded and reported outdoor observations | [Outdoor log](OUTDOOR_TEST_LOG.csv) |
| Look up existing camera/RGB wiring and attribution | [Pin map](../WIRING.md), the source camera configuration, and [SOURCES.md](../SOURCES.md) |

The dated record identifies the main S3 board and OV5640, the separate PIR supply with common ground, and the feeder-side Feather V2 vibration input. It is preserved evidence. The actual camera pin assignments are in `cameraInit()` in the source. The feeder sender's source is not included here; the receiver contract is available in the vibration guide.

## Starting an observation

Mount the camera before learning the reference and keep the view empty through settling and all twelve baseline frames. Wait for the sixty-second PIR warm-up. The program then needs LOW for 500 ms followed by HIGH for 100 ms. That opens a ten-second notification window while the camera stays in standby. A fresh notification starts capture; an acknowledgement alone does not prove a camera decision or physical output.

Color assistance is selected at calibration and stays fixed until recalibration/reset. Use the current `DETECTION_MODE` and `DETECTION_SCORES` messages to interpret the chosen mode and both image paths. Baseline/settling scores and diagnostic area placeholders are not operational detection measurements. Keep the raw session and any incomplete beginning or ending rather than filling gaps from a later heartbeat.

The output program drives three 1.5-second 8 kHz pulses with 0.5-second gaps and white flashing for 5.5 seconds. Its post-output cooldown is 4.5 seconds. An unconfirmed burst has no timed post-miss pause. The firmware guide describes the fresh-input requirement and manual-command behavior.

## What is demonstrated

The retained November 23 run shows a grayscale-qualified software alarm on frame 53. Color assistance was enabled, but its score stayed below 10% in every saved frame; the run does not establish color-only activation. It contains two complete camera bursts with different amounts of preceding trigger context and ends after another PIR wait opens. It supplies no unique flashed-binary identity or independent physical sound/light measurement.

The dated note also reports calibration, connection recovery and unrecorded jacket/cardboard observations. The [outdoor log](OUTDOOR_TEST_LOG.csv) retains four entries: the earlier unsaved zero-score burst, the recorded illuminated-hand sequence, the reported black-jacket miss and the reported cardboard success. Their labels identify accounts, not a complete trial denominator or four independent instrumented trials. Blank fields remain unmeasured. Keep those reports distinct from what the saved session itself contains.

## Current findings and earlier records

[PARTS_AND_FINDINGS.md](PARTS_AND_FINDINGS.md) follows the project from its early components through the November integration. [KNOWN_ISSUES.md](KNOWN_ISSUES.md) describes the limitations of the last course implementation and proposed future work. Both contain current November findings.

The [November 1 validation record](VALIDATION.md), original [November 1 overview](index.html), [motion history](../firmware/motion-size/HISTORY.md) and [test history](../tests/HISTORY.md) preserve earlier configurations and observations. Their earlier growth-gate, Wi-Fi-off, power and output statements apply to those versions. Use the operating guides above for the current program.

Open HTML galleries from a complete local checkout or download, keeping each gallery beside its original images, JSON and events. Preserve the four November outdoor entries and their unmeasured fields; put future observations, including actual conditions and failures, in separate records.
