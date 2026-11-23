# Current handoff — November 23, 2026

## Firmware and hardware

The default PlatformIO environment is `vibration_fusion` in `firmware/motion-size`. Main board: Adafruit ESP32-S3 TFT Feather (MAC ac:27:6e:b1:98:b8), OV5640, PIR OUT GPIO5, buzzer GPIO10, RGB R13/G36/B35. Feather V2 reads vibration DO on GPIO27. PIR uses a separate battery supply with common ground to the S3. Keep camera power connections secure. See the source camera configuration for the authoritative camera pin assignments.

The Feather vibration board communicates with the S3's Feeder-Main Wi-Fi AP via POST /vibration. PIR HIGH for 100 ms opens a 10-second vibration window; LOW for 500 ms rearms PIR. Qualifying vibration starts a camera burst of up to ten frames. Startup PIR warm-up is 60 seconds. Keep the view empty during baseline calibration (12 frames after settling).

## Current image comparison

320x240 JPEGs are decoded to RGB; 4x4 block averages form an 80x60 grid. The original luminance contrast threshold is restored to 25, with median brightness-offset compensation. A 3x3 majority filter and largest four-connected region determine area. Grayscale qualifies at 336 blocks (7%).

Color assistance is enabled at calibration only if at least 75% of baseline blocks have luminance below 20/255. Mode remains fixed until recalibration/reset; it does not automatically follow sunset. For each block, RGB differences from baseline produce a chroma range (maximum channel difference minus minimum). This cancels a common additive RGB brightness offset, but not arbitrary white-balance changes. A color difference of min(25,10+baseline_luminance/4) adds the block to the assisted mask. The assisted mask combines original grayscale and color differences; it qualifies at 480 blocks (10%). Grayscale remains available in both modes. Two consecutive frames must qualify via either path; they need not use the same path.

Serial DETECTION_MODE reports dark-block percentage and mode. DETECTION_SCORES reports separate grayscale and assisted percentages. An assisted score is zero when assistance is disabled. Scores during calibration are placeholders, not detection measurements.

White light is enabled before both baseline and detection capture: wait120 ms, discard two queued frames, acquire a fresh frame, then turn white off. No longer exposure-settling change was implemented. Alarm: 8 kHz, 50% duty GPIO drive, three1.5-second pulses with0.5-second gaps, white flashes5 Hz throughout5.5 seconds. Cooldown4.5 seconds begins after alarm ends. Increasing duty toward100% does not increase passive-buzzer AC drive.

## Live nighttime results and limits

The captured burst in ../tests/captures/20261123-002523-561342-outside-dark-inspection includes original JPEGs, metadata, events, and gallery. Calibration reported100% dark blocks and color assistance enabled. An earlier monitored ten-frame burst scored0% on both paths; its images were not saved. Subsequent recorded hand burst:

| Frame | Grayscale % | Assisted % |
|---|---:|---:|
|51|5.042|6.750|
|52|7.271|9.354|
|53|7.688|9.417|

The illuminated hand is visible against a mostly black background. Frames52 and53 passed grayscale; alarm activated on53 after eight captured burst frames. This is NOT evidence of color-only activation. User separately reported a black jacket failed detection and a cardboard box succeeded. Those observations lack recorded trial counts/distances or verified cardboard scores. Cardboard is a surrogate; actual deer detection, coat variability, deterrence effectiveness, runtime, and outdoor false-alarm rates remain unvalidated.

Repeated JPEG failures occurred before the user secured a reportedly loose3.3V connection. Following reset, monitored startup images decoded and all12 baseline samples completed without observed errors. Connection causality remains an inference. Black fabric may have insufficient visible contrast under this illumination; proposed longer illuminated settling has not been tested.

## Build, flash, and continue testing

Use PlatformIO ESP-IDF environment `vibration_fusion`; `classifier_test` retains historical growth-gate behavior and is not the deployed default. Example: `python -m platformio run -d deer_deterrent/firmware/motion-size -e vibration_fusion`. Upload adds `-t upload --upload-port COM5` (verify actual port). The checked-in platformio.ini currently contains machine-specific V: paths; map V: to the user profile on this workstation or adapt core_dir/packages_dir on another machine. Firmware was successfully built and flashed; live serial scores confirmed new code running.

Use tools/record_photos.py to record transfers and scores. Test vibration-only, PIR-only, combined visible target, alarm/cooldown rearm, and nighttime black/brown/gray targets at documented distances. Preserve false negatives. Offline low-light JPEG replays used only three saved calibration images rather than the original twelve; those estimates are not live summative results. Synthetic survey examples from chat are not participant data.

Older handoff and README material describes the October growth-only version. This document supersedes conflicting current-state claims; historical evidence remains unchanged.
