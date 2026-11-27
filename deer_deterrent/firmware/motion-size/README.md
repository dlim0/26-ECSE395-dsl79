# Main-board firmware: PIR, vibration and image change

The default PlatformIO environment is `vibration_fusion`. It runs on the Adafruit ESP32-S3 TFT Feather with the OV5640 camera, PIR input, RGB light and sound output. The [runbook](../../FinalReportCode/RUNBOOK.md) gives explicit build and recording commands; [VIBRATION_TEST.md](VIBRATION_TEST.md) defines the feeder message. The preserved [November 23 account](../../FinalReportCode/CURRENT_STATE_2026-11-23.md) describes the hardware session and its limits.

## Environments

All environments compile [src/app_main.cpp](src/app_main.cpp) with the definitions in [platformio.ini](platformio.ini). Select the named target for the operation being checked.

| Environment | Behavior |
|---|---|
| `vibration_fusion` — default | PIR qualification, a fresh vibration notification, then the current grayscale/color-assisted image rule and output cycle |
| `vibration_receiver` | Wi-Fi/message and output verification: a fresh notification starts the output cycle; PIR and image decisions are bypassed, and the camera stays in standby |
| `pir_wifi_camera_test` | Wi-Fi remains on; qualified PIR directly starts image capture without waiting for vibration. The automatic deterrent is suppressed and a qualifying result is labeled `LARGE_CHANGE_TEST_ONLY` |
| `pir_diagnostic` | Local PIR/light diagnostic with the camera in standby |
| `pir_camera_bench` | Local PIR-triggered camera checks plus the `TONE`, `TONE_LOW` and `TONE_CYCLE` speaker bench commands |
| `camera_diagnostic` | Repeated illuminated capture/decode checks, independent of PIR; `CAMERA_TEST` area values are placeholders |
| `classifier_test` | The retained grayscale/growth alternative, with Wi-Fi off. The environment name does not select the deer-recognition model |

The diagnostic environments have their own trigger/output behavior. Uploading one replaces the fusion program until fusion is uploaded again. The `SOUND` command remains a separate manual output check in the main processing loop, including the Wi-Fi camera test; suppression of that test's automatic output does not turn it into a physical output-disconnection check.

## Fusion startup and trigger sequence

At startup, keep the camera fixed and its view empty through the eight-second settling interval and all twelve reference frames. PIR warm-up lasts sixty seconds. The program prints `DETECTION_MODE` when calibration finishes; that line identifies whether the reference enabled color assistance. Startup still runs the image and retained growth self-checks, so an `APPROACH_SELFTEST` line is not the selected operating mode. The fusion startup line is `READY VIBRATION_FUSION`.

Once calibration and warm-up are complete and no output/cooldown is active:

1. PIR LOW for at least 500 ms rearms the input. A following HIGH for at least 100 ms opens a ten-second vibration window, with the camera in standby.
2. Opening the window discards earlier notifications. The [receiver](src/vibration_receiver.hpp) accepts the exact `vibration` message and retains the latest receipt time; a consumed event must be no more than two seconds old. A fresh event during the open window starts the camera even if PIR has since returned LOW.
3. A window that expires without such an event ends with `VIBRATION_TIMEOUT`. It requires another qualified PIR event before a later notification can start capture.
4. A started burst evaluates up to ten frame attempts. It ends immediately when two consecutive frames qualify, or ends unconfirmed at the limit. JPEG-decode failures clear consecutive qualification and consume an attempt; camera-start or capture failures abort the burst.

A failed ten-frame attempt has no timed post-miss pause in fusion mode. Another attempt needs a fresh LOW/HIGH qualification and vibration notification. Notifications outside the required window do not queue a future camera response.

## Image rule

Every 320 × 240 JPEG is decoded to RGB. Averages over 4 × 4 pixel blocks form an 80 × 60 analysis grid. The twelve reference frames establish both luminance and per-channel RGB baselines.

**Grayscale route.** Subtract the reference luminance and compensate the median brightness offset. A block differs when its remaining luminance difference has magnitude at least 25. A 3 × 3 majority filter requires at least five marked neighbors; the largest four-connected region is measured. At least 336 of the 4,800 blocks, or 7%, qualifies a frame.

**Assisted route.** Calibration enables assistance only when at least 75% of baseline blocks have luminance below 20/255. That choice remains fixed until recalibration or reset. For each block, form its three channel differences from the reference and take their maximum minus their minimum. A range of at least `min(25, 10 + baseline_luminance / 4)` marks a color change. This cancels a common additive RGB offset, but not arbitrary white-balance changes.

The assisted mask is the grayscale mask **OR** the enabled color-change mask. The same majority filter and largest-region measurement apply to that union; at least 480 blocks, or 10%, qualifies. Assisted area is not a count of color-only pixels. Grayscale remains available in either calibration mode.

One counter advances whenever either route qualifies and resets on a nonqualifying frame. Two consecutive qualifying frames trigger the response; they may qualify through different routes. Fusion uses this size/confirmation rule, without the retained alternative's five-frame growth requirement.

## Records and output

`DETECTION_SCORES` gives separate grayscale and assisted percentages, both cutoffs and the color-enabled flag. Assisted percentage is zero when assistance is disabled. Settling/calibration scores are placeholders, not scene-rejection measurements.

The `MOTION` record selects the grayscale region whenever grayscale qualifies or assistance does not qualify. Only an assisted-only pass selects the assisted region and its 10% cutoff. Its area/bounding box therefore describe the selected region, while the separate score line preserves the other route's context. See the [recording tools guide](../../tools/README.md) for their association and saved files.

Reference and detection captures use the same white-light sequence: turn white on, wait 120 ms, discard two queued frames, acquire a fresh frame and turn white off. RGB uses GPIO13/36/35. The TFT remains disabled because it shares the RGB pins. The camera is in standby between checks; the MCU and receiver remain active. Pictures are streamed over USB when a host is connected and are not stored persistently on the board.

In fusion mode, confirmation drives GPIO10 at 8 kHz and 50% duty for three 1.5-second pulses separated by 0.5-second gaps. White flashes at 5 Hz through the 5.5-second cycle. The timer drives the pattern independently of photo transfer. After output completion is processed, the main loop starts a 4.5-second cooldown and requires a fresh PIR rearm. Software ON/OFF records establish commands and state transitions, not an independent sound or optical measurement.

## Manual commands and reference control

In `vibration_fusion`, the USB command task accepts `BASELINE`, `ARM` and `SOUND`:

- `BASELINE` cancels current work, clears the reference, waits three seconds and learns twelve new empty frames. It selects the color-assistance mode again. It does not restart the original sixty-second warm-up clock.
- `ARM` cancels current work and requests rearming while keeping the learned reference. Use it with outputs idle for a controlled repeat; it still requires the qualified LOW/HIGH input sequence and does not bypass startup warm-up.
- `SOUND` requests the output cycle when no detection burst is active. Use it after reference learning for an output check. It bypasses the PIR/vibration/image decision and is a manual output test, not a detected-target result.

Cancelling an active output cycle sets its completion flag, so the normal post-output cooldown is still processed afterward. The recorder exposes the existing `BASELINE` and `ARM` actions through its calibration/rearm options; it does not add board commands. Close other serial readers before recording.

## Evidence and limits

The [November 23 saved session](../../tests/captures/20261123-002523-561342-outside-dark-inspection/index.html) contains eighteen pictures. Its alarm on frame 53 follows two grayscale passes; all assisted scores remain below 10%. It is evidence of that recorded sequence, not a demonstrated assisted-only benefit, a deer-recognition rate or a deterrence result. Its original gallery's three-frame caption does not describe the current two-frame rule; the gallery is preserved as recorded. The [evidence guide](../../tests/README.md) explains the partial boundaries and source-identity limits.

The learned reference and available illumination limit foreground contrast. The dated account and [outdoor observation log](../../FinalReportCode/OUTDOOR_TEST_LOG.csv) distinguish the recorded hand sequence from an unrecorded black-jacket miss and cardboard success. Trial counts and verified cardboard scores are unavailable; those observations do not supply a performance rate. The [known issues](../../FinalReportCode/KNOWN_ISSUES.md) retain the current limitations and proposed future controls. Preserve failures, conditions and distances in later trials. The older [HISTORY.md](HISTORY.md), [BUILD-STATUS.txt](BUILD-STATUS.txt) and [October test history](../../tests/HISTORY.md) remain evidence for their own program versions.
